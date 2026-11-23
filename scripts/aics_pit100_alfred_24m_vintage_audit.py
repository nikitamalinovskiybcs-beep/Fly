"""AICS 24m ALFRED day-as-of (vintage) retrieval for DGS30 and IORB.

48 original official FRED/ALFRED observations queries: two series x the
24 actual historical month-end source cutoffs. Request explicitly includes
realtime_start=realtime_end=the historical cutoff. Do NOT accept today's
revised latest data as if contemporaneous. Retain original JSON SHA256,
observed as-of vintage window and a date-only *pre-close safe* selection,
excluding observations on the market-close day without source release time.

Historical retro-queried ALFRED vintages help verify old revisions but do NOT
attest intraday publisher first-receipt, independently preregister AICS scores,
or promote a complete production model. All source-query failures stay null.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import time
from decimal import Decimal,InvalidOperation
from pathlib import Path
from urllib.parse import urlencode,urlparse,parse_qs
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

from scripts.aics_pit100_rebuild_24_month_public_filing_panel import (
    OVERLAY,read_bytes,
)

ROOT=Path("aics_data/agent_runs/ten_real_collection_rounds")
OUT=ROOT/"aics_pit100_24m_alfred_two_source_vintages.json"
RAW=ROOT/"pit100_alfred_24m_vintage_source_raw"
BASE="https://api.stlouisfed.org/fred/series/observations"
SERIES=("DGS30","IORB")
MAX_BYTES=500_000


def query(series,cutoff,key):
    if series not in SERIES or not re.fullmatch(r"20\d\d-\d\d-\d\d",cutoff):
        raise ValueError("Only historical 24m FRED market cutoffs supported")
    if not isinstance(key,str) or len(key)<10:
        raise ValueError("FRED API key not available")
    day=dt.date.fromisoformat(cutoff)
    args={
        "series_id":series,"realtime_start":cutoff,"realtime_end":cutoff,
        "observation_start":(day-dt.timedelta(days=14)).isoformat(),
        "observation_end":cutoff,"file_type":"json",
        "sort_order":"desc","limit":100,
        "api_key":key,
    }
    return BASE+"?"+urlencode(args)


def no_secret_url(url):
    base,sep,q=url.partition("?")
    params={k:v for k,v in parse_qs(q).items() if k!="api_key"}
    return base+"?"+urlencode([(k,x) for k,v in params.items() for x in v])


def fetch(url):
    if not url.startswith(BASE+"?"):
        raise ValueError("Only official FRED as-of vintage API")
    with urlopen(Request(url,headers={"Accept":"application/json",
                                     "User-Agent":"AICS Original PIT Research"}),timeout=18) as res:
        if not res.geturl().startswith(BASE+"?"):
            raise ValueError("Unexpected FRED vintage redirect")
        return res.read(MAX_BYTES+1)


def parse(raw,*,series,cutoff):
    if not isinstance(raw,bytes) or not 5<len(raw)<=MAX_BYTES:
        raise ValueError("Empty or oversized official FRED vintage")
    j=json.loads(raw)
    observations=j.get("observations",[])
    if not isinstance(observations,list):
        raise ValueError("No original ALFRED observations")
    before=[]
    same_day=[]
    all_seen=0
    for x in observations:
        if not isinstance(x,dict) or not all(k in x for k in ("date","value","realtime_start","realtime_end")):
            raise ValueError("FRED missing realtime observation identity")
        # A vintage request must be valid at the requested as-of day.
        if not (x["realtime_start"]<=cutoff<=x["realtime_end"]):
            raise ValueError("FRED observation not part of requested historical vintage")
        if x["date"]>cutoff:
            raise ValueError("Future-dated FRED value leaked into as-of")
        all_seen+=1
        if x["value"]==".":
            continue
        try:
            val=Decimal(str(x["value"]))
            if not val.is_finite():
                raise ValueError("Non-finite FRED as-of value")
        except (InvalidOperation,TypeError) as exc:
            raise ValueError("Non-numeric FRED vintage value") from exc
        record={"observed_date":x["date"],"rate_pct_original_asof":str(val),
                "realtime_start":x["realtime_start"],
                "realtime_end":x["realtime_end"]}
        if x["date"]<cutoff:
            before.append(record)
        else:
            same_day.append(record)
    before.sort(key=lambda x:x["observed_date"],reverse=True)
    same_day.sort(key=lambda x:x["observed_date"],reverse=True)
    return {
        "series":series,"asof_realtime_day":cutoff,
        "observation_rows_with_vintage_metadata":all_seen,
        "latest_before_market_cutoff_dateonly":before[0] if before else None,
        "latest_on_cutoff_day_unverified_intraday_only":same_day[0] if same_day else None,
        "earliest_observation_not_pulled_from_future":True,
        "source_vintage_asof_date_verified_from_API_response":True,
        "first_intraday_delivery_time_verified":False,
        "2026_retrieval_not_historical_original_response_capture":True,
    }


def collect(overlay,*,key,as_of,out=OUT,rawdir=RAW,fetcher=None,sleeper=None):
    months=overlay.get("monthly_last_weekday_market_proxy",[])
    if (overlay.get("schema")!="aics-24m-multi-node-first-public-date-research-overlay-v1"
        or len(months)!=24
        or overlay.get("independently_historical_pit_attested") is not False
        or not re.fullmatch(r"20\d\d-\d\d-\d\d",as_of)):
        raise ValueError("24 historical source research months required")
    if len({x["month"] for x in months})!=24 or months[-1]["month"]!="2026-10":
        raise ValueError("Broken original 24 month source window")
    rawdir=Path(rawdir);out=Path(out)
    rawdir.mkdir(parents=True,exist_ok=True)
    out.parent.mkdir(parents=True,exist_ok=True)
    fetcher=fetcher or fetch
    sleeper=sleeper or (lambda:time.sleep(.23))
    attempts=[]
    for month in months:
        cutoff=month["cutoff_date"]
        if cutoff>as_of or cutoff[:7]!=month["month"]:
            raise ValueError("Future or wrongly aligned historical cutoff")
        for series in SERIES:
            entry={
                "series":series,"month":month["month"],"market_cutoff_day":cutoff,
                "official_vintage_query_realtime_start_end":cutoff,
                "source_vintage_api_receipt_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
                "retrieved_currently_from_official_FRED_history":False,
                "source_original_sha256":None,
                "historically_PIT_source_delivery_attested":False,
                "approved_11node_score":None,
            }
            try:
                url=query(series,cutoff,key)
                entry["source_query_no_secret"]=no_secret_url(url)
                raw=fetcher(url)
                selection=parse(raw,series=series,cutoff=cutoff)
                if selection["latest_before_market_cutoff_dateonly"] is None:
                    raise ValueError("No valid pre-close-safe vintage observation")
                sha=hashlib.sha256(raw).hexdigest()
                target=rawdir/(f"{series}_{cutoff}_"+sha[:12]+".json.gz")
                target.write_bytes(gzip.compress(raw,compresslevel=6,mtime=0))
                if gzip.decompress(target.read_bytes())!=raw:
                    raise ValueError("Archived FRED original response changed")
                entry.update({
                    "retrieved_currently_from_official_FRED_history":True,
                    "source_original_sha256":sha,
                    "raw_source_bytes":len(raw),
                    "source_raw_archive_gz_path":str(target),
                    "asof_selection":selection,
                })
            except (HTTPError,URLError,OSError,TimeoutError,ValueError,TypeError,json.JSONDecodeError) as exc:
                entry.update({
                    "failure_type":type(exc).__name__,
                    "http_status":exc.code if isinstance(exc,HTTPError) else None,
                })
            attempts.append(entry)
            sleeper()
    if len(attempts)!=48 or len({(x["series"],x["month"]) for x in attempts})!=48:
        raise ValueError("Expected 48 unique official historical vintage requests")
    passed=[x for x in attempts if x["retrieved_currently_from_official_FRED_history"]]
    report={
        "schema":"aics-PIT100-24m-DGS30-IORB-ALFRED-historical-asof-snapshots-v1",
        "as_of":as_of,
        "official_historical_vintage_requests_attempted":48,
        "official_historical_vintage_original_responses_archived":len(passed),
        "official_historical_vintage_failed_or_missing":48-len(passed),
        "market_months_requested":24,
        "separate_historical_series_count":2,
        "strictly_pre_cutoff_observation_date_selected":True,
        "realtime_start_equals_realtime_end_on_each_query":True,
        "original_asof_vintage_values_are_not_reconstructed_from_latest_revised_series":True,
        "current_retrieval_does_not_prove_historical_first_receipt_time":True,
        "ALFRED_snapshot_query_does_not_certify_intraday_preclose_availability":True,
        "historical_pit_certified_index_nodes":0,
        "complete_11node_AICS":None,
        "AICS_SP500_spread":None,
        "trades_created":False,
        "monthly_observations":attempts,
    }
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="monthly_observations"}))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--rawdir",type=Path,default=RAW)
    p.add_argument("--overlay",type=Path,default=OVERLAY)
    args=p.parse_args()
    collect(read_bytes(args.overlay),key=os.getenv("FRED_API_KEY",""),as_of=args.as_of,
            out=args.out,rawdir=args.rawdir)


if __name__=="__main__":
    main()
