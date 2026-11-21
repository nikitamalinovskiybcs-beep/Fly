#!/usr/bin/env python3
"""Ten-stage AICS audit receipt; no fabricated data or publication."""
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path("aics_data")
def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return {}
live = load(ROOT/"live"/"manifest.json")
lq = load(ROOT/"live"/"quality_report.json")
xbrl = load(ROOT/"xbrl"/"manifest.json")
xq = load(ROOT/"xbrl"/"quality_report.json")
coverage = load(ROOT/"research"/"node_coverage.json")
readiness = load(ROOT/"research"/"readiness_report.json")
def status(condition):
    return "PASS" if condition else "BLOCKED"
stages = [
    ("01_source_manifest", bool(live.get("results"))),
    ("02_macro_sec_download", len(live.get("results", [])) == 10 and
     all(r.get("status") == "downloaded_unverified" for r in live.get("results", []))),
    ("03_macro_sec_lineage", bool(lq.get("gates")) and lq.get("passed") == lq.get("total")),
    ("04_sec_14_day_embargo", any(g.get("gate")=="08_sec_14_day_embargo" and g.get("passed")
                              for g in lq.get("gates", []))),
    ("05_xbrl_manifest", len(xbrl.get("results", [])) == 6),
    ("06_xbrl_source_download", len(xbrl.get("results", [])) == 6 and
     all(r.get("status")=="downloaded_unverified" for r in xbrl.get("results", []))),
    ("07_xbrl_lineage", xq.get("passed") is True),
    ("08_fixed_11_node_weights", coverage.get("fixed_weight_sum")==1050 and
     len(coverage.get("nodes",[]))==11),
    ("09_validated_pit_11_nodes", coverage.get("validated_nodes")==11),
    ("10_oos_and_committee_approval", readiness.get("ready_for_production") is True and
     not readiness.get("blocking_checks")),
]
source_files = sorted(p for sub in ("live","xbrl","research")
                      for p in (ROOT/sub).glob("*") if p.is_file()
                      and p.name != "ten_stage_receipt.json")
digests = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in source_files}
report = {
    "created_at":dt.datetime.now(dt.timezone.utc).isoformat(),
    "stages":[{"stage":name,"status":status(ok)} for name,ok in stages],
    "passed":sum(ok for _,ok in stages),"total":10,
    "ready_for_production":False,"index_aics":None,"model_score":None,
    "promotion":"BLOCKED","trades_created":False,
    "production_weights_changed":False,"verdict_mutated":False,
    "file_sha256":digests,
}
out = ROOT/"research"/"ten_stage_receipt.json"
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"passed":report["passed"],"total":10,
                  "blocked":[name for name,ok in stages if not ok],
                  "ready_for_production":False},indent=2))
