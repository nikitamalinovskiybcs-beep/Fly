#!/usr/bin/env python3
"""Minimal executable AICS research model; never executes trades.

Input JSON: {"as_of":"YYYY-MM-DD","nodes":{...}} using
scripts/aics_score_reproducibility_gate.py schema. An index is computed only
when all 11 node scores have independently verified PIT evidence.
"""
import argparse
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("aics_score_gate",HERE/"aics_score_reproducibility_gate.py")
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

def model(data):
    result=gate.evaluate(data)
    index=result["index_aics"]
    if index is None:
        signal="INSUFFICIENT_VERIFIED_DATA"
        band=None
    elif index<450:
        signal="ENTRY_ZONE_RESEARCH_ONLY"
        band="BELOW_450"
    elif index<=500:
        signal="WATCH_RESEARCH_ONLY"
        band="450_TO_500"
    else:
        signal="CASH_EXIT_ZONE_RESEARCH_ONLY"
        band="ABOVE_500"
    return {
        "as_of":result["as_of"],
        "index_aics":index,
        "signal":signal,
        "band":band,
        "hot_nodes":result["hot_nodes"],
        "multiplier":result["multiplier"],
        "node_coverage":result["node_coverage"],
        "required_nodes":11,
        "validated_weight":result["validated_weight"],
        "required_weight":1050,
        "errors":result["errors"],
        "model_accuracy":None,
        "out_of_sample_validated":False,
        "committee_approved":False,
        "promotion":"BLOCKED",
        "trades_created":False,
        "disclaimer":"Research-only arithmetic candidate; never a trading authorization."
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",required=True,help="Real 11-node PIT-evidence JSON")
    p.add_argument("--output",default="-",help="Output report JSON or '-'")
    a=p.parse_args()
    report=model(json.loads(Path(a.input).read_text(encoding="utf-8")))
    payload=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    if a.output=="-":print(payload,end="")
    else:
        target=Path(a.output)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(payload,encoding="utf-8")
    return 0 if report["index_aics"] is not None else 2

if __name__=="__main__":
    raise SystemExit(main())
