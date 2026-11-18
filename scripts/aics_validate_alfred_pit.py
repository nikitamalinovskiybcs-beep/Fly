#!/usr/bin/env python3
"""Independent structural checks of ALFRED as-of snapshots; no PIT promotion."""
import csv
import datetime as dt
import hashlib
import json
import math
import calendar
from pathlib import Path

ROOT=Path("aics_data/pit")
SERIES=("DGS30","SOFR","BAMLH0A0HYM2","BAMLH0A3HYC")
manifest_path=ROOT/"manifest.json"
manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
by_id={r.get("series_id"):r for r in manifest.get("results",[])}
errors=[]
counts={}
def completed_month_ends(today):
    first = today.year*12 + today.month - 2
    months = range(first-23,first+1)
    return {dt.date(n//12,n%12+1,calendar.monthrange(n//12,n%12+1)[1]).isoformat()
            for n in months}
try:
    audit_date=dt.date.fromisoformat(manifest["as_of"])
    if audit_date>dt.date.today():
        errors.append("future_manifest_as_of")
except (KeyError,ValueError,TypeError):
    errors.append("invalid_manifest_as_of")
    audit_date=dt.date.today()
expected_dates=completed_month_ends(audit_date)
if len(manifest.get("results",[]))!=4 or set(by_id)!=set(SERIES):
    errors.append("missing_or_duplicate_series")
if manifest.get("source") != "ALFRED historical as-of snapshots":
    errors.append("unexpected_source_classification")
if manifest.get("verified_pit") is not False or manifest.get("publishable") is not False:
    errors.append("unsafe_promotion_flags")
if manifest.get("index_aics") is not None or manifest.get("model_score") is not None:
    errors.append("unexpected_score")
for sid in SERIES:
    path=ROOT/f"alfred_asof_{sid}.csv"
    if not path.exists():
        errors.append(f"{sid}:missing_csv")
        continue
    try:
        with path.open(newline="",encoding="utf-8") as handle:
            rows=list(csv.DictReader(handle))
        item=by_id.get(sid,{})
        if item.get("query_mode")!="realtime_start=realtime_end=as_of":
            errors.append(f"{sid}:unexpected_query_mode")
        if item.get("source_endpoint")!="https://api.stlouisfed.org/fred/series/observations":
            errors.append(f"{sid}:unexpected_source_endpoint")
        if item.get("rows")!=len(rows):
            errors.append(f"{sid}:row_count_mismatch")
        if item.get("sha256")!=hashlib.sha256(path.read_bytes()).hexdigest():
            errors.append(f"{sid}:sha256_mismatch")
        snapshots=item.get("snapshots",[])
        if len(snapshots)!=24 or {s.get("as_of") for s in snapshots}!=expected_dates:
            errors.append(f"{sid}:snapshot_dates_incomplete")
        if item.get("complete") is not True:
            errors.append(f"{sid}:manifest_incomplete")
        if any(s.get("status")!="downloaded_unverified" for s in snapshots):
            errors.append(f"{sid}:missing_historical_vintage")
        expected={s["as_of"]:s.get("rows") for s in snapshots if s.get("status")=="downloaded_unverified"}
        actual={}
        seen=set()
        for row in rows:
            asof=dt.date.fromisoformat(row["as_of"])
            observed=dt.date.fromisoformat(row["observation_date"])
            start=dt.date.fromisoformat(row["realtime_start"])
            end=dt.date.fromisoformat(row["realtime_end"])
            value=float(row["value"])
            key=(row["as_of"],row["observation_date"])
            if key in seen:
                errors.append(f"{sid}:duplicate_observation")
                break
            seen.add(key)
            if (row["as_of"] not in expected_dates or row["series_id"]!=sid or row["source"]!="ALFRED_AS_OF"
                or row["verified_pit"]!="False" or observed>asof
                or not start<=asof<=end or not math.isfinite(value)):
                errors.append(f"{sid}:invalid_asof_lineage")
                break
            actual[row["as_of"]]=actual.get(row["as_of"],0)+1
        if actual!=expected:
            errors.append(f"{sid}:snapshot_row_count_mismatch")
        counts[sid]=len(rows)
    except (KeyError,ValueError,TypeError,OverflowError) as exc:
        errors.append(f"{sid}:{type(exc).__name__}")
report={"as_of":manifest.get("as_of"),"source":"ALFRED_AS_OF",
        "structurally_valid":not errors,"errors":errors,"rows":counts,
        "independently_verified_pit":False,
        "index_aics":None,"model_score":None,"promotion":"BLOCKED",
        "trades_created":False}
ROOT.mkdir(parents=True,exist_ok=True)
(ROOT/"quality_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"structurally_valid":not errors,"errors":errors,"rows":counts},indent=2))
if errors:
    raise SystemExit("ALFRED PIT snapshot quality gates failed")
