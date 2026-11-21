#!/usr/bin/env python3
"""Ten evidence-quality gates; diagnostics only, never produces an AICS score."""
import csv
import datetime as dt
import hashlib
import json
import math
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
try:
    utc_day = dt.date.fromisoformat(manifest["as_of"])
    fred_day = dt.date.fromisoformat(manifest["fred_realtime_as_of"])
    fred_clock_consistent = dt.timedelta(days=0) <= (utc_day-fred_day) <= dt.timedelta(days=1)
except (ValueError, KeyError, TypeError):
    fred_clock_consistent = False
check("02b_fred_calendar_day_not_future", fred_clock_consistent)
results = manifest.get("results", [])
by_id = {r.get("id"): r for r in results}
check("01_manifest_exists", manifest_path.exists())
check("02_as_of_date", bool(manifest.get("as_of")) and
      dt.date.fromisoformat(manifest["as_of"]) <= dt.date.today() if manifest.get("as_of") else False)
check("03_expected_sources", len(results)==len(EXPECTED) and set(by_id) == EXPECTED,
      {"missing":sorted(EXPECTED-set(by_id)),"duplicates":len(results)-len(by_id)})
check("04_source_downloads", len(results)==10 and all(r.get("status")=="downloaded_unverified" for r in results),
      [r.get("id") for r in results if r.get("status")!="downloaded_unverified"])
check("05_no_production_index", manifest.get("index_aics") is None and
      manifest.get("predictive_model_score") is None and manifest.get("publishable") is False)
check("06_source_classification", all(by_id.get(sid,{}).get("source")=="FRED_CURRENT_VINTAGE"
      for sid in ("BAMLH0A0HYM2","BAMLH0A3HYC","SOFR")) and
      by_id.get("DGS30",{}).get("source")=="ALFRED")
csv_counts = {}
vintage_valid = True
observation_duplicates = {}
observation_order_valid = True
numeric_valid = True
snapshot_cutoff_valid = True
manifest_counts_valid = True
vintage_rows_present = True
for sid in ("BAMLH0A0HYM2","BAMLH0A3HYC","DGS30","SOFR"):
    name = f"alfred_{sid}.csv" if sid=="DGS30" else f"fred_current_{sid}.csv"
    path = ROOT / name
    if not path.exists():
        vintage_valid=False
        continue
    with path.open(newline="",encoding="utf-8") as handle:
        rows=list(csv.DictReader(handle))
    csv_counts[sid]=len(rows)
    if by_id.get(sid,{}).get("rows") != len(rows):
        manifest_counts_valid=False
    if not rows:
        vintage_rows_present=False
    seen = set()
    duplicate_count = 0
    for row in rows:
        try:
            key = (row["series_id"], row["date"], row["realtime_start"], row["realtime_end"])
            if key in seen:
                duplicate_count += 1
            seen.add(key)
            if (dt.date.fromisoformat(row["date"]) >
                dt.date.fromisoformat(row["realtime_end"])):
                observation_order_valid = False
            value = float(row["value"])
            if not math.isfinite(value):
                numeric_valid = False
            if sid != "DGS30" and row["realtime_start"] != manifest.get("fred_realtime_as_of"):
                snapshot_cutoff_valid = False
            if (row["series_id"] != sid or row["verified_pit"] != "False" or
                dt.date.fromisoformat(row["realtime_start"]) >
                dt.date.fromisoformat(row["realtime_end"])):
                vintage_valid=False
                break
        except (KeyError,ValueError,OverflowError):
            vintage_valid=False
            break
    observation_duplicates[sid] = duplicate_count
check("07_observation_lineage", vintage_valid and len(csv_counts)==4, csv_counts)
sec_valid=True
sec_counts={}
sec_duplicates={}
sec_manifest_match=True
sec_cik_valid=True
sec_period_valid=True
sec_accession_shape=True
for ticker in ("NVDA","MSFT","AMZN","GOOGL","META","ORCL"):
    path=ROOT / f"sec_eligible_filings_{ticker}.json"
    if not path.exists():
        sec_valid=False
        continue
    filings=json.loads(path.read_text(encoding="utf-8"))
    sec_counts[ticker]=len(filings)
    if by_id.get(ticker,{}).get("eligible_filings") != len(filings):
        sec_manifest_match=False
    seen_accessions=set()
    sec_duplicates[ticker]=0
    for filing in filings:
        if filing.get("accession_number") in seen_accessions:
            sec_duplicates[ticker]+=1
        seen_accessions.add(filing.get("accession_number"))
        try:
            if filing["cik"] != {"NVDA":"0001045810","MSFT":"0000789019",
                "AMZN":"0001018724","GOOGL":"0001652044",
                "META":"0001326801","ORCL":"0001341439"}[ticker]:
                sec_cik_valid=False
            if not filing["accession_number"].count("-") == 2:
                sec_accession_shape=False
            filed=dt.date.fromisoformat(filing["filed_at"])
            available=dt.date.fromisoformat(filing["available_at"])
            if filing.get("period_end") and dt.date.fromisoformat(filing["period_end"]) > filed:
                sec_period_valid=False
            if (available != filed+dt.timedelta(days=14) or available >
                dt.date.fromisoformat(manifest["as_of"]) or
                filing["ticker"]!=ticker or filing["form"] not in ("10-K","10-Q","8-K")
                or not filing["cik"] or not filing["accession_number"]):
                sec_valid=False
                break
        except (KeyError,ValueError):
            sec_valid=False
            break
check("07d_manifest_observation_counts", manifest_counts_valid, csv_counts)
check("07e_numeric_finite", numeric_valid)
check("07f_nonempty_sources", vintage_rows_present)
check("07g_current_snapshot_cutoff", snapshot_cutoff_valid)
check("07b_no_duplicate_observations", len(observation_duplicates)==4 and
      all(n==0 for n in observation_duplicates.values()), observation_duplicates)
check("07c_observation_dates", observation_order_valid)
check("08_sec_14_day_embargo", sec_valid and len(sec_counts)==6, sec_counts)
check("08b_sec_manifest_counts", sec_manifest_match, sec_counts)
check("08c_sec_accession_uniqueness", len(sec_duplicates)==6 and
      all(v==0 for v in sec_duplicates.values()), sec_duplicates)
check("08d_sec_cik_mapping", sec_cik_valid)
check("08e_sec_period_end_not_future", sec_period_valid)
check("08f_sec_accession_format", sec_accession_shape)
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
