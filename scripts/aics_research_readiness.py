#!/usr/bin/env python3
"""Research readiness report: no fabricated node scores or model performance."""
import datetime as dt
import json
from pathlib import Path

ROOT=Path("aics_data")
def read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
live=read(ROOT/"live"/"manifest.json")
live_quality=read(ROOT/"live"/"quality_report.json")
xbrl=read(ROOT/"xbrl"/"manifest.json")
xbrl_quality=read(ROOT/"xbrl"/"quality_report.json")
coverage=read(ROOT/"research"/"node_coverage.json")
pit=read(ROOT/"pit"/"manifest.json")
pit_quality=read(ROOT/"pit"/"quality_report.json")
checks=[
    {"name":"evidence_manifest_present","passed":bool(live.get("results"))},
    {"name":"evidence_quality_passed","passed":bool(live_quality.get("gates")) and
     live_quality.get("passed")==live_quality.get("total")},
    {"name":"xbrl_manifest_present","passed":bool(xbrl.get("results"))},
    {"name":"xbrl_quality_passed","passed":xbrl_quality.get("passed") is True},
    {"name":"fixed_node_weights","passed":coverage.get("fixed_weight_sum")==1050 and
     len(coverage.get("nodes",[]))==11},
    {"name":"alfred_historical_snapshots_complete","passed":len(pit.get("results",[]))==4 and
     all(r.get("complete") is True for r in pit.get("results",[]))},
    {"name":"alfred_asof_structural_validation","passed":pit_quality.get("structurally_valid") is True},
    {"name":"all_nodes_pit_validated","passed":coverage.get("validated_nodes")==11},
    {"name":"chronological_24m_oos_validated","passed":False},
    {"name":"committee_approval_recorded","passed":False},
]
report={"as_of":dt.datetime.now(dt.timezone.utc).isoformat(),
        "checks":checks,"ready_for_production":False,
        "blocking_checks":[c["name"] for c in checks if not c["passed"]],
        "index_aics":None,"model_score":None,"promotion":"BLOCKED",
        "production_weights_changed":False,"verdict_mutated":False,
        "trades_created":False}
out=ROOT/"research"
out.mkdir(parents=True,exist_ok=True)
(out/"readiness_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"ready_for_production":False,
                  "blocking_checks":report["blocking_checks"]},indent=2))
