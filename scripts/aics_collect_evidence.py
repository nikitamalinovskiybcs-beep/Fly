#!/usr/bin/env python3
"""Evidence-only AICS data collection; never publishes an index score."""
import csv
import datetime as dt
import json
import os
import time
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
    for attempt in range(3):
        try:
            with urlopen(req, timeout=35) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code != 429 or attempt == 2:
                raise
            # Bounded retry; never silently replace missing observations.
            time.sleep((attempt + 1) * 10)
    raise RuntimeError("Unreachable HTTP retry state")
def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
key = os.getenv("FRED_API_KEY", "")
for sid, node in SERIES.items():
    if not key:
        results.append({"source":"ALFRED","id":sid,"status":"missing_secret"})
        continue
    try:
        rows = []
        vintage_available = sid == "DGS30"
        window_start = dt.date(2010, 1, 1) if vintage_available else TODAY
        while window_start <= TODAY:
            # Bound each real-time window below FRED's 2000-vintage limit.
            window_end = min(TODAY, window_start + dt.timedelta(days=365)) if vintage_available else TODAY
            offset = 0
            page_size = 1000
            while True:
                params = urlencode({"series_id":sid,"api_key":key,"file_type":"json",
                                    "realtime_start":window_start.isoformat(),
                                    "realtime_end":window_end.isoformat(),
                                    "observation_start":"2010-01-01",
                                    "limit":page_size,"offset":offset,"sort_order":"asc"})
                data = get("https://api.stlouisfed.org/fred/series/observations?"+params)
                observations = data.get("observations", [])
                if not isinstance(observations, list):
                    raise ValueError("Missing observations list")
                for o in observations:
                    if o.get("value") in ("", "."): continue
                    rows.append({"node":node,"series_id":sid,"date":o["date"],
                                 "realtime_start":o["realtime_start"],
                                 "realtime_end":o["realtime_end"],"value":o["value"],
                                 "source":"ALFRED" if vintage_available else "FRED_CURRENT_VINTAGE",
                                 "verified_pit":False})
                offset += len(observations)
                if not observations or offset >= int(data["count"]):
                    break
                if offset >= 1000000:
                    raise ValueError("ALFRED pagination safety limit reached")
            window_start = window_end + dt.timedelta(days=1)
        path = OUT / (f"alfred_{sid}.csv" if vintage_available else f"fred_current_{sid}.csv")
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["node","series_id","date","realtime_start",
                      "realtime_end","value","source","verified_pit"])
            writer.writeheader(); writer.writerows(rows)
        results.append({"source":"ALFRED" if vintage_available else "FRED_CURRENT_VINTAGE",
                        "id":sid,"status":"downloaded_unverified",
                        "historical_pit_available":False if not vintage_available else None,
                        "rows":len(rows)})
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as e:
        detail = ""
        if isinstance(e, HTTPError):
            detail = e.read(1024).decode("utf-8", errors="replace")
        results.append({"source":"ALFRED" if sid == "DGS30" else "FRED_CURRENT_VINTAGE",
                        "id":sid,"status":"error",
                        "error":type(e).__name__,
                        "http_status":e.code if isinstance(e, HTTPError) else None,
                        "api_message":detail[:500]})
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
        fields = ("form", "filingDate", "reportDate", "accessionNumber", "primaryDocument")
        counts = [len(recent.get(field, [])) for field in fields]
        if len(set(counts)) != 1:
            raise ValueError("SEC filing metadata arrays have inconsistent lengths")
        filings = []
        for form, filed, period, accession, document in zip(*(recent[field] for field in fields)):
            if form not in ("10-K", "10-Q", "8-K"):
                continue
            available_at = dt.date.fromisoformat(filed) + dt.timedelta(days=14)
            if available_at > TODAY:
                continue
            filings.append({"ticker":ticker,"cik":cik,"form":form,
                            "filed_at":filed,"available_at":available_at.isoformat(),
                            "period_end":period or None,"accession_number":accession,
                            "primary_document":document,"xbrl_fact_extracted":False,
                            "verified_pit":False})
        write_json(OUT / f"sec_eligible_filings_{ticker}.json", filings)
        results.append({"source":"SEC","id":ticker,"status":"downloaded_unverified",
                        "eligible_filings":len(filings),"rule":"filed_at+14_calendar_days",
                        "xbrl_facts_extracted":False})
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as e:
        results.append({"source":"SEC","id":ticker,"status":"error",
                        "error":type(e).__name__})
failed = sum(r["status"] != "downloaded_unverified" for r in results)
write_json(OUT / "manifest.json",{"as_of":TODAY.isoformat(),"results":results,
    "failed_sources":failed,
    "index_aics":None,"predictive_model_score":None,"publishable":False,
    "note":"Raw downloads are not independently verified PIT data. Do not score."})
print(json.dumps({"as_of":TODAY.isoformat(),"results":results},indent=2))

if failed:
    raise SystemExit(f"AICS incomplete: {failed} source(s) failed; see artifact manifest")
