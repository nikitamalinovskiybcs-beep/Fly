#!/usr/bin/env python3
"""Historical ALFRED as-of snapshots. Never replace unavailable vintages with current data."""
import calendar
import csv
import datetime as dt
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OUT = Path("aics_data/pit")
OUT.mkdir(parents=True, exist_ok=True)
TODAY = dt.date.today()
SERIES = ("DGS30", "SOFR", "BAMLH0A0HYM2", "BAMLH0A3HYC")
KEY = os.getenv("FRED_API_KEY", "").strip()
HEADERS = ("series_id","observation_date","as_of","realtime_start",
           "realtime_end","value","source","verified_pit")
def month_end(year,month):
    return dt.date(year,month,calendar.monthrange(year,month)[1])
def month_back(date, n):
    total=date.year*12+(date.month-1)-n
    return month_end(total//12,total%12+1)
# 24 historical month-end snapshots, ending at the last completed month.
last_month=month_back(TODAY,1)
DATES=tuple(sorted(month_back(last_month,n) for n in range(24)))
def request_json(params):
    url="https://api.stlouisfed.org/fred/series/observations?"+urlencode(params)
    for attempt in range(4):
        try:
            with urlopen(Request(url,headers={"User-Agent":"AICS PIT audit"}),timeout=45) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in (429,500,502,503,504) or attempt==3:
                raise
            retry=exc.headers.get("Retry-After","")
            wait=int(retry) if retry.isdigit() else 10*(attempt+1)
            time.sleep(min(wait,60))
    raise RuntimeError("Retry exhausted")
results=[]
for sid in SERIES:
    rows=[]
    statuses=[]
    for as_of in DATES:
        if not KEY:
            statuses.append({"as_of":as_of.isoformat(),"status":"missing_secret"})
            continue
        offset=0
        snapshot_rows=[]
        try:
            while True:
                params={"series_id":sid,"api_key":KEY,"file_type":"json",
                        "realtime_start":as_of.isoformat(),
                        "realtime_end":as_of.isoformat(),
                        "observation_start":"2010-01-01",
                        "observation_end":as_of.isoformat(),
                        "limit":1000,"offset":offset,"sort_order":"asc"}
                payload=request_json(params)
                observations=payload.get("observations")
                if not isinstance(observations,list):
                    raise ValueError("No observations array")
                for o in observations:
                    if o.get("value") in ("",".",None):
                        continue
                    observed=dt.date.fromisoformat(o["date"])
                    rs=dt.date.fromisoformat(o["realtime_start"])
                    re=dt.date.fromisoformat(o["realtime_end"])
                    if observed>as_of or not(rs<=as_of<=re):
                        raise ValueError("Historical snapshot violates as-of boundary")
                    snapshot_rows.append({"series_id":sid,"observation_date":o["date"],
                                          "as_of":as_of.isoformat(),
                                          "realtime_start":o["realtime_start"],
                                          "realtime_end":o["realtime_end"],"value":o["value"],
                                          "source":"ALFRED_AS_OF","verified_pit":False})
                offset+=len(observations)
                if not observations or offset>=int(payload["count"]):
                    break
                if offset>100000:
                    raise ValueError("Pagination safety limit")
            rows.extend(snapshot_rows)
            statuses.append({"as_of":as_of.isoformat(),
                             "status":"downloaded_unverified" if snapshot_rows else "empty",
                             "rows":len(snapshot_rows)})
        except (HTTPError,URLError,TimeoutError,ValueError,KeyError) as exc:
            statuses.append({"as_of":as_of.isoformat(),"status":"error",
                             "error":type(exc).__name__,
                             "http_status":exc.code if isinstance(exc,HTTPError) else None})
        time.sleep(0.4)
    path=OUT/f"alfred_asof_{sid}.csv"
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    results.append({"series_id":sid,"snapshots":statuses,"rows":len(rows),
                    "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                    "complete":len(statuses)==24 and
                    all(x["status"]=="downloaded_unverified" for x in statuses)})
manifest={"as_of":TODAY.isoformat(),"source":"ALFRED historical as-of snapshots",
          "window":"24 completed month ends","results":results,
          "verified_pit":False,"publishable":False,
          "index_aics":None,"model_score":None,
          "note":"As-of API retrieval is research evidence, not independently validated PIT."}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print(json.dumps({"as_of":manifest["as_of"],
                  "complete_series":[r["series_id"] for r in results if r["complete"]],
                  "incomplete_series":[r["series_id"] for r in results if not r["complete"]],
                  "snapshot_counts":{r["series_id"]:sum(s["status"]=="downloaded_unverified"
                     for s in r["snapshots"]) for r in results}},indent=2))
if not all(r["complete"] for r in results):
    raise SystemExit("ALFRED PIT snapshots incomplete; no historical PIT promotion")
