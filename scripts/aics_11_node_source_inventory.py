#!/usr/bin/env python3
"""Build honest 11-node source inventory. Never invent values or promote proxies."""
import argparse
import csv
import json
from pathlib import Path

NODES=[
 ("Private Credit",150,"BAMLH0A0HYM2;BAMLH0A3HYC","indirect public credit proxies; not private credit specific"),
 ("Insurers",125,"","requires PIT insurer holdings and exposure filings"),
 ("UST 30Y",125,"DGS30","30-year Treasury yield; score calibration pending"),
 ("Neoclouds",100,"","one original-package proxy requires independently verified lineage"),
 ("AI Equities",100,"","requires fixed PIT equity universe and historical price observations"),
 ("Hyperscalers",100,"","requires SEC filings with 14-day publication lag"),
 ("SPV",100,"","requires primary SPV funding/deal disclosures"),
 ("Repo",100,"SOFR","SOFR alone does not establish repo stress"),
 ("Power/Data Centers",50,"","requires dated capacity, grid, and funding evidence"),
 ("Semiconductors Supply",50,"","requires dated supply/lead-time disclosures"),
 ("AI Demand",50,"","requires dated customer demand and contract evidence"),
]
assert len(NODES)==11 and sum(n[1] for n in NODES)==1050

def build(path):
    records=[]
    for name,weight,series,note in NODES:
        records.append({"node":name,"weight":weight,"source_series_candidates":series,
          "candidate_source_count":len(series.split(";")) if series else 0,
          "independently_verified_pit":False,"node_score_0_100":None,
          "source_evidence_status":"CANDIDATE_NOT_CERTIFIED" if series else "MISSING",
          "evidence_gap":note})
    return {"node_count":11,"total_weight":1050,"source_inventory":records,
            "nodes_with_source_candidates":sum(bool(r["source_series_candidates"]) for r in records),
            "independently_verified_nodes":0,"index_aics":None,"model_score":None,
            "promotion":"BLOCKED","trades_created":False,
            "note":"Candidate series names are a mapping, not observations; never backfill absent nodes."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="aics_data/pit/eleven_node_source_inventory.json")
    args=p.parse_args()
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    report=build(None)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"nodes":11,"source_candidate_nodes":report["nodes_with_source_candidates"],
                      "certified_nodes":0,"index_aics":None}))
if __name__=="__main__":
    main()
