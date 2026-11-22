"""AICS V63 — genuinely prospective DGS30 / SOFR / IORB first-source capture.

All four frozen UST/Repo research score hypotheses existed post-hoc before
registration and are NOT official AICS scores. No training, retrospective
"new" months, trading, official full AICS, or independent publication-PIT
certification is implied. Original FRED CSV is kept ONLY in ephemeral runner
storage, no full source redistribution.

The FRED series dates are observations/effective days, NOT first-delivery
timestamps. In particular the SOFR overnight financing rate is normally
published on the following business day and can be revised. We capture the
entire response sha256 and our true UTC time of receipt. Only the previously
COMPLETED month can become an original FIRST CAPTURE research record after
the first observed joint rate in the following month. Initial Nov 2026
capture is not allowed before December.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import tempfile
import urllib.error
import urllib.request
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from pathlib import Path

from scripts.aics_v62_trusted_score_method_admission_gate import registry_frozen, PIN as V62_REGISTRY_PIN

ROOT=Path("aics_data/research")
METHOD=Path("aics_data/governance/aics_v63_frozen_future_ust_repo_shadow_methods_2026-11-22.json")
LEDGER=ROOT/"aics_v63_first_capture_ust_repo_forward_ledger.json"
RECEIPT=ROOT/"aics_v63_ust_repo_source_first_capture_receipt.json"
PIN="c08d3872644f8e09a60cd32c1c8c0f9ce05f98b6"
URL_PREFIX="https://fred.stlouisfed.org/graph/fredgraph.csv?id="
SERIES=("DGS30","SOFR","IORB")
FIRST_MONTH="2026-11"
FREEZE_DATE=dt.date(2026,11,22)
LIMIT=2_000_000
USER_AGENT="AICS-FirstSource-Future-Research/1.0 (no copyrighted raw redistribution)"

def _sha(x):
    return hashlib.sha256(x).hexdigest()

def _blob_sha(x):
    return hashlib.sha1(f"blob {len(x)}\0".encode()+x).hexdigest()

def lock_methods():
    # V62 freeze itself must remain intact before V63 is considered.
    registry_frozen()
    raw=METHOD.read_bytes()
    if _blob_sha(raw)!=PIN:
        raise ValueError("Registered V63 formula bytes changed after public freeze")
    j=json.loads(raw)
    if (j.get("schema")!="aics-v63-preregistered-future-only-research-ust-repo-source-to-shadow-v1"
        or j.get("registered_at_date")!="2026-11-22"
        or j.get("first_eligible_original_market_month")!=FIRST_MONTH
        or j.get("original_11node_weights_total")!=1050
        or j.get("trading_allowed") is not False
        or j.get("full_11_node_AICS") is not None
        or j.get("candidate_promotion")!="BLOCKED"
        or j.get("single_default_official_replacement_selected") is not None
        or j.get("hypotheses_posthoc_invented_after_known_2024_2026_history") is not True
        or j.get("model_family_is_not_independently_untouched_oos_even_after_future_appraisal") is not True
        or j.get("authoritative_v62_official_score_method_registry_sha1")!=V62_REGISTRY_PIN
        or [x.get("id") for x in j.get("shadow_scenarios_unapproved_and_not_probabilities",[])]!=[
            "UST_VOL10_POSTHOC_LOCKED","UST_VOL_PLUS_RISE_POSTHOC_LOCKED",
            "REPO_PREMIUM_20_POSTHOC_LOCKED","REPO_PREMIUM_10_POSTHOC_LOCKED"]):
        raise ValueError("Frozen research parameters inconsistent with unapproved governance")
    for name in SERIES:
        if j["source_series"][name]["uri"]!=URL_PREFIX+name:
            raise ValueError("Research source was swapped")
    return j,_sha(raw)

def _parse_series(raw,name,now):
    if name not in SERIES or type(raw)!=bytes or not 0<len(raw)<=LIMIT:
        raise ValueError("Expected genuine bounded FRED source bytes")
    try:
        stream=io.StringIO(raw.decode("utf-8-sig",errors="strict"),newline="")
    except UnicodeError as e:
        raise ValueError("Unexpected FRED encoding") from e
    reader=csv.DictReader(stream)
    if not reader.fieldnames or len(reader.fieldnames)!=2:
        raise ValueError("Source changed CSV format")
    a,b=reader.fieldnames
    if a.strip().lower() not in ("observation_date","date") or b.strip().upper()!=name:
        raise ValueError("Source rate series ID/header mismatch")
    values={}
    prior=None
    miss=0
    for row in reader:
        if set(row)!=set(reader.fieldnames) or None in row:
            raise ValueError("Malformed FRED original date/value row")
        try:
            day=dt.date.fromisoformat(row[a])
        except (TypeError,ValueError) as e:
            raise ValueError("Invalid source day") from e
        if row[a]!=day.isoformat() or (prior is not None and day<=prior) or day>now.date():
            raise ValueError("Out-of-order or future trading observation")
        prior=day
        number=row[b]
        if number in (".","",None):
            miss+=1
            continue
        try:
            value=Decimal(number)
        except (TypeError,InvalidOperation) as e:
            raise ValueError("Unparseable true rate reading") from e
        if not value.is_finite() or not Decimal(0)<=value<=Decimal(30):
            raise ValueError("Unsupported original rate value")
        if len(value.as_tuple().digits)>15:
            raise ValueError("Unexpected source precision")
        values[day]=value
    if len(values)<21:
        raise ValueError("Real DGS30/SOFR/IORB daily source too short")
    return values,miss

def _month_before(now):
    day=now.date().replace(day=1)-dt.timedelta(days=1)
    return day.strftime("%Y-%m")

def _month_after(month):
    y,m=map(int,month.split("-"))
    return f"{y+int(m==12):04d}-{m%12+1:02d}"

def _format(value):
    return str(value.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))

def _clamp(score):
    return min(Decimal(100),max(Decimal(0),score))

def _sample_volatility_bp(prices,cutoff):
    # Exactly last 21 recorded DGS30 dates <= same-date rate joint snapshot.
    history=[(d,v) for d,v in sorted(prices.items()) if d<=cutoff]
    if len(history)<21:
        raise ValueError("20 observed DGS30 changes unavailable at research date")
    recent=history[-21:]
    if (cutoff-recent[-1][0]).days>0 or (recent[-1][0]-recent[0][0]).days>45:
        raise ValueError("Treasury volatility date coverage invalid")
    changes=[(recent[i][1]-recent[i-1][1])*Decimal(100)
             for i in range(1,len(recent))]
    avg=sum(changes)/Decimal(20)
    var=sum((v-avg)**2 for v in changes)/Decimal(19)
    # Python Decimal square root; research-only scoring, round only at display.
    return var.sqrt()

def _rounded_score(x):
    return float(x.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))

def _validate_ledger(ledger):
    if (ledger.get("schema")!="aics-v63-first-capture-ust-repo-monthly-shadow-ledger-v1"
        or ledger.get("method_registry_git_blob_sha1")!=PIN
        or ledger.get("registered_at_date")!="2026-11-22"
        or ledger.get("source_first_delivery_independent_PIT_certified") is not False
        or ledger.get("official_AICS") is not None
        or ledger.get("trades_created") is not False
        or not isinstance(ledger.get("completed_monthly_snapshots"),list)):
        raise ValueError("V63 append-only ledger governance contract altered")
    previous=None
    for x in ledger["completed_monthly_snapshots"]:
        month=x.get("month")
        if (not isinstance(month,str) or month<FIRST_MONTH
            or previous is not None and month<=previous
            or x.get("official_AICS") is not None
            or x.get("scores_are_approved") is not False
            or x.get("independently_first_delivered_PIT") is not False):
            raise ValueError("Untrusted/reordered historical monthly shadow row")
        previous=month
    return ledger

def compute(raw,ledger,*,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Source receipt must be actual aware UTC")
    now=now.astimezone(dt.timezone.utc)
    if now.date()<FREEZE_DATE:
        raise ValueError("Cannot claim first live original capture before V63 registration")
    registry,registry_sha=lock_methods()
    _validate_ledger(ledger)
    if set(raw)!=set(SERIES):
        raise ValueError("All three original rate responses mandatory")
    rate_map={}
    missed={}
    fingerprints={}
    latest={}
    for n in SERIES:
        values,miss=_parse_series(raw[n],n,now)
        rate_map[n]=values
        missed[n]=miss
        fingerprints[n]={"source_url":URL_PREFIX+n,"original_bytes_sha256":_sha(raw[n]),
                         "original_bytes":len(raw[n]),"observed_numeric_rows":len(values),
                         "missing_rows":miss}
        recent=sorted(values)[-1]
        latest[n]={"last_observed_effective_date":recent.isoformat(),
                   "last_observed_rate_percent":str(values[recent])}
    prior_month=_month_before(now)
    joint=sorted(set.intersection(*(set(rate_map[n]) for n in SERIES)))
    preceding=[d for d in joint if d.strftime("%Y-%m")==prior_month]
    following=[d for d in joint if d.strftime("%Y-%m")==_month_after(prior_month)]
    next_month_first=following[0] if following else None
    candidate=None
    if prior_month>=FIRST_MONTH and preceding and next_month_first is not None:
        day=preceding[-1]
        # Rate observation dates are NOT first publication. A next-month common
        # observation in the same received originals gives temporal maturity,
        # but NOT a provider-attested publication timestamp.
        month_last=(day.replace(day=1)+dt.timedelta(days=32)).replace(day=1)-dt.timedelta(days=1)
        if ((month_last-day).days>7 or day>=now.date() or next_month_first>now.date()
            or next_month_first>=now.date() or now.date()<=FREEZE_DATE):
            raise ValueError("The candidate month has no mature joint day")
        daily_vol=_sample_volatility_bp(rate_map["DGS30"],day)
        vol10=_clamp(daily_vol*Decimal(10))
        rate=rate_map["DGS30"][day]
        sofr=rate_map["SOFR"][day]
        iorb=rate_map["IORB"][day]
        spread_bp=(sofr-iorb)*Decimal(100)
        repo20=_clamp(max(Decimal(0),spread_bp)*Decimal(5))
        repo10=_clamp(max(Decimal(0),spread_bp)*Decimal(10))
        prev=next((v for v in ledger["completed_monthly_snapshots"]
                   if v["month"]==(_month_before(dt.datetime(
                       day.year,day.month,1,tzinfo=dt.timezone.utc)))),None)
        vol_plus_rise=None
        if prev is not None:
            earlier=Decimal(prev["observed_rate_percent"]["DGS30"])
            delta=(rate-earlier)*Decimal(100)
            rise=_clamp(max(Decimal(0),delta)*Decimal(2))
            vol_plus_rise=_rounded_score((vol10+rise)/Decimal(2))
        candidate={
            "month":prior_month,
            "joint_source_rate_effective_date":day.isoformat(),
            "first_following_month_joint_observation_day":next_month_first.isoformat(),
            "first_captured_at_utc":now.isoformat(),
            "method_registry_git_blob_sha1":PIN,
            "method_registry_source_sha256":registry_sha,
            "observed_rate_percent":{"DGS30":str(rate),"SOFR":str(sofr),"IORB":str(iorb)},
            "observed_SOFR_minus_IORB_bp":str(spread_bp),
            "observed_DGS30_20_daily_yield_changes_SD_bp":_format(daily_vol),
            "research_shadows_not_official_0_100":{
                "UST_VOL10_POSTHOC_LOCKED":_rounded_score(vol10),
                "UST_VOL_PLUS_RISE_POSTHOC_LOCKED":vol_plus_rise,
                "REPO_PREMIUM_20_POSTHOC_LOCKED":_rounded_score(repo20),
                "REPO_PREMIUM_10_POSTHOC_LOCKED":_rounded_score(repo10)},
            "original_rate_source_receipts":fingerprints,
            "independently_first_delivered_PIT":False,
            "scores_are_approved":False,
            "official_AICS":None,
            "trades_created":False,
        }
    status=("FIRST_COMPLETED_POST_FREEZE_MONTH_CANDIDATE" if candidate else
            "NO_COMPLETED_JOINT_RATE_MONTH_ELIGIBLE")
    if prior_month<FIRST_MONTH:
        status="PRE_FREEZE_BACKFILL_BLOCKED"
    report={
        "schema":"aics-v63-three-real-fred-first-capture-receipt-v1",
        "captured_at_utc":now.isoformat(),
        "required_previous_calendar_month":prior_month,
        "original_series_receipts":fingerprints,
        "latest_retrieved_actual_observed_rates":latest,
        "source_last_joint_observed_date":joint[-1].isoformat() if joint else None,
        "next_month_joint_observation_exists":next_month_first is not None,
        "month_candidate":candidate,
        "status":status,
        "historical_2024_2026_oos_untouched":False,
        "source_first_delivery_PIT_independently_verified":False,
        "official_AICS":None,
        "trades_created":False,
    }
    return report

def append_research_row(ledger,report,raw):
    _validate_ledger(ledger)
    now=dt.datetime.fromisoformat(report["captured_at_utc"])
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Invalid purported first-seen time")
    rebuilt=compute(raw,ledger,now=now)
    # Require exactly the original bytes, not merely user-provided self-claims.
    for key in ("month_candidate","original_series_receipts",
                "required_previous_calendar_month","status","captured_at_utc"):
        if rebuilt[key]!=report.get(key):
            raise ValueError("Reported new rate differs from actual rehashed original FRED bytes")
    candidate=rebuilt["month_candidate"]
    if candidate is None:
        return ledger,False
    rows=ledger["completed_monthly_snapshots"]
    match=next((x for x in rows if x["month"]==candidate["month"]),None)
    if match is not None:
        # Later provider revisions must not silently amend already frozen
        # original observation, even when scores don't change after rounding.
        if (match["joint_source_rate_effective_date"]!=candidate["joint_source_rate_effective_date"]
            or match["observed_rate_percent"]!=candidate["observed_rate_percent"]
            or match["research_shadows_not_official_0_100"]!=candidate["research_shadows_not_official_0_100"]):
            raise ValueError("Provider revised an already-frozen first-observed rate")
        return ledger,False
    if rows and rows[-1]["month"]>=candidate["month"]:
        raise ValueError("Cannot append a historical month over a future observation")
    if rows and _month_after(rows[-1]["month"])!=candidate["month"]:
        raise ValueError("No missed-month backfill: original month sequence broken")
    amended=json.loads(json.dumps(ledger))
    amended["completed_monthly_snapshots"].append(candidate)
    return amended,True

def fetch(name):
    url=URL_PREFIX+name
    req=urllib.request.Request(url,headers={
        "User-Agent":USER_AGENT,"Accept":"text/csv,text/plain;q=0.9",
        "Cache-Control":"no-cache"})
    try:
        with urllib.request.urlopen(req,timeout=28) as res:
            if res.status!=200:
                raise ValueError("FRED provider HTTP status not 200")
            raw=res.read(LIMIT+1)
    except (TimeoutError,urllib.error.URLError) as e:
        raise RuntimeError("Upstream source failed; refuse stale fallback") from e
    if not raw or len(raw)>LIMIT:
        raise ValueError("Raw source unavailable or too large")
    return raw

def _atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path_tmp=None
    try:
        with tempfile.NamedTemporaryFile("wb",dir=path.parent,delete=False) as fh:
            path_tmp=Path(fh.name)
            fh.write(data)
        os.replace(path_tmp,path)
    finally:
        if path_tmp is not None and path_tmp.exists():
            path_tmp.unlink()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger",type=Path,default=LEDGER)
    p.add_argument("--receipt",type=Path,default=RECEIPT)
    p.add_argument("--apply-to-ledger",action="store_true")
    args=p.parse_args()
    if args.apply_to_ledger and args.ledger.resolve()!=LEDGER.resolve():
        raise ValueError("Only canonical versioned first-capture ledger can be edited")
    if args.receipt.resolve() in (LEDGER,METHOD):
        raise ValueError("Cannot overwrite immutable governance input")
    rows=json.loads(args.ledger.read_text(encoding="utf-8"))
    # Fetch three real live original sources. A single new capture timestamp
    # is set AFTER all source requests have completed.
    original={name:fetch(name) for name in SERIES}
    when=dt.datetime.now(dt.timezone.utc)
    report=compute(original,rows,now=when)
    amended,changed=append_research_row(rows,report,original)
    report["source_candidate_appended"]=changed if args.apply_to_ledger else False
    report["source_candidate_still_not_committed"]=changed and not args.apply_to_ledger
    _atomic(args.receipt,(json.dumps(report,indent=2,ensure_ascii=False)+"\n").encode())
    if changed and args.apply_to_ledger:
        _atomic(args.ledger,(json.dumps(amended,indent=2,ensure_ascii=False)+"\n").encode())
    # Full raw FRED original bytes exist only in-memory and CI ephemeral process.
    print(json.dumps({key:v for key,v in report.items() if key!="month_candidate"},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
