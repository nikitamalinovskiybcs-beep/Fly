#!/usr/bin/env python3
"""Ten evidence-quality gates; diagnostics only, never produces an AICS score."""
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path("aics_data/live")
EXPECTED = {"BAMLH0A0HYM2", "BAMLH0A3HYC", "DGS30", "SOFR",
            "NVDA", "MSFT", "AMZN", "GOOGL", "META", "ORCL"}
checks = []
def check(name, passed, detail="", blocking=True):
    checks.append({"gate":name,"passed":bool(passed),"detail":str(detail),
                   "blocking":blocking})
manifest_path = ROOT / "manifest.json"
manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
results = manifest.get("results", [])
by_id = {r.get("id"): r for r in results}
check("01_manifest_exists", manifest_path.exists())
check("02_as_of_date", bool(manifest.get("as_of")) and
      dt.date.fromisoformat(manifest["as_of"]) <= dt.date.today() if manifest.get("as_of") else False)
check("03_expected_sources", set(by_id) == EXPECTED, sorted(set(EXPECTED)-set(by_id)))
check("04_source_downloads", len(results)==10 and all(r.get("status")=="downloaded_unverified" for r in results),
      [r.get("id") for r in results if r.get("status")!="downloaded_unverified"])
check("05_no_production_index", manifest.get("index_aics") is None and
      manifest.get("predictive_model_score") is None and manifest.get("publishable") is False)
check("06_source_classification", all(by_id.get(sid,{}).get("source")=="FRED_CURRENT_VINTAGE"
      for sid in ("BAMLH0A0HYM2","BAMLH0A3HYC","SOFR")) and
      by_id.get("DGS30",{}).get("source")=="ALFRED")
csv_counts = {}
vintage_valid = True
for sid in ("BAMLH0A0HYM2","BAMLH0A3HYC","DGS30","SOFR"):
    name = f"alfred_{sid}.csv" if sid=="DGS30" else f"fred_current_{sid}.csv"
    path = ROOT / name
    if not path.exists():
        vintage_valid=False
        continue
    with path.open(newline="",encoding="utf-8") as handle:
        rows=list(csv.DictReader(handle))
    csv_counts[sid]=len(rows)
    for row in rows:
        try:
            if (row["series_id"] != sid or row["verified_pit"] != "False" or
                dt.date.fromisoformat(row["realtime_start"]) >
                dt.date.fromisoformat(row["realtime_end"])):
                vintage_valid=False
                break
        except (KeyError,ValueError):
            vintage_valid=False
            break
check("07_observation_lineage", vintage_valid and len(csv_counts)==4, csv_counts)
sec_valid=True
sec_counts={}
for ticker in ("NVDA","MSFT","AMZN","GOOGL","META","ORCL"):
    path=ROOT / f"sec_eligible_filings_{ticker}.json"
    if not path.exists():
        sec_valid=False
        continue
    filings=json.loads(path.read_text(encoding="utf-8"))
    sec_counts[ticker]=len(filings)
    for filing in filings:
        try:
            filed=dt.date.fromisoformat(filing["filed_at"])
            available=dt.date.fromisoformat(filing["available_at"])
            if (available != filed+dt.timedelta(days=14) or available >
                dt.date.fromisoformat(manifest["as_of"]) or
                filing["ticker"]!=ticker or filing["form"] not in ("10-K","10-Q","8-K")
                or not filing["cik"] or not filing["accession_number"]):
                sec_valid=False
                break
        except (KeyError,ValueError):
            sec_valid=False
            break
check("08_sec_14_day_embargo", sec_valid and len(sec_counts)==6, sec_counts)
check("09_no_claimed_xbrl_facts", all(r.get("xbrl_facts_extracted") is False
      for r in results if r.get("source")=="SEC"))
check("10_pit_promotion_blocked", all(r.get("historical_pit_available") is False
      for r in results if r.get("source")=="FRED_CURRENT_VINTAGE") and
      manifest.get("publishable") is False)
digests={}
for path in sorted(ROOT.glob("*")):
    if path.is_file() and path.name not in ("quality_report.json",):
        digests[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
report={"as_of":manifest.get("as_of"),"gates":checks,
        "passed":sum(c["passed"] for c in checks),
        "total":len(checks),"evidence_sha256":digests,
        "index_aics":None,"model_score":None,"promotion":"BLOCKED",
        "production_weights_changed":False,"verdict_mutated":False,
        "trades_created":False}
ROOT.mkdir(parents=True,exist_ok=True)
(ROOT/"quality_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"passed":report["passed"],"total":report["total"],
                  "failed_gates":[c["gate"] for c in checks if not c["passed"]]},indent=2))
if not all(c["passed"] for c in checks):
    raise SystemExit("AICS evidence quality gates failed; inspect quality_report.json")
