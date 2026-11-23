"""Reopen exact seven BXSL and seven OBDC SEC originals and replay cost ratios.

BXSL: first-period "percentage of assets on non-accrual, at amortized cost"
row. OBDC: original performing/non-accrual *amortized-cost* table, checked
from both reported percentage and independent nonaccrual/total amounts.
Other issuer or fair-value denominators are not silently substituted.
All historical source delivery and forecasting certification remain false.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_arcc_seven_original_nonaccrual_replay import (
    LEDGER, QUEUE, REPORTS, TARGETED, PERIODS, VisibleText,
)
from scripts.aics_priority100_workbench import ROOT,verify_gzip_original

OUT=ROOT/"aics_bxsl_obdc_fourteen_original_nonaccrual_numeric_replay.json"
BXSL=re.compile(
    r"Percentage of assets on non-accrual, at amortized cost\s*"
    r"(?:\(\d+\))*\s*(\d{1,3}(?:\.\d+)?)\s*%",re.I
)
OBDC_ANCHOR=re.compile(
    r"the table below presents the amortized cost(?: and fair value)? "
    r"of our performing and non-accrual(?: debt)? investments",re.I
)
OBDC_ROW=re.compile(
    r"\bNon-accrual\s+([\d,]+)\s+(\d{1,3}(?:\.\d+)?)\s+.*?"
    r"\bTotal\s+\$\s*([\d,]+)",re.I
)


def extract_cost(raw,issuer):
    parser=VisibleText()
    parser.feed(raw.decode("utf-8",errors="replace"))
    text=" ".join(" ".join(parser.parts).split())
    if issuer=="BXSL":
        found=list(BXSL.finditer(text))
        vals={Decimal(m.group(1)) for m in found}
        value=next(iter(vals)) if len(vals)==1 else None
        return {
            "issuer":issuer,
            "source_values_unique":len(vals)==1,
            "matches":len(found),
            "original_first_period_amortized_cost_nonaccrual_pct":str(value) if value is not None else None,
            "original_source_numeric_dollars_thousands":None,
            "reported_percent_matches_independent_amount_fraction":None,
            "source_excerpt":text[found[0].start():found[0].end()+80] if value is not None else None,
        }
    if issuer!="OBDC":
        raise ValueError("Unsupported BDC source parser")
    anchors=list(OBDC_ANCHOR.finditer(text))
    candidates=[]
    for anchor in anchors:
        match=OBDC_ROW.search(text[anchor.end():anchor.end()+1500])
        if match:
            cost=int(match.group(1).replace(",",""))
            pct=Decimal(match.group(2))
            total=int(match.group(3).replace(",",""))
            if cost<0 or total<=0 or cost>total:
                raise ValueError("Impossible OBDC original amortized cost table")
            implied=(Decimal(cost)*100/Decimal(total)).quantize(
                Decimal("0.1"),rounding=ROUND_HALF_UP
            )
            candidates.append((pct,cost,total,implied,anchor.start()))
    unique={(pct,cost,total) for pct,cost,total,_,_ in candidates}
    row=candidates[0] if len(unique)==1 else None
    matched=row is not None and row[0]==row[3]
    return {
        "issuer":issuer,
        "source_values_unique":bool(row is not None),
        "matches":len(candidates),
        "original_first_period_amortized_cost_nonaccrual_pct":str(row[0]) if row else None,
        "original_source_numeric_dollars_thousands":{
            "nonaccrual_amortized_cost":row[1],"total_amortized_cost":row[2]
        } if row else None,
        "reported_percent_matches_independent_amount_fraction":bool(matched),
        "source_excerpt":text[row[4]:row[4]+550] if row else None,
    }


def _key(rec):
    return (str(int(rec["CIK"])),rec["accession"])


def build(ledger,queue,reports,targeted,*,extractor=extract_cost):
    if (ledger.get("schema")!="aics-private-credit-2024q2-2026q1-8quarter-original-sec-cost-breadth-expost-v1"
        or len(ledger.get("original_issuer_quarter_observations",[]))!=24
        or ledger.get("weight")!=150 or ledger.get("weight_total")!=1050
        or queue.get("schema")!="aics-priority100-evidence-workbench-v1"
        or queue.get("independently_certified_nodes")!=0
        or queue.get("full_11node_AICS") is not None
        or len(queue.get("priority_queue",[]))!=100
        or reports.get("schema")!="aics-PIT100-distinct-original-SEC-primary-report-downloads-v1"
        or targeted.get("schema")!="aics-PIT100-targeted-original-scoring-accession-SGML-fill-v1"):
        raise ValueError("BDC original source/queue schema or safety invariant broken")
    tasks={_key(x):x for x in queue["priority_queue"]
           if x["workstream"]=="exact_SEC_source_bytes_and_numeric_replay"}
    base={_key(x):x for x in reports["tasks"]}
    added={_key(x):x for x in targeted["targeted_source_results"]}
    out=[]
    for issuer in ("BXSL","OBDC"):
        originals=[x for x in ledger["original_issuer_quarter_observations"]
                   if x["issuer"]==issuer and x["quarter"] in PERIODS]
        if len(originals)!=7 or {r["quarter"] for r in originals}!=set(PERIODS):
            raise ValueError("Not seven original BDC source quarters for "+issuer)
        for period in PERIODS:
            row=next(x for x in originals if x["quarter"]==period)
            match=re.fullmatch(
                r"https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/[A-Za-z0-9_.-]+",
                row["original_numeric_source_url"]
            )
            if not match or str(int(match.group(1)))!=row["cik"]:
                raise ValueError("Invalid SEC provenance or mismatched issuer CIK")
            acc=match.group(2)
            accession=f"{acc[:10]}-{acc[10:12]}-{acc[12:]}"
            key=(row["cik"],accession)
            task=tasks.get(key)
            if (task is None or task["issuer"]!=issuer
                or task["cohort"]!=f"PRIVATE_CREDIT:{period}"):
                raise ValueError("Missing exact SEC accession for research issuer-period")
            result={
                "issuer":issuer,"quarter":period,"accession":accession,
                "original_document_url":row["original_numeric_source_url"],
                "original_source_bytes_rehashed":False,
                "original_issuer_cost_percentage_reproduced":False,
                "historical_first_provider_receipt_verified":False,
                "status":"BLOCKED_SOURCE_OR_NUMERIC",
            }
            if task["exact_referenced_document_and_sgml_bytes_rehashed"]:
                if task["archive_origin"]=="original_100_document_sample":
                    src=base.get(key)
                    path=src.get("compressed_archive_path") if src else None
                    sha=src.get("raw_SHA256") if src else None
                elif task["archive_origin"]=="targeted_exact_original":
                    src=added.get(key)
                    path=src.get("original_doc_gzip_archived_path") if src else None
                    sha=src.get("original_doc_raw_sha256") if src else None
                else:
                    raise ValueError("Unsupported SEC original archive source")
                if path and verify_gzip_original(path,sha):
                    result["original_source_bytes_rehashed"]=True
                    with gzip.open(path,"rb") as f:
                        raw=f.read(48_000_001)
                    if len(raw)>48_000_000:
                        raise ValueError("Original SEC disclosure larger than cap")
                    parsed=extractor(raw,issuer)
                    valid=(parsed["source_values_unique"] is True
                           and parsed["original_first_period_amortized_cost_nonaccrual_pct"] is not None
                           and Decimal(parsed["original_first_period_amortized_cost_nonaccrual_pct"])==
                               Decimal(row["nonaccrual_amortized_cost_pct"])
                           and (issuer=="BXSL" or
                                parsed["reported_percent_matches_independent_amount_fraction"] is True))
                    result.update({
                        "original_numeric_extraction":parsed,
                        "original_issuer_cost_percentage_reproduced":bool(valid),
                        "status":"ORIGINAL_BDC_COST_REPLAYED_NOT_PIT" if valid
                                 else "BLOCKED_SOURCE_OR_NUMERIC",
                        "original_file_sha256":sha,
                    })
            out.append(result)
    if len(out)!=14 or len({(x["issuer"],x["quarter"]) for x in out})!=14:
        raise ValueError("14 BDC source-scoped research tasks not distinct")
    return {
        "schema":"aics-BXSL-OBDC-fourteen-original-SEC-nonaccrual-replay-v1",
        "as_of":queue["as_of"],
        "original_BXSL_OBDC_issuer_periods_attempted":14,
        "original_file_sha256_reverified":sum(x["original_source_bytes_rehashed"] for x in out),
        "original_nonaccrual_cost_percentages_reproduced":
            sum(x["original_issuer_cost_percentage_reproduced"] for x in out),
        "blocked_original_cost_percentages":
            sum(not x["original_issuer_cost_percentage_reproduced"] for x in out),
        "actual_borrower_specific_credit_loss_not_inferred":True,
        "first_publisher_feed_history_certified":False,
        "independent_24month_OOS":None,
        "certified_AICS_nodes":0,
        "full_11node_AICS":None,
        "trades_created":False,
        "events":out,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger",type=Path,default=LEDGER)
    parser.add_argument("--queue",type=Path,default=QUEUE)
    parser.add_argument("--reports",type=Path,default=REPORTS)
    parser.add_argument("--targeted",type=Path,default=TARGETED)
    parser.add_argument("--out",type=Path,default=OUT)
    args=parser.parse_args()
    paths=(args.ledger,args.queue,args.reports,args.targeted)
    result=build(*(json.loads(x.read_text(encoding="utf-8")) for x in paths))
    result["input_sha256"]={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in paths}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="events"}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
