#!/usr/bin/env python3
"""Audit 11 fixed AICS nodes; source downloads are not validated node scores."""
import datetime as dt
import json
from pathlib import Path

ROOT = Path("aics_data")
WEIGHTS = {
    "Private Credit":150, "Insurers":125, "UST 30Y":125,
    "Neoclouds":100, "AI Equities":100, "Hyperscalers":100,
    "SPV":100, "Repo":100, "Power/Data Centers":50,
    "Semiconductors Supply":50, "AI Demand":50,
}
assert len(WEIGHTS) == 11 and sum(WEIGHTS.values()) == 1050
live_path = ROOT/"live"/"manifest.json"
xbrl_path = ROOT/"xbrl"/"manifest.json"
live = json.loads(live_path.read_text()) if live_path.exists() else {}
xbrl = json.loads(xbrl_path.read_text()) if xbrl_path.exists() else {}
sources = {r.get("id"):r for r in live.get("results",[])}
xbrl_sources = {r.get("ticker"):r for r in xbrl.get("results",[])}
mapping = {
    "Private Credit":["BAMLH0A3HYC"],
    "UST 30Y":["DGS30"],
    "Neoclouds":["BAMLH0A0HYM2"],
    "Repo":["SOFR"],
    "Hyperscalers":["MSFT","AMZN","GOOGL","META","ORCL"],
    "Semiconductors Supply":["NVDA"],
}
nodes = []
for node, weight in WEIGHTS.items():
    ids = mapping.get(node, [])
    downloaded = [sid for sid in ids if sources.get(sid,{}).get("status")=="downloaded_unverified"]
    # The candidate mapping is a research hypothesis, not evidence of node coverage.
    nodes.append({"node":node,"weight":weight,"candidate_source_ids":ids,
                  "downloaded_candidate_ids":downloaded,
                  "validated_node_score":None,"validated_pit_coverage":False,
                  "proxy_mapping_approved":False})
report = {"as_of":dt.datetime.now(dt.timezone.utc).isoformat(),
          "fixed_weight_sum":sum(WEIGHTS.values()),"nodes":nodes,
          "downloaded_candidate_sources":sum(len(n["downloaded_candidate_ids"]) for n in nodes),
          "xbrl_companyfacts_downloaded":sum(r.get("status")=="downloaded_unverified"
                                            for r in xbrl_sources.values()),
          "validated_nodes":0,"index_aics":None,"model_score":None,
          "promotion":"BLOCKED","production_weights_changed":False,
          "verdict_mutated":False,"trades_created":False,
          "blockers":["No independently validated PIT mapping and node scores",
                      "FRED current-only snapshots cannot be used for historical backtests",
                      "11-node coverage and 24-month chronological OOS are unproven"]}
out = ROOT/"research"
out.mkdir(parents=True,exist_ok=True)
(out/"node_coverage.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"nodes":len(nodes),"validated_nodes":0,"weight_sum":1050,
                  "index_aics":None},indent=2))
