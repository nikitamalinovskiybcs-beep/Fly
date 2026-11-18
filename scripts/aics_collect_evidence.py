#!/usr/bin/env python3
"""Evidence-only AICS data collection; never publishes an index score."""
import csv
import datetime as dt
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OUT = Path("aics_data/live")
OUT.mkdir(parents=True, exist_ok=True)
TODAY = dt.date.today()
SERIES = {
    "BAMLH0A0HYM2": "neoclouds_proxy",
    "BAMLH0A3HYC": "private_credit_proxy",
    "DGS30": "ust_30y_proxy",
    "SOFR": "repo_proxy",
}
CIKS = {"NVDA": "0001045810", "MSFT": "0000789019", "AMZN": "0001018724",
        "GOOGL": "0001652044", "META": "0001326801", "ORCL": "0001341439"}
results = []
def get(url, headers=None):
    req = Request(url, headers=headers or {"User-Agent": "AICS research evidence collector"})
    with urlopen(req, timeout=35) as response:
        return json.load(response)
def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
key = os.getenv("FRED_API_KEY", "")
for sid, node in SERIES.items():
    if not key:
        results.append({"source":"ALFRED","id":sid,"status":"missing_secret"})
        continue
    try:
        params = urlencode({"series_id":sid,"api_key":key,"file_type":"json",
                            "realtime_start":"1776-07-04","realtime_end":TODAY.isoformat(),
                            "observation_start":"2010-01-01"})
        data = get("https://api.stlouisfed.org/fred/series/observations?"+params)
        rows = []
        for o in data.get("observations", []):
            if o.get("value") in ("", "."): continue
            rows.append({"node":node,"series_id":sid,"date":o["date"],
                         "realtime_start":o["realtime_start"],
                         "realtime_end":o["realtime_end"],"value":o["value"],
                         "source":"ALFRED","verified_pit":False})
        path = OUT / f"alfred_{sid}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["node","series_id","date","realtime_start",
                      "realtime_end","value","source","verified_pit"])
            writer.writeheader(); writer.writerows(rows)
        results.append({"source":"ALFRED","id":sid,"status":"downloaded_unverified",
                        "rows":len(rows)})
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as e:
        results.append({"source":"ALFRED","id":sid,"status":"error",
                        "error":type(e).__name__})
identity = os.getenv("EDGAR_IDENTITY", "").strip()
for ticker, cik in CIKS.items():
    if not identity:
        results.append({"source":"SEC","id":ticker,"status":"missing_secret"})
        continue
    try:
        headers={"User-Agent":identity,"Accept":"application/json"}
        data=get(f"https://data.sec.gov/submissions/CIK{cik}.json",headers)
        write_json(OUT / f"sec_submissions_{ticker}.json",data)
        recent=data.get("filings",{}).get("recent",{})
        eligible=0
        for form,filed in zip(recent.get("form",[]),recent.get("filingDate",[])):
            if form not in ("10-K","10-Q","8-K"):continue
            if dt.date.fromisoformat(filed)+dt.timedelta(days=14)<=TODAY:eligible+=1
        results.append({"source":"SEC","id":ticker,"status":"downloaded_unverified",
                        "eligible_filings":eligible,"rule":"filed_at+14_calendar_days"})
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as e:
        results.append({"source":"SEC","id":ticker,"status":"error",
                        "error":type(e).__name__})
failed = sum(r["status"] != "downloaded_unverified" for r in results)
write_json(OUT / "manifest.json",{"as_of":TODAY.isoformat(),"results":results,
    "failed_sources":failed,
    "index_aics":None,"predictive_model_score":None,"publishable":False,
    "note":"Raw downloads are not independently verified PIT data. Do not score."})
print(json.dumps({"as_of":TODAY.isoformat(),"results":results},indent=2))
\nif failed:\n    raise SystemExit(f"AICS incomplete: {failed} source(s) failed; see artifact manifest")\n