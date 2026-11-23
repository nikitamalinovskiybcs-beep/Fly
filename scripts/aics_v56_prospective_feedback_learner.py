"""AICS V56 prospective feedback learner for the five frozen V53 specialists.

This is genuinely executable online weight adaptation, not 100 LLMs.
NO historical 2024-26 training labels, no invented market prices, no retraining
base GPT or underlying five experts. Fail closed until >=12 NEW fully matured
one-month labels with two distinct positive >=5% monthly-close drawdown
episodes and two negative labels. This small-data policy is a research-only
heuristic, NOT proof of calibration or improvement. No production trades.

Every prediction is reconstructed from its timestamped V55 source snapshot.
Each subsequent outcome uses a separately timestamped, original-source
S&P500 month-close receipt. The frozen score is computed at forecast timestamp;
weights are built using only outcomes matured before that timestamp.

A hash named in user data is not independently verified first delivery; the
ledger and source bytes still require external independent append-only audit.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from scripts.aics_v55_forward_prospective_conductor import (
    FROZEN, SELECTED, THRESHOLDS, HORIZONS, iso_instant, exact_date,
    validate_freeze, score_candidate, month_last_date
)
from scripts.aics_score_reproducibility_gate import WEIGHTS

INPUT=Path("aics_data/research/aics_v56_prospective_forecast_outcome_ledger.json")
OUTPUT=Path("aics_data/research/aics_v56_self_learning_status.json")
SCHEMA="aics-v56-prospective-forecast-outcome-ledger-v1"
LEARNING_LABEL="one_month_SP500_month_close_drawdown_at_least_5pct"
LEARNING_THRESHOLD=0.05
MIN_MATURED_LABELS=12
MIN_POSITIVE_MONTHS=2
MIN_NEGATIVE_MONTHS=2
MIN_INDEPENDENT_POSITIVE_EPISODES=2
LEARNING_RATE=0.5
SOFTMAX_MIX=0.25
INITIAL_WEIGHTS={name:0.2 for name in SELECTED}
assert len(WEIGHTS)==11 and sum(WEIGHTS.values())==1050


def month_after(value,steps=1):
    if type(steps)!=int or steps<0 or steps>120:
        raise ValueError("Bad forward-only outcome horizon")
    d=month_last_date(value)
    n=(d.year*12+d.month-1)+steps
    return f"{n//12:04d}-{n%12+1:02d}"


def _as_utc_now(now):
    now=now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Real evaluation clock must include timezone")
    return now.astimezone(dt.timezone.utc)


def _numeric(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
        raise ValueError("S&P500 monthly close must be actual positive numeric number")
    return float(value)


def _hash_format(s):
    if (not isinstance(s,str) or len(s)!=64
        or any(x not in "0123456789abcdef" for x in s.lower())):
        raise ValueError("Original source receipt requires SHA256 syntax")


def _source_uri(uri):
    if not isinstance(uri,str) or not uri.startswith("https://"):
        raise ValueError("Source receipt must have an HTTPS URI")


def _market_closes(ledger,now):
    close_rows={}
    prior=None
    for row in ledger["observed_sp500_month_closes"]:
        if not isinstance(row,dict):
            raise ValueError("Invalid original monthly market-close record")
        month=row.get("month")
        month_after(month,0)
        if month<"2026-11":
            raise ValueError("No retrospective 2024–2026 price backfill allowed")
        if prior is not None and month<=prior:
            raise ValueError("S&P monthly market-close receipts must be append-only chronological")
        prior=month
        date=exact_date(row.get("market_close_date"))
        if date.year!=int(month[:4]) or date.month!=int(month[5:7]):
            raise ValueError("Market-close receipt has wrong month")
        retrieved=iso_instant(row.get("retrieved_at_utc"))
        if retrieved.date()<date or retrieved>now:
            raise ValueError("Market-close receipt was not actually available by evaluation clock")
        sha=row.get("source_sha256")
        _hash_format(sha)
        _source_uri(row.get("source_uri"))
        if row.get("independently_verified_first_publication_PIT") is not False:
            raise ValueError("Do not forge independent historical/provider PIT claim")
        price=_numeric(row.get("sp500_close"))
        close_rows[month]={"close":price,"date":date,"retrieved":retrieved,
                           "uri":row["source_uri"],"sha":sha}
    return close_rows


def _positive_episodes(events):
    """Count beginnings of consecutive calendar-month positive label streaks."""
    positive=sorted(ev["month"] for ev in events if ev["label"])
    count=0
    prior=None
    for month in positive:
        if prior is None or month_after(prior)!=month:
            count+=1
        prior=month
    return count


def _learn(prior_events,*,now):
    """Weights are prospective research challenger ONLY, never base AICS.

    Squared error against a binary >=5% month-close event is a bounded
    ORDINAL SURROGATE; score/100 is NOT a calibrated event probability.
    """
    matured=sorted((e for e in prior_events if e["matured_at"]<=now),
                   key=lambda x:(x["matured_at"],x["month"]))
    positives=sum(e["label"] for e in matured)
    negatives=len(matured)-positives
    episodes=_positive_episodes(matured)
    eligible=(len(matured)>=MIN_MATURED_LABELS and
              positives>=MIN_POSITIVE_MONTHS and
              negatives>=MIN_NEGATIVE_MONTHS and
              episodes>=MIN_INDEPENDENT_POSITIVE_EPISODES)
    if not eligible:
        weights=dict(INITIAL_WEIGHTS)
    else:
        losses={
            name:math.fsum((e["raw_expert_risk"][name]/100-float(e["label"]))**2
                           for e in matured)
            for name in SELECTED
        }
        # Shift log weights before exp so evaluation cannot overflow.
        logits={name:-LEARNING_RATE*loss for name,loss in losses.items()}
        top=max(logits.values())
        exp={name:math.exp(x-top) for name,x in logits.items()}
        total=math.fsum(exp.values())
        weights={
            name:0.75/len(SELECTED)+SOFTMAX_MIX*exp[name]/total
            for name in SELECTED
        }
    if not math.isclose(math.fsum(weights.values()),1.0,abs_tol=1e-12):
        raise ValueError("Research expert weights must sum to one")
    if min(weights.values())<0.15-1e-12 or max(weights.values())>0.4+1e-12:
        raise ValueError("Shadow learner vote weight concentration exceeds freeze contract")
    return {
        "trained_using_matured_labels":eligible,
        "matured_1month_forecast_labels":len(matured),
        "observed_positive_label_months":positives,
        "observed_negative_label_months":negatives,
        "distinct_observed_positive_episodes":episodes,
        "prospective_five_expert_weights":{name:round(weights[name],10) for name in SELECTED},
        "research_only_bounded_ordinal_squared_error_not_calibrated_probability":True,
    }


def _forecast(record,closes,now):
    if not isinstance(record,dict) or record.get("schema")!="aics-v55-prospective-research-snapshot-v1":
        raise ValueError("Forecast receipt must preserve its complete original V55 input")
    month=record.get("signal_month")
    if month not in closes:
        raise ValueError("No independent market-close receipt for source forecast")
    score=score_candidate(record,actual_now=now)
    assert score["full_11_node_AICS"] is None
    c=closes[month]
    if (score["market_close_date"]!=c["date"].isoformat()
        or record["market_close_retrieved_at_utc"] is None
        or iso_instant(record["market_close_retrieved_at_utc"])!=c["retrieved"]
        or record["market_close_source_uri"]!=c["uri"]
        or record["market_close_source_sha256"].lower()!=c["sha"].lower()):
        raise ValueError("Source forecast not tied to the exact received starting close")
    when=iso_instant(record["forecast_created_at_utc"])
    individual={x["model_id"]:x["shadow_risk_0_100"]
                for x in score["five_individual_frozen_expert_shadow_scores"]}
    if tuple(individual)!=SELECTED:
        raise ValueError("Five frozen V53 specialist models were replaced")
    return {
        "month":month,"asof":when,"initial_SP500_close":c["close"],
        "raw_expert_risk":individual,
        "frozen_V53_median":score["five_median_shadow_score_NOT_AICS"],
        "untrained_mean":score["five_equal_weight_mean_shadow_score_NOT_AICS"],
    }


def evaluate(ledger,*,now=None):
    wallclock=_as_utc_now(now)
    freeze=json.loads(FROZEN.read_text(encoding="utf-8"))
    locked=validate_freeze(freeze)
    if (not isinstance(ledger,dict) or ledger.get("schema")!=SCHEMA
        or ledger.get("frozen_registry_date")!="2026-11-22"
        or ledger.get("frozen_five_specialists")!=list(SELECTED)
        or ledger.get("original_11node_weight_total_unchanged")!=1050
        or ledger.get("no_trades") is not True
        or ledger.get("original_11node_AICS") is not None
        or not isinstance(ledger.get("original_v55_forecast_snapshots"),list)
        or not isinstance(ledger.get("observed_sp500_month_closes"),list)):
        raise ValueError("Unsupported prospective freeze and ledger contract")
    closes=_market_closes(ledger,wallclock)
    forecasts=[]
    previous_month=None
    previous_forecast_time=None
    for record in ledger["original_v55_forecast_snapshots"]:
        f=_forecast(record,closes,wallclock)
        if (previous_month is not None and f["month"]<=previous_month or
            previous_forecast_time is not None and f["asof"]<=previous_forecast_time):
            raise ValueError("Prediction source records must be appended chronologically")
        previous_month=f["month"]
        previous_forecast_time=f["asof"]
        forecasts.append(f)
    events=[]
    for f in forecasts:
        nxt=month_after(f["month"])
        if nxt not in closes:
            continue
        c=closes[nxt]
        if c["retrieved"]<=f["asof"]:
            raise ValueError("Future month closure existed before allegedly prospective forecast")
        value=(c["close"]/f["initial_SP500_close"]-1)
        events.append({
            "month":f["month"],
            "matured_at":c["retrieved"],
            "label":value<=-LEARNING_THRESHOLD,
            "realized_next_month_SP500_close_return_pct":round(value*100,6),
            "raw_expert_risk":f["raw_expert_risk"],
        })
    replay=[]
    for f in forecasts:
        state=_learn(events,now=f["asof"])
        weights=state["prospective_five_expert_weights"]
        weighted=math.fsum(weights[k]*f["raw_expert_risk"][k] for k in SELECTED)
        replay.append({
            "month":f["month"],
            "prediction_created_at_utc":f["asof"].isoformat(),
            "five_frozen_experts":f["raw_expert_risk"],
            "original_frozen_median_shadow_not_AICS":f["frozen_V53_median"],
            "fixed_equal_mean_shadow_not_AICS":f["untrained_mean"],
            "prequential_bounded_adaptive_shadow_score_not_AICS":round(weighted,6),
            "only_previous_matured_label_weights":state,
            "next_month_outcome_used_to_make_this_forecast":False,
            "full_AICS":None,
            "trade_created":False,
        })
    latest=_learn(events,now=wallclock)
    matured=[x for x in events if x["matured_at"]<=wallclock]
    if len(events)!=len(matured):
        raise ValueError("Future month close masquerading as already matured")
    primary_10pct_status="NO_NEW_PROSPECTIVE_CRISIS_LABELS" if not matured else "NOT_TRAINED_ON_10PCT_CRISIS_LABELS"
    return {
        "schema":"aics-v56-genuine-future-only-research-feedback-learning-v1",
        "evaluation_as_of_utc":wallclock.isoformat(),
        "frozen_top_five_locked_contract":locked,
        "original_prospective_snapshot_count":len(forecasts),
        "original_forward_SP500_monthly_closes_count":len(closes),
        "matured_individual_1month_5pct_labels":len(matured),
        "adaptive_weights_currently_activated":latest["trained_using_matured_labels"],
        "latest_shadow_weight_state":latest,
        "base_five_expert_formulas_frozen_no_self_modification":True,
        "v53_original_frozen_median_unchanged":True,
        "training_update_rule":"exp(-0.5 * cumulative bounded ordinal squared error) mixed 75pct equal + 25pct adaptive",
        "training_not_authorized_until_min_12_labels_2_positive_episodes":True,
        "training_objective_secondary_1m_5pct_only":LEARNING_LABEL,
        "original_10pct_crisis_target_not_optimized":True,
        "historical_2000_2008_10pct_accuracy":None,
        "actual_PROSPECTIVE_future_10pct_validation":primary_10pct_status,
        "new_untouched_out_of_sample_forecast_accuracy_proven":None,
        "research_PIT_independent_provider_first_delivery_verified":False,
        "append_only_history_external_audit_confirmed":False,
        "original_11node_weights_1050_unchanged":True,
        "official_AICS_index":None,
        "trades_created":False,
        "forward_score_series":replay,
        "observed_matured_monthly_label_receipts":[
            {"forecast_month":x["month"],
             "label_matured_at_utc":x["matured_at"].isoformat(),
             "drawdown_at_least_5pct":x["label"],
             "realized_next_month_SP500_close_return_pct":x["realized_next_month_SP500_close_return_pct"]}
            for x in matured
        ],
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger",type=Path,default=INPUT)
    p.add_argument("--out",type=Path,default=OUTPUT)
    a=p.parse_args()
    if a.ledger.resolve()!=INPUT.resolve():
        raise ValueError("AICS prospective observations must use the official tracked research ledger")
    raw=a.ledger.read_bytes()
    payload=json.loads(raw)
    result=evaluate(payload)
    result["ledger_SHA256"]=hashlib.sha256(raw).hexdigest()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    summary={k:v for k,v in result.items()
             if k not in ("forward_score_series","observed_matured_monthly_label_receipts")}
    print(json.dumps(summary,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
