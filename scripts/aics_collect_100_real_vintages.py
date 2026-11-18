#!/usr/bin/env python3
"""100 REAL ALFRED vintage collection jobs: 4 series x 25 completed month-ends.

No synthetic observations; no present-day backfill; output never promotes AICS.
"""
import calendar
import csv
import datetime as dt
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SERIES=("DGS30","SOFR","BAMLH0A0HYM2","BAMLH0A3HYC")
OUT=Path("aics_data/pit_100")
HEADERS=("series_id","observation_date","as_of","realtime_start","realtime_end","value","source","verified_pit")

def month_end(y,m):
    return dt.date(y,m,calendar.monthrange(y,m)[1])

def snapshots(today):
    last=month_end(today.year if today.month>1 else today.year-1,today.month-1 if today.month>1 else 12)
    result=[]
    for back in range(24,-1,-1):
        n=last.year*12+last.month-1-back
        result.append(month_end(n//12,n%12+1))
    return result

def fetch(params):
    url="https://api.stlouisfed.org/fred/series/observations?"+urlencode(params)
    for attempt in range(4):
        try:
            with urlopen(Request(url,headers={"User-Agent":"AICS real 100 vintage collector"}),timeout=45) as response:
                return json.load(response)
        except HTTPError as e:
            if e.code not in (429,500,502,503,504) or attempt==3: raise
            time.sleep(min(60,10*(attempt+1)))
    raise RuntimeError("unreachable")

def run(today=None,key=None):
    today=today or dt.date.today()
    key=key if key is not None else os.environ.get("FRED_API_KEY","").strip()
    if not key:
        raise RuntimeError("FRED_API_KEY missing: no collection performed")
    OUT.mkdir(parents=True,exist_ok=True)
    jobs=[]
    for sid in SERIES:
        rows=[]
        for asof in snapshots(today):
            status={"series_id":sid,"as_of":asof.isoformat(),"status":"failed"}
            try:
                offset=0
                snapshot=[]
                while True:
                    p={"series_id":sid,"api_key":key,"file_type":"json",
                       "realtime_start":asof.isoformat(),"realtime_end":asof.isoformat(),
                       "observation_start":"2010-01-01","observation_end":asof.isoformat(),
                       "limit":1000,"offset":offset,"sort_order":"asc"}
                    payload=fetch(p)
                    obs=payload["observations"]
                    for o in obs:
                        if o.get("value") in (None,"","."):continue
                        date=dt.date.fromisoformat(o["date"])
                        start=dt.date.fromisoformat(o["realtime_start"])
                        end=dt.date.fromisoformat(o["realtime_end"])
                        if not(date<=asof and start<=asof<=end):
                            raise ValueError("look-ahead/realtime interval violation")
                        snapshot.append(dict(zip(HEADERS,(sid,o["date"],asof.isoformat(),
                            o["realtime_start"],o["realtime_end"],o["value"],"ALFRED_AS_OF",False))))
                    offset+=len(obs)
                    if offset>=int(payload["count"]) or not obs:break
                    if offset>100000:raise ValueError("pagination overflow")
                if not snapshot:raise ValueError("empty vintage")
                rows.extend(snapshot)
                status.update(status="downloaded_unverified",rows=len(snapshot))
            except (HTTPError,URLError,TimeoutError,KeyError,ValueError) as e:
                status.update(error=type(e).__name__)
                if isinstance(e,HTTPError):status["http_status"]=e.code
            jobs.append(status)
            time.sleep(0.4)
        path=OUT/f"alfred_asof_{sid}.csv"
        with path.open("w",newline="",encoding="utf-8") as fh:
            writer=csv.DictWriter(fh,fieldnames=HEADERS)
            writer.writeheader();writer.writerows(rows)
    manifest={"as_of":today.isoformat(),"job_count":len(jobs),
              "successful_jobs":sum(j["status"]=="downloaded_unverified" for j in jobs),
              "jobs":jobs,"source":"ALFRED historical as-of API",
              "csv_sha256":{sid:hashlib.sha256((OUT/f"alfred_asof_{sid}.csv").read_bytes()).hexdigest() for sid in SERIES},
              "independently_verified_pit":False,"index_aics":None,
              "model_score":None,"promotion":"BLOCKED","trades_created":False}
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({"job_count":manifest["job_count"],"successful_jobs":manifest["successful_jobs"],"promotion":"BLOCKED"}))
    return manifest["successful_jobs"]==100

if __name__=="__main__":
    raise SystemExit(0 if run() else 2)
