"""Independently replay 7 ARCC original SEC non-accrual disclosure pairs.

The original issuer's contemporaneous current-period amortized-cost and
fair-value non-accrual percentages are parsed from exact accession documents.
No revised issuer reports, synthetic values, historical first-feed claims,
full AICS node certification or trading signals are created.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

from scripts.aics_priority100_workbench import (
    ROOT, REPORTS, TARGETED, verify_gzip_original,
)

LEDGER=Path("aics_data/research/private_credit_2024q2_2026q1_first_sec_cost_breadth_2026-11-22.json")
QUEUE=ROOT/"aics_priority100_evidence_queue.json"
OUT=ROOT/"aics_arcc_seven_original_nonaccrual_numeric_replay.json"
PERIODS=("2024-Q3","2024-Q4","2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q1")
DISCLOSURE=re.compile(
    r"loans on non[\s-]*accrual status represented\s*"
    r"(\d{1,2}(?:\.\d+)?)\s*%\s*of the total investments at amortized cost"
    r"\s*\(or\s*(\d{1,2}(?:\.\d+)?)\s*%\s*at fair value\)",
    re.I,
)


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
        self.skip_depth=0

    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):
            self.skip_depth+=1

    def handle_endtag(self,tag):
        if tag in ("script","style") and self.skip_depth:
            self.skip_depth-=1

    def handle_data(self,data):
        if not self.skip_depth:
            self.parts.append(data)


def extract_pair(raw):
    parser=VisibleText()
    parser.feed(raw.decode("utf-8",errors="replace"))
    text=" ".join(" ".join(parser.parts).split())
    matches=list(DISCLOSURE.finditer(text))
    values={(Decimal(m.group(1)),Decimal(m.group(2))) for m in matches}
    pair=next(iter(values)) if len(values)==1 else None
    return {
        "unique_original_current_period_cost_fair_pair":pair is not None,
        "original_candidate_occurrences":len(matches),
        "different_candidate_pairs":len(values),
        "amortized_cost_nonaccrual_pct":str(pair[0]) if pair else None,
        "fair_value_nonaccrual_pct":str(pair[1]) if pair else None,
        "original_excerpt":text[matches[0].start():matches[0].end()+125] if pair else None,
    }


def _key(row):
    return (str(int(row["CIK"])),row["accession"])


def build(ledger,queue,reports,targeted,*,extractor=extract_pair):
    if (ledger.get("schema")!="aics-private-credit-2024q2-2026q1-8quarter-original-sec-cost-breadth-expost-v1"
        or ledger.get("weight")!=150 or ledger.get("weight_total")!=1050
        or len(ledger.get("original_issuer_quarter_observations",[]))!=24
        or queue.get("schema")!="aics-priority100-evidence-workbench-v1"
        or queue.get("full_11node_AICS") is not None
        or queue.get("independently_certified_nodes")!=0
        or len(queue.get("priority_queue",[]))!=100
        or reports.get("schema")!="aics-PIT100-distinct-original-SEC-primary-report-downloads-v1"
        or targeted.get("schema")!="aics-PIT100-targeted-original-scoring-accession-SGML-fill-v1"):
        raise ValueError("ARCC source ledger / priority source provenance invalid")
    candidates=[x for x in ledger["original_issuer_quarter_observations"]
                if x["issuer"]=="ARCC" and x["quarter"] in PERIODS]
    if len(candidates)!=7 or {x["quarter"] for x in candidates}!=set(PERIODS):
        raise ValueError("Seven original dated ARCC issuer quarters required")
    taskmap={_key(x):x for x in queue["priority_queue"]
             if x["workstream"]=="exact_SEC_source_bytes_and_numeric_replay"}
    basemap={_key(x):x for x in reports["tasks"]}
    newmap={_key(x):x for x in targeted["targeted_source_results"]}
    out=[]
    for quarter in PERIODS:
        row=next(x for x in candidates if x["quarter"]==quarter)
        original_url=row["original_numeric_source_url"]
        match=re.fullmatch(
            r"https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/[A-Za-z0-9_.-]+",
            original_url
        )
        if match is None or str(int(match.group(1)))!=row["cik"]:
            raise ValueError("ARCC original SEC source URL/CIK mismatch")
        acc=match.group(2)
        accession=f"{acc[:10]}-{acc[10:12]}-{acc[12:]}"
        key=(row["cik"],accession)
        task=taskmap.get(key)
        if task is None or task["cohort"]!=f"PRIVATE_CREDIT:{quarter}" or task["issuer"]!="ARCC":
            raise ValueError("Missing original ARCC accession/correct cohort in Priority100")
        res={
            "issuer":"ARCC","quarter":quarter,"CIK":key[0],"accession":accession,
            "original_document_url":original_url,
            "original_source_bytes_rehashed":False,
            "original_cost_and_fair_numbers_reproduced":False,
            "independent_historical_first_delivery":False,
            "state":"BLOCKED_ORIGINAL_DOCUMENT_OR_NUMERIC",
        }
        if task["exact_referenced_document_and_sgml_bytes_rehashed"]:
            archive=task["archive_origin"]
            if archive=="original_100_document_sample":
                src=basemap.get(key)
                filename=src.get("compressed_archive_path") if src else None
                sha=src.get("raw_SHA256") if src else None
            elif archive=="targeted_exact_original":
                src=newmap.get(key)
                filename=src.get("original_doc_gzip_archived_path") if src else None
                sha=src.get("original_doc_raw_sha256") if src else None
            else:
                raise ValueError("Unrecognized original source archive origin")
            if filename and verify_gzip_original(filename,sha):
                res["original_source_bytes_rehashed"]=True
                with gzip.open(filename,"rb") as f:
                    original=f.read(48_000_001)
                if len(original)>48_000_000:
                    raise ValueError("Original document exceeds SEC source byte guard")
                parsed=extractor(original)
                cost=parsed["amortized_cost_nonaccrual_pct"]
                fair=parsed["fair_value_nonaccrual_pct"]
                success=(parsed["unique_original_current_period_cost_fair_pair"]
                         and cost is not None and fair is not None
                         and Decimal(cost)==Decimal(row["nonaccrual_amortized_cost_pct"])
                         and Decimal(fair)==Decimal(row["nonaccrual_fair_value_pct"]))
                res.update({
                    "original_numeric_extraction":parsed,
                    "original_cost_and_fair_numbers_reproduced":bool(success),
                    "state":"ORIGINAL_ARCC_NUMERIC_PAIR_REPLAYED_NOT_HISTORICAL_PIT"
                        if success else "BLOCKED_ORIGINAL_DOCUMENT_OR_NUMERIC",
                    "original_raw_sha256":sha,
                })
        out.append(res)
    return {
        "schema":"aics-arcc-seven-original-SEC-cost-fair-nonaccrual-replay-v1",
        "as_of":queue["as_of"],
        "original_ARCC_quarter_tasks_executed":7,
        "exact_original_hashes_reverified":sum(x["original_source_bytes_rehashed"] for x in out),
        "original_source_cost_and_fair_pairs_reproduced":
            sum(x["original_cost_and_fair_numbers_reproduced"] for x in out),
        "blocked_original_numeric_pairs":sum(not x["original_cost_and_fair_numbers_reproduced"] for x in out),
        "accounting_statement_source_only_not_full_private_credit_node":True,
        "independent_historical_first_feed_attested":False,
        "approved_24month_OOS":None,
        "certified_AICS_nodes":0,
        "production_AICS":None,
        "trades_created":False,
        "events":out,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger",type=Path,default=LEDGER)
    p.add_argument("--queue",type=Path,default=QUEUE)
    p.add_argument("--reports",type=Path,default=REPORTS)
    p.add_argument("--targeted",type=Path,default=TARGETED)
    p.add_argument("--out",type=Path,default=OUT)
    args=p.parse_args()
    paths=(args.ledger,args.queue,args.reports,args.targeted)
    data=build(*(json.loads(x.read_text(encoding="utf-8")) for x in paths))
    data["input_sha256"]={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in paths}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in data.items() if k!="events"}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
