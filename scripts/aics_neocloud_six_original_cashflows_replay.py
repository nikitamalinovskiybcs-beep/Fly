"""Six exact original CoreWeave/Nebius SEC cashflow disclosure numeric audits.

CoreWeave Q1/H1/9M originals use USD thousands with cash purchases of
property/equipment including capitalized software. Nebius Q1/Q2/Q3
original 6-K exhibits use USD millions, Q1 whole group, and Q2/Q3
continuing-operation periods. Q2 Nebius is taken from its explicit
quarter column, not wrongly derived from incomparable H1 minus Q1.
Original raw bytes are rehashed, values independently parsed and 3
research cohort totals replayed. No historic first-feed/PIT certification.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path

from scripts.aics_arcc_seven_original_nonaccrual_replay import VisibleText
from scripts.aics_priority100_workbench import ROOT,REPORTS,TARGETED,verify_gzip_original

LEDGER=Path("aics_data/research/neoclouds_2025_q1_q3_sec_cashflow_research_2026-11-21.json")
QUEUE=ROOT/"aics_priority100_evidence_queue.json"
OUT=ROOT/"aics_neocloud_six_original_issuer_cashflows_replay.json"
CRWV_CFO=re.compile(
    r"Net cash provided by(?: \(used in\))? operating activities"
    r"\s*\$\s*(\(?\s*[\d,]+\s*\)?)\s*\$\s*[\d,]+",re.I,
)
CRWV_CAPEX=re.compile(
    r"Purchase of property and equipment, including capitalized internal-use software"
    r"\s*\$\s*\(\s*([\d,]+)\s*\)\s*\$",re.I,
)
NEG_NUM=re.compile(r"\(\s*([\d,]+(?:\.\d+)?)\s*\)")
PERIODS={
    "2025-Q1":("crwv_q1","nbis_q1"),
    "2025-Q2":("crwv_h1","nbis_q2"),
    "2025-Q3":("crwv_9m","nbis_9m"),
}


def normalized_text(raw):
    parser=VisibleText()
    parser.feed(raw.decode("utf-8",errors="replace"))
    return " ".join(" ".join(parser.parts).split())


def dec(x):
    x=str(x).strip()
    negative=x.startswith("(") and x.endswith(")")
    x=x.strip("() ").replace(",","")
    value=Decimal(x)
    return -value if negative else value


def _unique(values):
    vals=set(values)
    return next(iter(vals)) if len(vals)==1 else None


def parse_coreweave(raw):
    text=normalized_text(raw)
    cf=_unique(dec(m.group(1)) for m in CRWV_CFO.finditer(text))
    pp=_unique(Decimal(m.group(1).replace(",","")) for m in CRWV_CAPEX.finditer(text))
    if cf is None or pp is None or pp<=0:
        return {"found_original_current_period_cashflow_pair":False}
    return {
        "found_original_current_period_cashflow_pair":True,
        "cfo_ytd_usd_m":str(cf/1000),
        "cash_purchases_ytd_usd_m":str(pp/1000),
        "original_table_units":"USD thousands, divided by 1000",
        "cash_capex_scope":"PP&E including capitalized internal-use software",
    }


def source_parenthetical_pairs(text,label,*,minimum=2):
    matches=list(re.finditer(re.escape(label),text,re.I))
    candidates=[]
    for m in matches:
        # Nearby values only, never search later sections for a target number.
        vals=[Decimal(s.replace(",","")) for s in NEG_NUM.findall(
            text[m.end():m.end()+175])]
        if len(vals)>=minimum:
            candidates.append(vals[:minimum])
    if not candidates:
        return None
    unique={tuple(row) for row in candidates}
    return list(next(iter(unique))) if len(unique)==1 else None


def parse_nebius(raw,period):
    text=normalized_text(raw)
    if period=="2025-Q1":
        c=source_parenthetical_pairs(text,"Cash used in operating activities")
        p=source_parenthetical_pairs(text,"Puchases of property, plant and equipment")
        if not c or not p:
            return {"found_original_current_period_cashflow_pair":False}
        return {"found_original_current_period_cashflow_pair":True,
                "cfo_quarter_usd_m":str(-c[1]),
                "cash_purchases_quarter_usd_m":str(p[1]),
                "source_scope":"Q1 whole group before Toloka deconsolidation"}
    if period=="2025-Q2":
        c=source_parenthetical_pairs(
            text,"Cash used in operating activities – continuing operations",minimum=4)
        p=source_parenthetical_pairs(
            text,"Purchases of property, plant and equipment",minimum=4)
        if not c or not p:
            return {"found_original_current_period_cashflow_pair":False}
        return {"found_original_current_period_cashflow_pair":True,
                "cfo_quarter_usd_m":str(-c[1]),
                "cash_purchases_quarter_usd_m":str(p[1]),
                "cfo_h1_usd_m":str(-c[3]),
                "cash_purchases_h1_usd_m":str(p[3]),
                "source_scope":"explicit continuing-operations Q2 and H1; no H1-minus-Q1"}
    if period=="2025-Q3":
        c=source_parenthetical_pairs(text,"Net cash used in operating activities")
        p=source_parenthetical_pairs(text,"Capital expenditures")
        if not c or not p:
            return {"found_original_current_period_cashflow_pair":False}
        return {"found_original_current_period_cashflow_pair":True,
                "cfo_9m_usd_m":str(-c[1]),
                "cash_purchases_9m_usd_m":str(p[1]),
                "source_scope":"continuing operations 9M, separately disclosed capital expenditures"}
    raise ValueError("Unexpected Nebius period")


def _key(row):
    return (str(int(row["CIK"])),row["accession"])


def build(ledger,queue,reports,targeted):
    if (ledger.get("schema")!="aics-neocloud-2025-q1-q3-original-sec-research-v1"
        or len(ledger.get("sources",{}))!=6
        or len(ledger.get("observations",[]))!=3
        or queue.get("schema")!="aics-priority100-evidence-workbench-v1"
        or queue.get("full_11node_AICS") is not None
        or queue.get("independently_certified_nodes")!=0
        or len(queue.get("priority_queue",[]))!=100
        or reports.get("schema")!="aics-PIT100-distinct-original-SEC-primary-report-downloads-v1"
        or targeted.get("schema")!="aics-PIT100-targeted-original-scoring-accession-SGML-fill-v1"):
        raise ValueError("Neocloud SEC source-to-score evidence input invalid")
    tasks={_key(r):r for r in queue["priority_queue"]
           if r["workstream"]=="exact_SEC_source_bytes_and_numeric_replay"}
    base={_key(r):r for r in reports["tasks"]}
    added={_key(r):r for r in targeted["targeted_source_results"]}
    rows={}
    observations=[]
    for period,(crwv,nbis) in PERIODS.items():
        for skey in (crwv,nbis):
            src=ledger["sources"][skey]
            cik_match=re.fullmatch(
                r"https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/[A-Za-z0-9_.-]+",
                src["source_page"])
            if cik_match is None:
                raise ValueError("Invalid first-original SEC score source address")
            accession=f"{cik_match.group(2)[:10]}-{cik_match.group(2)[10:12]}-{cik_match.group(2)[12:]}"
            if accession!=src["accession"]:
                raise ValueError("Original source accession or SEC URL mismatched")
            key=(str(int(cik_match.group(1))),accession)
            task=tasks.get(key)
            if (task is None or task["cohort"]!=f"NEOCLOUDS:{period}"
                or task["issuer"]!=src["issuer"]
                or task["exact_referenced_document_and_sgml_bytes_rehashed"] is not True):
                # Do not claim independently verified numeric source data merely
                # from an issuer URL or metadata.
                rows[skey]={"source_key":skey,"issuer":src["issuer"],
                            "source_bytes_rehashed":False,
                            "original_numeric_claims_reproduced":False,
                            "state":"BLOCKED_SOURCE_OR_MATCH"}
                continue
            if task["archive_origin"]=="original_100_document_sample":
                filing=base.get(key)
                path=filing.get("compressed_archive_path") if filing else None
                sha=filing.get("raw_SHA256") if filing else None
            elif task["archive_origin"]=="targeted_exact_original":
                filing=added.get(key)
                path=filing.get("original_doc_gzip_archived_path") if filing else None
                sha=filing.get("original_doc_raw_sha256") if filing else None
            else:
                raise ValueError("Unsupported original SEC archive origin")
            result={"source_key":skey,"issuer":src["issuer"],"accession":accession,
                    "source_bytes_rehashed":False,
                    "original_numeric_claims_reproduced":False,
                    "historical_first_data_feed_attested":False,
                    "state":"BLOCKED_SOURCE_OR_MATCH"}
            if path and verify_gzip_original(path,sha):
                result["source_bytes_rehashed"]=True
                with gzip.open(path,"rb") as fp:
                    raw=fp.read(48_000_001)
                if len(raw)>48_000_000:
                    raise ValueError("SEC original size exceeds safety cap")
                extracted=(parse_coreweave(raw) if src["issuer"]=="CoreWeave"
                           else parse_nebius(raw,period))
                required=("cfo_ytd","cash_purchases_ytd") if src["issuer"]=="CoreWeave" else (
                    ("cfo_quarter","cash_purchases_quarter") if period!="2025-Q3"
                    else ("cfo_9m","cash_purchases_9m"))
                if period=="2025-Q2" and src["issuer"]=="Nebius":
                    required+=("cfo_h1","cash_purchases_h1")
                good=(extracted["found_original_current_period_cashflow_pair"] is True
                      and all(Decimal(extracted[k+"_usd_m"])==Decimal(src[k])
                              for k in required))
                result.update({
                    "original_numeric_extraction":extracted,
                    "original_numeric_claims_reproduced":bool(good),
                    "original_raw_sha256":sha,
                    "state":"ORIGINAL_ISSUER_CASHFLOWS_REPLAYED_NOT_HISTORICALLY_PIT"
                        if good else "BLOCKED_SOURCE_OR_MATCH",
                })
            rows[skey]=result

    # Score is only computed when all six underlying raw original source
    # checks pass, including source period and cashflow comparability flags.
    all_ok=all(r["original_numeric_claims_reproduced"] for r in rows.values()) and len(rows)==6
    if all_ok:
        a=lambda k,field:Decimal(rows[k]["original_numeric_extraction"][field+"_usd_m"])
        quarters={
            "2025-Q1":(a("crwv_q1","cfo_ytd"),a("crwv_q1","cash_purchases_ytd"),
                       a("nbis_q1","cfo_quarter"),a("nbis_q1","cash_purchases_quarter")),
            "2025-Q2":(a("crwv_h1","cfo_ytd")-a("crwv_q1","cfo_ytd"),
                       a("crwv_h1","cash_purchases_ytd")-a("crwv_q1","cash_purchases_ytd"),
                       a("nbis_q2","cfo_quarter"),a("nbis_q2","cash_purchases_quarter")),
            "2025-Q3":(a("crwv_9m","cfo_ytd")-a("crwv_h1","cfo_ytd"),
                       a("crwv_9m","cash_purchases_ytd")-a("crwv_h1","cash_purchases_ytd"),
                       a("nbis_9m","cfo_9m")-a("nbis_q2","cfo_h1"),
                       a("nbis_9m","cash_purchases_9m")-a("nbis_q2","cash_purchases_h1")),
        }
        for period,(cfo1,cap1,cfo2,cap2) in quarters.items():
            observed=next(x for x in ledger["observations"] if x["period"]==period)
            tot=cfo1+cfo2
            cap=cap1+cap2
            research_score=Decimal(100)*max(Decimal(0),min(Decimal(1),(cap-tot)/cap))
            research_score=research_score.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
            match=(cap>0 and
                   (cfo1,cap1,cfo2,cap2,tot,cap,research_score)==tuple(
                       Decimal(observed[k]) for k in (
                           "coreweave_operating_cash_m","coreweave_cash_purchases_m",
                           "nebius_operating_cash_m","nebius_cash_purchases_m",
                           "total_operating_cash_m","total_cash_purchases_m","score"
                       )
                   ))
            observations.append({
                "period":period,"original_financial_inputs_replayed":bool(match),
                "research_score_from_original_issuer_data_NOT_AICS":str(research_score),
                "combined_issuer_CFO_usd_m":str(tot),
                "combined_issuer_cash_purchases_usd_m":str(cap),
                "issuer_cashflow_scope_comparable_across_all_quarters":False,
            })

    return {
        "schema":"aics-six-original-neocloud-issuer-cashflow-source-replay-v1",
        "as_of":queue["as_of"],
        "six_exact_original_source_tasks":6,
        "original_raw_sha_reverified":sum(x["source_bytes_rehashed"] for x in rows.values()),
        "issuer_source_numeric_claims_reproduced":sum(x["original_numeric_claims_reproduced"] for x in rows.values()),
        "research_period_scores_reproduced_from_all_original_source_bytes":sum(
            x["original_financial_inputs_replayed"] for x in observations),
        "first_historical_public_data_delivery_verified":False,
        "2025_Q1_Nebius_scope_differs_from_continuing_operations_in_Q2_Q3":True,
        "independent_24month_OOS":None,
        "certified_11node_AICS":None,
        "trades_created":False,
        "source_results":rows,
        "research_events":observations,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger",type=Path,default=LEDGER)
    parser.add_argument("--queue",type=Path,default=QUEUE)
    parser.add_argument("--reports",type=Path,default=REPORTS)
    parser.add_argument("--targeted",type=Path,default=TARGETED)
    parser.add_argument("--out",type=Path,default=OUT)
    args=parser.parse_args()
    files=[args.ledger,args.queue,args.reports,args.targeted]
    data=build(*(json.loads(p.read_text(encoding="utf-8")) for p in files))
    data["input_sha256"]={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in data.items() if k not in ("source_results","research_events")}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
