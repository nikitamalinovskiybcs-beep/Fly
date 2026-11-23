"""AICS V58: unattended first capture of observed S&P500 month-close through FRED.

This is a SOURCE-CAPTURE utility, not a model trainer and not a full 11-node
AICS producer. Fetch FRED's daily index CSV and preserve one (and only one)
already-completed month-close after the prior month's first next-month traded
observation is present. The original CSV stays only in the private Actions
artifact because S&P Dow Jones Indices data displayed on FRED is copyrighted.
A timestamped SHA256 of the fetched source bytes is attached to the single
monthly numerical receipt, not a fabricated source historical timestamp.

Network or source failure MUST FAIL CLOSED. No fallback to stale or synthetic
prices. No retrospective 2024-2026 source backfill, no current-month pseudo-
close and no forward forecasts until every necessary separately timestamped
feature is available. Collection uses this process's actual UTC capture clock.

A provider API receipt cannot itself certify independent provider-first-
delivery point-in-time; that must be separately audited.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import tempfile
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

SOURCE_URL="https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500"
LEDGER=Path("aics_data/research/aics_v56_prospective_forecast_outcome_ledger.json")
RECEIPT=Path("aics_data/research/aics_v58_month_close_capture_receipt.json")
RAW=Path(tempfile.gettempdir())/"aics_sp500_fred_licensed_source.csv"
FROZEN_MONTH="2026-11"
FROZEN_DATE=dt.date(2026,11,22)
MAX_BYTES=3_000_000
USER_AGENT="AICS-Research-FirstCapture/1.0 (private research; no price redistribution)"
LEDGER_SCHEMA="aics-v56-prospective-forecast-outcome-ledger-v1"


def _month(date):
    return date.strftime("%Y-%m")


def _prev_month(instant):
    day=instant.date().replace(day=1)-dt.timedelta(days=1)
    return _month(day)


def _following_month(month):
    y,m=map(int,month.split("-"))
    return f"{y+int(m==12):04d}-{1 if m==12 else m+1:02d}"


def _parse_source(raw, received):
    if not isinstance(raw,bytes) or not raw or len(raw)>MAX_BYTES:
        raise ValueError("FRED source bytes missing or over hard size cap")
    try:
        stream=io.StringIO(raw.decode("utf-8-sig",errors="strict"),newline="")
    except UnicodeError as e:
        raise ValueError("FRED source response not UTF-8 CSV") from e
    reader=csv.DictReader(stream)
    if not reader.fieldnames or len(reader.fieldnames)!=2:
        raise ValueError("FRED SP500 CSV has unexpected structure")
    first,second=[name.strip().lower() for name in reader.fieldnames]
    if first not in ("observation_date","date") or second!="sp500":
        raise ValueError("Unexpected source series or non-FRED SP500 structure")
    records=[]
    prior_date=None
    missing_count=0
    for row in reader:
        if set(row)!=set(reader.fieldnames) or None in row:
            raise ValueError("Malformed FRED daily-row CSV")
        date_string=row[reader.fieldnames[0]]
        close_string=row[reader.fieldnames[1]]
        try:
            day=dt.date.fromisoformat(date_string)
        except (TypeError,ValueError) as e:
            raise ValueError("Malformed FRED date") from e
        if day.isoformat()!=date_string or (prior_date is not None and day<=prior_date):
            raise ValueError("Source dates must be strictly increasing")
        if day>received.date():
            raise ValueError("FRED claims a trading close in the future")
        prior_date=day
        if close_string in ("","." ,None):
            missing_count+=1
            continue
        try:
            value=Decimal(close_string)
        except (InvalidOperation,TypeError) as e:
            raise ValueError("Non-numeric daily market close") from e
        if not value.is_finite() or value<=0 or value>Decimal("100000000"):
            raise ValueError("Invalid observed S&P 500 close in source")
        if len(value.as_tuple().digits)>18:
            raise ValueError("Suspiciously precise price source, refuse")
        records.append((day,value))
    if not records:
        raise ValueError("FRED source has zero actual market closes")
    return records,missing_count


def receipt(raw,*,now=None):
    """Only previous calendar month's close, only if next month's trading seen.

    Do not backfill an October price in November 2026 as future PIT. In
    December, November is eligible only when a December market observation
    has appeared in the very same retrieved FRED original response.
    """
    current=now if now is not None else dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Actual source capture clock cannot be naive")
    current=current.astimezone(dt.timezone.utc)
    previous=_prev_month(current)
    rows,missing=_parse_source(raw,current)
    lookup={}
    for day,value in rows:
        lookup.setdefault(_month(day),[]).append((day,value))
    following=_following_month(previous)
    source_sha=hashlib.sha256(raw).hexdigest()
    candidate=None
    if previous>=FROZEN_MONTH and previous in lookup and following in lookup:
        day,value=lookup[previous][-1]
        next_day=lookup[following][0][0]
        if day>=current.date() or next_day>current.date():
            raise ValueError("No genuine past monthly close with next-month source proof")
        # FRED rows provide an exact decimal level, while V56 source ledger
        # currently validates numeric JSON float; never invent rounding.
        numeric=float(value)
        if Decimal(str(numeric))!=value:
            raise ValueError("Original FRED SP500 close cannot be preserved losslessly")
        candidate={
            "month":previous,
            "market_close_date":day.isoformat(),
            "retrieved_at_utc":current.isoformat(),
            "source_uri":SOURCE_URL,
            "source_sha256":source_sha,
            "sp500_close":numeric,
            "independently_verified_first_publication_PIT":False,
        }
    status=("NEW_MONTH_CLOSE_SOURCE_CANDIDATE" if candidate else
            "WAITING_FOR_FIRST_NEXT_MONTH_MARKET_CLOSE")
    if previous<FROZEN_MONTH:
        status="NOT_YET_ELIGIBLE_POST_FREEZE_MONTH"
    return {
        "schema":"aics-v58-first-observed-FRED-SP500-month-close-v1",
        "source_provider":"FRED Federal Reserve Bank of St Louis displaying S&P Dow Jones Indices",
        "source_url":SOURCE_URL,
        "licensed_data_full_csv_must_not_be_committed":True,
        "retrieved_at_utc":current.isoformat(),
        "original_csv_bytes_sha256":source_sha,
        "original_csv_bytes_length":len(raw),
        "original_source_observed_valid_daily_rows":len(rows),
        "original_source_missing_daily_rows":missing,
        "required_completed_month":previous,
        "first_next_month_observation_proof_present":candidate is not None,
        "month_close_candidate_for_V56":candidate,
        "status":status,
        "independently_verified_first_market_delivery":False,
        "models_or_5_expert_signals_computed":False,
        "official_AICS":None,
        "trades_created":False,
    }


def update_ledger(ledger,report,raw):
    """Append only; don't ever silently revise or backfill first-capture close."""
    if (ledger.get("schema")!=LEDGER_SCHEMA
        or ledger.get("frozen_registry_date")!="2026-11-22"
        or ledger.get("frozen_five_specialists")!=[
            "EXPERT-078","EXPERT-052","EXPERT-041","EXPERT-001","EXPERT-021"]
        or ledger.get("original_11node_weight_total_unchanged")!=1050
        or ledger.get("original_11node_AICS") is not None
        or ledger.get("no_trades") is not True
        or not isinstance(ledger.get("original_v55_forecast_snapshots"),list)
        or not isinstance(ledger.get("observed_sp500_month_closes"),list)):
        raise ValueError("Prospective market ledger freeze contract has changed")
    # Rebuild the receipt from the same immutable bytes; a JSON claim alone
    # cannot authorize adding a new market observation.
    received_claim=dt.datetime.fromisoformat(report["retrieved_at_utc"])
    if received_claim.tzinfo is None or received_claim.utcoffset() is None:
        raise ValueError("Source receipt timestamp must have a timezone")
    recalculated=receipt(raw,now=received_claim)
    for field in ("original_csv_bytes_sha256","original_csv_bytes_length",
                  "required_completed_month","month_close_candidate_for_V56","status"):
        if recalculated[field]!=report.get(field):
            raise ValueError("Candidate report does not match original FRED source bytes")
    month=report.get("required_completed_month")
    candidate=report.get("month_close_candidate_for_V56")
    received=dt.datetime.fromisoformat(report["retrieved_at_utc"])
    if candidate is not None and (candidate["month"]!=month or
                                  candidate["source_uri"]!=SOURCE_URL or
                                  candidate["independently_verified_first_publication_PIT"] is not False or
                                  candidate["source_sha256"]!=report["original_csv_bytes_sha256"] or
                                  dt.datetime.fromisoformat(candidate["retrieved_at_utc"])!=received):
        raise ValueError("Candidate evidence does not match first source capture receipt")
    if candidate is None:
        return ledger,False
    originals=ledger["observed_sp500_month_closes"]
    old=next((item for item in originals if item["month"]==month),None)
    if old is not None:
        if (old["market_close_date"]!=candidate["market_close_date"] or
            old["sp500_close"]!=candidate["sp500_close"]):
            raise ValueError("Source revision detected: do not rewrite old monthly source receipt")
        return ledger,False
    if originals and originals[-1]["month"]>=month:
        raise ValueError("Only strictly append new forward monthly observations")
    if (month<FROZEN_MONTH or
        dt.date.fromisoformat(candidate["market_close_date"])<=FROZEN_DATE or
        dt.date.fromisoformat(candidate["market_close_date"])>=received.date()):
        raise ValueError("Retrospective or same-day source is not a valid forward first capture")
    amended=json.loads(json.dumps(ledger))
    amended["observed_sp500_month_closes"].append(candidate)
    return amended,True


def fetch_source():
    request=urllib.request.Request(SOURCE_URL,headers={
        "User-Agent":USER_AGENT,"Accept":"text/csv,text/plain;q=0.9",
        "Cache-Control":"no-cache"})
    try:
        with urllib.request.urlopen(request,timeout=28) as res:
            if res.status!=200:
                raise ValueError("Provider did not return HTTP 200")
            raw=res.read(MAX_BYTES+1)
    except (TimeoutError,urllib.error.URLError) as e:
        raise RuntimeError("External live FRED source unavailable, no fallback price") from e
    if not raw or len(raw)>MAX_BYTES:
        raise ValueError("Market source is empty or too large")
    return raw


def _write_atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=None
    try:
        with tempfile.NamedTemporaryFile("wb",dir=path.parent,delete=False) as out:
            temp=Path(out.name)
            out.write(data)
        os.replace(temp,path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--receipt",type=Path,default=RECEIPT)
    p.add_argument("--raw",type=Path,default=RAW)
    p.add_argument("--ledger",type=Path,default=LEDGER)
    p.add_argument("--apply-to-ledger",action="store_true")
    args=p.parse_args()
    if args.apply_to_ledger and args.ledger.resolve()!=LEDGER.resolve():
        raise ValueError("Cannot automatically mutate an untracked ledger path")
    if args.raw.resolve().is_relative_to(Path.cwd().resolve()):
        raise ValueError("Copyrighted FRED raw source must not be stored inside the Git repo")
    raw=fetch_source()
    now=dt.datetime.now(dt.timezone.utc)
    report=receipt(raw,now=now)
    ledger=json.loads(args.ledger.read_text(encoding="utf-8"))
    amended,new=update_ledger(ledger,report,raw)
    report["actual_new_month_close_appended_to_V56_ledger"]=new if args.apply_to_ledger else False
    report["actual_new_month_close_available_not_yet_written"]=new and not args.apply_to_ledger
    # Source raw bytes stay in ephemeral job storage; NEVER source-controlled or uploaded.
    _write_atomic(args.raw,raw)
    _write_atomic(args.receipt,(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode())
    if new and args.apply_to_ledger:
        _write_atomic(args.ledger,(json.dumps(amended,ensure_ascii=False,indent=2)+"\n").encode())
    print(json.dumps({k:v for k,v in report.items() if k not in (
        "month_close_candidate_for_V56",)},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
