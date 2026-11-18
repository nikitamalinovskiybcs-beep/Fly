#!/usr/bin/env python3
"""AICS score reproducibility gate: refuse to certify untraceable 646.3/650.7 claims.

No data fabrication, interpolation, or unverified PIT promotion. Input is an
explicit JSON object with as_of, and 11 per-node score records.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

WEIGHTS = {"Private Credit":150,"Insurers":125,"UST 30Y":125,
           "Neoclouds":100,"AI Equities":100,"Hyperscalers":100,
           "SPV":100,"Repo":100,"Power/Data Centers":50,
           "Semiconductors Supply":50,"AI Demand":50}
assert sum(WEIGHTS.values()) == 1050

def evaluate(data):
    errors=[]
    as_of=data.get("as_of")
    try:
        cutoff=dt.date.fromisoformat(as_of)
    except (TypeError,ValueError):
        cutoff=None
        errors.append("invalid_as_of")
    nodes=data.get("nodes")
    if not isinstance(nodes,dict):
        nodes={}
        errors.append("nodes_missing")
    extra=set(nodes)-set(WEIGHTS)
    if extra:
        errors.append("unknown_nodes:"+",".join(sorted(extra)))
    validated={}
    for name,weight in WEIGHTS.items():
        row=nodes.get(name)
        if not isinstance(row,dict):
            errors.append("missing_node:"+name)
            continue
        score=row.get("score")
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score) or not 0<=score<=100:
            errors.append("invalid_score:"+name)
            continue
        evidence=row.get("evidence")
        if not isinstance(evidence,dict) or not evidence.get("source_uri") or not evidence.get("source_sha256"):
            errors.append("missing_source_evidence:"+name)
            continue
        try:
            available=dt.date.fromisoformat(evidence["available_at"])
            filed=dt.date.fromisoformat(evidence["filed_at"]) if evidence.get("source_type")=="SEC" else None
        except (KeyError,ValueError,TypeError):
            errors.append("invalid_evidence_dates:"+name)
            continue
        if cutoff is None or available>cutoff:
            errors.append("future_unavailable:"+name)
            continue
        if filed is not None and available < filed+dt.timedelta(days=14):
            errors.append("sec_embargo_violation:"+name)
            continue
        if evidence.get("independently_verified_pit") is not True:
            errors.append("unverified_pit:"+name)
            continue
        if not evidence.get("score_method_version") or not evidence.get("training_cutoff"):
            errors.append("missing_score_lineage:"+name)
            continue
        try:
            training_cutoff=dt.date.fromisoformat(evidence["training_cutoff"])
        except (TypeError,ValueError):
            errors.append("invalid_training_cutoff:"+name)
            continue
        if cutoff is None or training_cutoff>cutoff:
            errors.append("training_lookahead:"+name)
            continue
        validated[name]={"score":score,"weight":weight}
    ready=len(validated)==len(WEIGHTS) and not errors
    if ready:
        hot=sum(v["score"]>60 for v in validated.values())
        multiplier=min(1.35,max(1,1+0.20*min(max(hot-2,0),1)+0.05*max(hot-3,0)))
        raw=sum(v["weight"]*v["score"]/100 for v in validated.values())
        index=raw*multiplier
    else:
        hot=multiplier=raw=index=None
    return {"as_of":as_of,"node_coverage":len(validated),"required_nodes":11,
            "validated_weight":sum(v["weight"] for v in validated.values()),
            "required_weight":1050,"errors":errors,
            "hot_nodes":hot,"multiplier":multiplier,"raw_score":raw,
            "index_aics":index,"model_score":None,
            "promotion":"BLOCKED","trades_created":False,
            "note":"Index value is a reproducibility candidate only; OOS and committee approval are separate gates."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("input_json")
    p.add_argument("--output",default="-")
    a=p.parse_args()
    result=evaluate(json.loads(Path(a.input_json).read_text(encoding="utf-8")))
    output=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if a.output=="-": print(output,end="")
    else: Path(a.output).write_text(output,encoding="utf-8")
    return 0 if result["index_aics"] is not None else 2

if __name__=="__main__":
    raise SystemExit(main())
