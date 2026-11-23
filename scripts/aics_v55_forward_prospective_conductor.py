"""AICS V55 locked five-specialist prospective research scoring contract.

Never refit/reselect the V53 experts. Do not republish the pre-freeze
2024-2026 backtest as OOS. There is deliberately NO forward score today:
a genuine new, timestamped source snapshot AFTER 2026-11-22 is required.

On a supplied future snapshot, produce ONLY a non-PIT-certified five-expert
research shadow score and the prospective label-evaluation schedule. This
module makes NO market-data requests, no provider first-feed attestation, no
full 11-node AICS score, no similarity percent to 2000/2008, and no trades.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from scripts.aics_v53_hundred_model_top5_ensemble import (
    candidate_score, FAMILIES
)
from scripts.aics_score_reproducibility_gate import WEIGHTS

FROZEN=Path("aics_data/research/aics_v53_frozen_top5_shadow_selection_2026-11-22.json")
V53_SCRIPT=Path("scripts/aics_v53_hundred_model_top5_ensemble.py")
OUT=Path("aics_data/research/aics_v55_forward_model_initial_status_2026-11-22.json")
FROZEN_V53_BLOB_SHA="3420c289c6bd4b0387396e50937a525f19f4035e"
FROZEN_REGISTER_BLOB_SHA="15d051e55b65cabd732cbf57c0fba42806fc2f39"
FROZEN_DATE=dt.date(2026,11,22)
NODES=11
SELECTED=("EXPERT-078","EXPERT-052","EXPERT-041","EXPERT-001","EXPERT-021")
FAMILIES_SELECTED=(
    "one_month_market_shock_analyst",
    "severity_acceleration_sentinel",
    "breadth_acceleration_sentinel",
    "breadth_persistence_specialist",
    "credit_mix_architect",
)
REQUIRED_FEATURES=(
    "B","S","BM2","SM3","BM3","SM2","loss3","loss1","vol","accelB","accelS"
)
HORIZONS=(1,3,6)
THRESHOLDS=(5,10)
assert len(WEIGHTS)==NODES and sum(WEIGHTS.values())==1050


def git_blob_sha(raw):
    return hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()


def iso_instant(value):
    if not isinstance(value,str):
        raise ValueError("Timestamp must be an actual aware ISO 8601 string")
    try:
        instant=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as e:
        raise ValueError("Invalid actual UTC/source timestamp") from e
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Naive timestamp is not provable publication time")
    return instant.astimezone(dt.timezone.utc)


def exact_date(value):
    if not isinstance(value,str):
        raise ValueError("Date must be exact ISO YYYY-MM-DD")
    x=dt.date.fromisoformat(value)
    if x.isoformat()!=value:
        raise ValueError("Non-canonical date")
    return x


def month_last_date(month):
    if (not isinstance(month,str) or len(month)!=7
        or month[4]!="-"):
        raise ValueError("Unrecognized monthly forecast identifier")
    try:
        y=int(month[:4]);m=int(month[5:7])
        start=dt.date(y,m,1)
    except ValueError as e:
        raise ValueError("Invalid forecast month") from e
    return start


def file_digest(path):
    raw=path.read_bytes()
    return {"git_blob_sha1":git_blob_sha(raw),"raw_sha256":hashlib.sha256(raw).hexdigest()}


def validate_freeze(frozen):
    if (file_digest(V53_SCRIPT)["git_blob_sha1"]!=FROZEN_V53_BLOB_SHA
        or file_digest(FROZEN)["git_blob_sha1"]!=FROZEN_REGISTER_BLOB_SHA):
        raise ValueError("Frozen V53 code or expert roster changed without registration")
    if (frozen.get("schema")!="aics-v53-five-selected-model-experts-preregistered-shadow-candidate-v1"
        or frozen.get("recorded_at_date")!=FROZEN_DATE.isoformat()
        or frozen.get("chosen_top5_agent_ids")!=list(SELECTED)
        or frozen.get("chosen_top5_families")!=list(FAMILIES_SELECTED)
        or frozen.get("default_unapproved_fusion")!="five_model_median"
        or frozen.get("historical_selection_uses_outcomes") is not True
        or frozen.get("no_rerank_on_fresh_data_without_new_version") is not True
        or frozen.get("future_out_of_sample_results") is not None
        or frozen.get("production_AICS") is not None
        or frozen.get("trading_approved") is not False
        or frozen.get("old_11node_weights_total_unchanged")!=1050):
        raise ValueError("Prospective frozen research spec is corrupted or promoted")
    for model_id,family in zip(SELECTED,FAMILIES_SELECTED):
        n=int(model_id.rsplit("-",1)[1])
        if n<1 or n>100 or FAMILIES[(n-1)//10]!=family:
            raise ValueError("Frozen expert model ID-family mismatch")
    return {
        "frozen_registry_git_blob":FROZEN_REGISTER_BLOB_SHA,
        "frozen_execution_code_git_blob":FROZEN_V53_BLOB_SHA,
        "five_exact_frozen_expert_ids":list(SELECTED),
        "default_fusion":"median",
        "original_candidate_selection_used_historical_outcomes":True,
    }


def score_candidate(data,*,actual_now=None):
    """Fail closed on missing new observations, time leaks and fake certs."""
    if (data.get("schema")!="aics-v55-prospective-research-snapshot-v1"
        or data.get("certified_11node_AICS") is not None
        or data.get("independent_source_delivery_pit_certified") is not False
        or data.get("trading_permission") is not False):
        raise ValueError("Only unapproved prospective research snapshots accepted")
    month=data.get("signal_month")
    first=month_last_date(month)
    if first<=dt.date(2026,10,1):
        raise ValueError("Pre-freeze market months cannot be relabeled as forward OOS")
    close_date=exact_date(data.get("market_close_date"))
    if close_date.year!=first.year or close_date.month!=first.month:
        raise ValueError("Future snapshot market date does not match monthly risk period")
    if close_date<=FROZEN_DATE:
        raise ValueError("Genuine new market close must be after the freeze")
    asof=iso_instant(data.get("forecast_created_at_utc"))
    wallclock=(actual_now if actual_now is not None else dt.datetime.now(dt.timezone.utc))
    if wallclock.tzinfo is None or asof>wallclock.astimezone(dt.timezone.utc):
        raise ValueError("A self-reported future timestamp cannot create a current prospective forecast")
    close_retrieved=iso_instant(data.get("market_close_retrieved_at_utc"))
    if asof.date()<close_date or close_retrieved.date()<close_date or close_retrieved>asof:
        raise ValueError("No scoring prior to real market close and publication")
    if asof.date()<=FROZEN_DATE:
        raise ValueError("Forecaster must run only after model was registered")
    market_uri=data.get("market_close_source_uri")
    market_sha=data.get("market_close_source_sha256")
    if (not isinstance(market_uri,str) or not market_uri.startswith("https://")
        or not isinstance(market_sha,str) or len(market_sha)!=64
        or any(c not in "0123456789abcdef" for c in market_sha.lower())):
        raise ValueError("Future monthly market close evidence is not identifiable")
    features=data.get("features")
    if not isinstance(features,dict) or set(features)!=set(REQUIRED_FEATURES):
        raise ValueError("All eleven recorded shadow feature definitions are mandatory")
    values={}
    for name,row in features.items():
        if not isinstance(row,dict):
            raise ValueError("Every future feature needs its own actual first-seen receipt")
        value=row.get("value")
        if isinstance(value,bool) or not isinstance(value,(float,int)):
            raise ValueError("Only numerical observed source feature values accepted")
        value=float(value)
        if not math.isfinite(value) or not 0<=value<=100:
            raise ValueError("Future feature value must have valid research model range")
        available=iso_instant(row.get("source_first_seen_at_utc"))
        if available>asof:
            raise ValueError("Prospective source was first seen after its forecast")
        sha=row.get("source_sha256")
        uri=row.get("source_uri")
        if (not isinstance(sha,str) or len(sha)!=64
            or any(c not in "0123456789abcdef" for c in sha.lower())
            or not isinstance(uri,str) or not uri.startswith("https://")):
            raise ValueError("Source feature receipt missing immutable identity")
        if row.get("independently_attested_publication_PIT") is not False:
            raise ValueError("Do not assert independent PIT verification by self-report")
        values[name]=value
    raw=[]
    for model_id in SELECTED:
        expert_number=int(model_id.rsplit("-",1)[1])
        family=(expert_number-1)//10
        variant=(expert_number-1)%10+1
        prediction=candidate_score(family,variant,values)
        raw.append({"model_id":model_id,"shadow_risk_0_100":round(prediction,6)})
    avg=math.fsum(x["shadow_risk_0_100"] for x in raw)/len(raw)
    med=median(x["shadow_risk_0_100"] for x in raw)
    return {
        "schema":"aics-v55-prospective-five-model-forward-research-score-v1",
        "market_month":month,
        "as_of_utc":asof.isoformat(),
        "market_close_date":close_date.isoformat(),
        "new_month_after_frozen_date":True,
        "five_individual_frozen_expert_shadow_scores":raw,
        "five_equal_weight_mean_shadow_score_NOT_AICS":round(avg,6),
        "five_median_shadow_score_NOT_AICS":round(med,6),
        "forward_event_horizons_months":list(HORIZONS),
        "future_SP500_drawdown_thresholds_percent":list(THRESHOLDS),
        "future_outcomes_matured":False,
        "future_crisis_warning_accuracy":None,
        "independent_source_delivery_PIT_attested":False,
        "full_11_node_AICS":None,
        "trade_permission":False,
        "market_and_feature_receipt_hashes_self_reported_not_independently_rehashed":True,
        "warning":"A verified date/format receipt is not independently attested first-delivery evidence.",
    }


def build(frozen,snapshot=None,*,actual_now=None):
    contract=validate_freeze(frozen)
    candidate=score_candidate(snapshot,actual_now=actual_now) if snapshot is not None else None
    return {
        "schema":"aics-v55-forward-only-model-conductor-v1",
        "registry_recorded_at":"2026-11-22",
        "as_of_research_build_date":"2026-11-22",
        "crisis_warning_definition":"Prospective warning must PRECEDE first objective market/funding onset, not merely WorldCom/Lehman",
        "historical_dotcom_nasdaq_crisis_onset":"2000-03-10",
        "hypothesized_old_crossing_2000_window":["2000-10-01","2000-12-31"],
        "historical_funding_crisis_onset":"2007-08-09",
        "hypothesized_old_crossing_2007_window":["2007-10-01","2007-12-31"],
        "old_crossing_precedes_actual_2000_or_2007_onset":False,
        "old_historical_crossing_independently_reproduced":False,
        "model_registry_hash_locked":contract,
        "next_possible_first_prospective_month":"2026-11",
        "first_new_prospective_month_has_real_market_and_feature_snapshot":candidate is not None,
        "prospective_research_score":candidate,
        "prospective_missing_event_outcomes_must_remain_null":candidate is None,
        "current_operational_status":"FORWARD_RESEARCH_SCORE_READY_UNCERTIFIED" if candidate else "AWAITING_GENUINE_FIRST_NEW_MONTH_SOURCE",
        "five_model_historical_5pct_AUC_is_not_prospective_accuracy":True,
        "historical_10pct_crisis_backtest_falsifiable":False,
        "future_market_data_invented":False,
        "full_11_node_AICS":None,
        "independent_11node_PIT_certified":0,
        "original_11node_weights_unchanged":1050,
        "production_trades":False,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen",type=Path,default=FROZEN)
    parser.add_argument("--prospective-snapshot",type=Path)
    parser.add_argument("--out",type=Path,default=OUT)
    args=parser.parse_args()
    if args.frozen.resolve()!=FROZEN.resolve():
        raise ValueError("Frozen expert roster cannot be silently replaced by a path flag")
    freeze=json.loads(args.frozen.read_text(encoding="utf-8"))
    snapshot=(json.loads(args.prospective_snapshot.read_text(encoding="utf-8"))
              if args.prospective_snapshot else None)
    report=build(freeze,snapshot)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
