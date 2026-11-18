#!/usr/bin/env python3
"""Summarize actual historical PIT coverage without inferring missing values."""
import datetime as dt
import json
from pathlib import Path

ROOT=Path("aics_data/pit")
path=ROOT/"manifest.json"
manifest=json.loads(path.read_text()) if path.exists() else {}
quality_path=ROOT/"quality_report.json"
quality=json.loads(quality_path.read_text()) if quality_path.exists() else {}
required=("DGS30","SOFR","BAMLH0A0HYM2","BAMLH0A3HYC")
by_id={r.get("series_id"):r for r in manifest.get("results",[])}
series=[]
for sid in required:
    item=by_id.get(sid,{})
    snapshots=item.get("snapshots",[])
    good=[s for s in snapshots if s.get("status")=="downloaded_unverified"]
    failures=[{"as_of":s.get("as_of"),"status":s.get("status"),
               "http_status":s.get("http_status"),"error":s.get("error")}
              for s in snapshots if s.get("status")!="downloaded_unverified"]
    status_counts={status:sum(s.get("status")==status for s in snapshots) for status in sorted({s.get("status") for s in snapshots})}
    series.append({"series_id":sid,"status_counts":status_counts,"snapshots_requested":24,
                   "snapshots_downloaded_unverified":len(good),
                   "observations_downloaded":item.get("rows",0),
                   "missing_snapshots":failures,
                   "structurally_valid":bool(quality.get("structurally_valid")) and
                   item.get("complete") is True,
                   "independently_verified_pit":False})
report={"as_of":manifest.get("as_of"),"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "series":series,"historical_snapshot_coverage_complete":all(
          s["snapshots_downloaded_unverified"]==24 and s["structurally_valid"] for s in series),
        "independently_verified_pit":False,"index_aics":None,
        "model_score":None,"promotion":"BLOCKED","trades_created":False}
ROOT.mkdir(parents=True,exist_ok=True)
(ROOT/"coverage_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"series":[{"id":s["series_id"],
                              "downloaded":s["snapshots_downloaded_unverified"],
                              "requested":24} for s in series],
                  "promotion":"BLOCKED"},indent=2))
