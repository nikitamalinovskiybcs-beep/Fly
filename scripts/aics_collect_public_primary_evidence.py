#!/usr/bin/env python3
"""Collect real public primary-source evidence for AICS, without generating scores.

SEC submissions are issuer-specific raw disclosures; EIA endpoint is metadata.
Neither is automatically an 11-node numerical time series. Fail closed.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request,urlopen

OUT=Path("aics_data/source_evidence")
# CIKs are fixed identifiers, not fitted from future market outcomes.
SEC_ISSUERS={
    "MSFT":"0000789019",
    "AMZN":"0001018724",
    "GOOGL":"0001652044",
    "NVDA":"0001045810",
    "ORCL":"0001341439",
}
SOURCES=[
    ("SEC_MSFT","Hyperscalers","https://data.sec.gov/submissions/CIK0000789019.json"),
    ("SEC_AMZN","Hyperscalers","https://data.sec.gov/submissions/CIK0001018724.json"),
    ("SEC_GOOGL","Hyperscalers","https://data.sec.gov/submissions/CIK0001652044.json"),
    ("SEC_NVDA","Semiconductors Supply","https://data.sec.gov/submissions/CIK0001045810.json"),
    ("SEC_ORCL","Neoclouds","https://data.sec.gov/submissions/CIK0001341439.json"),
    ("EIA_METADATA","Power/Data Centers","https://api.eia.gov/v2/"),
]
NODES=("Private Credit","Insurers","UST 30Y","Neoclouds","AI Equities",
       "Hyperscalers","SPV","Repo","Power/Data Centers",
       "Semiconductors Supply","AI Demand")
WEIGHTS=(150,125,125,100,100,100,100,100,50,50,50)
assert len(NODES)==11 and sum(WEIGHTS)==1050

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    ua=os.environ.get("AICS_SEC_USER_AGENT","").strip()
    records=[]
    for source,node,url in SOURCES:
        item={"source_id":source,"candidate_node":node,"url":url,
              "retrieved_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
              "status":"not_retrieved","pit_verified":False,"score_eligible":False}
        if source.startswith("SEC_") and not ua:
            item["status"]="blocked_missing_sec_user_agent"
            records.append(item)
            continue
        try:
            req=Request(url,headers={"User-Agent":ua if source.startswith("SEC_") else "AICS research evidence collector",
                                    "Accept":"application/json"})
            with urlopen(req,timeout=35) as response:
                raw=response.read(12_000_001)
                if len(raw)>12_000_000:raise ValueError("response_too_large")
                data=json.loads(raw)
                if not isinstance(data,dict):raise ValueError("invalid_json_structure")
            filename=OUT/(source.lower()+".json")
            filename.write_bytes(raw)
            item.update(status="downloaded_unverified",sha256=hashlib.sha256(raw).hexdigest(),
                        bytes=len(raw),local_path=str(filename))
        except Exception as e:
            item.update(status="fetch_error",error=type(e).__name__)
        records.append(item)
    report={"retrieved_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "node_weights":dict(zip(NODES,WEIGHTS)),"sources":records,
            "downloaded_sources":sum(r["status"]=="downloaded_unverified" for r in records),
            "independently_verified_node_scores":0,"index_aics":None,"model_score":None,
            "promotion":"BLOCKED","trades_created":False,
            "limitations":["SEC submissions are filings metadata, not calibrated node values",
                           "EIA endpoint response is API metadata, not a power demand time series",
                           "SEC filings require available_at = filed_at + 14 calendar days",
                           "No historical source is promoted without source-level PIT validation"]}
    (OUT/"manifest.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"downloaded_sources":report["downloaded_sources"],
                      "attempted_sources":len(records),"index_aics":None}))
    return report["downloaded_sources"]>0

if __name__=="__main__":
    raise SystemExit(0 if run() else 2)
