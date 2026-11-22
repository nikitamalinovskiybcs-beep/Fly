"""AICS V59: sharp, conditional 24-month interval for a MISSING 11-node score.

This is a robust missing-data IDENTIFICATION envelope, not a probability
interval, a posterior estimate, a new score or an AICS trade signal. The 11
node weights and hot multiplier remain EXACTLY as in official score gate.
The source is original ex-post V18 proxy research; no independent historical
provider-first-delivery PIT certification exists. Never promote these bounds
to an independently verified time series, and never fill a missing node with
a fabricated score.

For each month conditional on the observed V18 nodes, all unobserved nodes
can take any score in [0,100]. The official raw weighted sum and hot-node
multiplier are monotone nondecreasing in each node's score. Thus BOTH ends
of the displayed feasible interval are attained by setting all missing
nodes to the respective mathematical boundary 0/100. Those are boundary
CASES for proof, NOT newly manufactured observations.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS

SOURCE=Path("aics_data/research/aics_v18_private_credit_24m_pit_proxy_overlay_2026-11-22.json")
OUT=Path("aics_data/research/aics_v59_24m_pit_uncertainty_envelope_2026-11-22.json")
D=lambda x: Decimal(str(x))
TOTAL=1050
ONE=D("1")
ZERO=D("0")
HUNDRED=D("100")
HOT=D("60")
MIN_MULT=ONE
MAX_MULT=D("1.35")
ENTRY=D("450")
EXIT=D("500")
assert len(WEIGHTS)==11 and sum(WEIGHTS.values())==TOTAL


def multiplier(h):
    if type(h)!=int or h<0 or h>len(WEIGHTS):
        raise ValueError("Invalid count of hot score nodes")
    return min(MAX_MULT,max(MIN_MULT,
        ONE + D("0.20")*min(max(h-2,0),1)+D("0.05")*max(0,h-3)))


def exact_score(raw):
    if type(raw) not in (str,int,float,Decimal):
        raise ValueError("Source score must be a real numeric score")
    try:
        x=D(raw)
    except (InvalidOperation,ValueError) as exc:
        raise ValueError("Source score could not be parsed") from exc
    if not x.is_finite() or not ZERO<=x<=HUNDRED:
        raise ValueError("Source score outside [0,100]")
    return x


def _f(value):
    return float(value)


def _r2(value):
    return _f(value.quantize(D("0.01"),rounding=ROUND_HALF_UP))


def _region(low,high):
    if high<ENTRY:
        return "CERTAIN_ENTER_IF_RESEARCH_PROXY_VALID"
    if low>EXIT:
        return "CERTAIN_EXIT_IF_RESEARCH_PROXY_VALID"
    if low>=ENTRY and high<=EXIT:
        return "CERTAIN_WATCH_IF_RESEARCH_PROXY_VALID"
    return "UNDECIDABLE_INCOMPLETE_NODE_COVERAGE"


def _what_if_one_known(raw,h,missing,node):
    """Maximum residual width after obtaining ONE currently unknown node.

    At fixed node x∈[0,100], set all remaining missing nodes to 0 vs 100.
    Width is piecewise linear, nondecreasing on each side of hot threshold.
    The branch maxima occur at x=60 (not hot) or x=100 (hot).
    """
    weight=WEIGHTS[node]
    rest=missing-{node}
    rest_weight=sum(WEIGHTS[x] for x in rest)
    residual=[]
    for score in (ZERO,HOT,HUNDRED):
        hot=h+int(score>HOT)
        r=raw+D(weight)*score/HUNDRED
        low=r*multiplier(hot)
        high=(r+D(rest_weight))*multiplier(hot+len(rest))
        residual.append({
            "hypothetical_assumed_node_score_for_BOUND_ONLY":_f(score),
            "residual_full_index_width":_r2(high-low),
            "residual_width_exact":str(high-low),
            "residual_lower_exact":str(low),
            "residual_upper_exact":str(high)
        })
    max_residual=max(D(v["residual_width_exact"]) for v in residual)
    return max_residual,residual


def month_bound(row):
    if not isinstance(row,dict) or not isinstance(row.get("node_scores"),dict):
        raise ValueError("No original research month scored nodes")
    month=row.get("month")
    cutoff=row.get("cutoff_date")
    try:
        year,mm=map(int,month.split("-"))
        expected=dt.date.fromisoformat(cutoff)
    except (TypeError,ValueError) as exc:
        raise ValueError("Malformed month / publication cutoff") from exc
    if len(month)!=7 or expected.year!=year or expected.month!=mm:
        raise ValueError("Research month cutoff mismatch")
    known=row["node_scores"]
    missing=row.get("missing_nodes")
    if not isinstance(missing,list) or len(set(missing))!=len(missing):
        raise ValueError("Invalid list of unknown scored nodes")
    if set(known)&set(missing) or set(known)|set(missing)!=set(WEIGHTS):
        raise ValueError("V18 must partition exactly 11 frozen AICS nodes")
    if (row.get("known_node_count")!=len(known) or
        row.get("known_weight")!=sum(WEIGHTS[name] for name in known)):
        raise ValueError("Known research node coverage changed")
    raw=ZERO
    hot=0
    for name,record in known.items():
        if not isinstance(record,dict):
            raise ValueError("Invalid individual research node")
        score=exact_score(record.get("score"))
        raw+=D(WEIGHTS[name])*score/HUNDRED
        hot+=int(score>HOT)
        try:
            published=dt.date.fromisoformat(record["research_eligible_date"])
        except (KeyError,ValueError,TypeError) as exc:
            raise ValueError("Unavailable known original research publication date") from exc
        if published>expected:
            raise ValueError("Future look-ahead research node score in prior month")
    try:
        published_raw=D(row.get("partial_weighted_points_not_full_aics"))
    except (TypeError,InvalidOperation,ValueError) as exc:
        raise ValueError("Invalid original partial weighted score") from exc
    if not published_raw.is_finite() or not ZERO<=published_raw<=D(TOTAL):
        raise ValueError("Original raw index contribution out of range")
    if abs(raw-published_raw)>D("0.01"):
        raise ValueError("Original displayed partial score differs from raw input")
    missing_set=set(missing)
    missing_weight=sum(WEIGHTS[name] for name in missing_set)
    low=raw*multiplier(hot)
    high=(raw+D(missing_weight))*multiplier(hot+len(missing))
    if not low<=high:
        raise ValueError("Official hot multipliers have violated monotone bounds")
    if missing_set and _region(low,high)!="UNDECIDABLE_INCOMPLETE_NODE_COVERAGE":
        # This row could still have a conclusive robust threshold if the source
        # bounds lie entirely inside a single trading category.
        pass
    conditional_unknowns=[]
    for node in missing:
        max_remaining,branches=_what_if_one_known(raw,hot,missing_set,node)
        guarantee=(high-low)-max_remaining
        if guarantee < -D("0.00000001"):
            raise ValueError("Resolving a missing node worsened the robust interval")
        conditional_unknowns.append({
            "unobserved_node":node,
            "fixed_weight":WEIGHTS[node],
            "worst_case_residual_interval_width_if_THIS_NODE_FIRST_RESOLVED":_r2(max_remaining),
            "guaranteed_at_least_interval_width_reduction_if_resolved":_r2(guarantee),
            "note":"Boundary sensitivity only, NOT a score and NOT guaranteed PIT collection",
            "endpoint_and_hot_boundary_scenarios":branches
        })
    priority=sorted(conditional_unknowns,
                    key=lambda x:(-x["guaranteed_at_least_interval_width_reduction_if_resolved"],
                                  -x["fixed_weight"],x["unobserved_node"]))
    return {
        "month":month,
        "cutoff_date":cutoff,
        "known_node_count":len(known),
        "missing_node_count":len(missing),
        "known_weight":row["known_weight"],
        "missing_weight":missing_weight,
        "known_weight_coverage_percent":round(row["known_weight"]/TOTAL*100,2),
        "observed_partial_weighted_sum_not_full_index":_r2(raw),
        "observed_partial_weighted_sum_exact":str(raw),
        "known_hot_nodes_strict_gt_60":hot,
        "lower_bound_hot_multiplier":_f(multiplier(hot)),
        "upper_bound_hot_multiplier":_f(multiplier(hot+len(missing))),
        "conditional_full_index_lower_if_all_missing_scores_ZERO_BOUND_CASE":_r2(low),
        "conditional_full_index_upper_if_all_missing_scores_100_BOUND_CASE":_r2(high),
        "conditional_index_lower_exact":str(low),
        "conditional_index_upper_exact":str(high),
        "conditional_interval_width":_r2(high-low),
        "conditional_interval_width_exact":str(high-low),
        "entry_450_watch_500_cash_threshold_identification":_region(low,high),
        "feasible_both_under_450_and_over_500":low<ENTRY and high>EXIT,
        "missing_nodes_not_imputed":missing,
        "missing_node_identification_priorities":priority,
        "full_11_node_AICS":None,
        "independently_historical_PIT_verified":False,
        "strict_trade_action":None,
        "note":"Ex-post source-conditional mathematical bounds, NOT true AICS observations"
    }


def build(source):
    if (source.get("schema")!="aics-v18-24m-private-credit-original-sec-expost-research-overlay-v1"
        or source.get("scores_are_expost_not_preregistered") is not True
        or source.get("historical_pit_source_bytes_independently_attested") is not False
        or source.get("full_11node_index_months")!=0
        or source.get("aics_sp500_spread_months")!=0
        or source.get("production_index_changed") is not False
        or source.get("trades_created") is not False
        or sum(WEIGHTS.values())!=TOTAL):
        raise ValueError("Never treat ex-post V18 as PIT-certified official AICS")
    market=source.get("monthly_last_weekday_market_proxy")
    if not isinstance(market,list) or len(market)!=24:
        raise ValueError("V59 must preserve exactly the 24 real source months")
    records=[]
    for j,row in enumerate(market):
        expected_year=2024+(10+j)//12
        expected_month=(10+j)%12+1
        expected=f"{expected_year:04d}-{expected_month:02d}"
        if row.get("month")!=expected:
            raise ValueError("Missing or reordered research months are not imputed")
        records.append(month_bound(row))
    classifications={}
    for record in records:
        label=record["entry_450_watch_500_cash_threshold_identification"]
        classifications[label]=classifications.get(label,0)+1
    robust_directions=[]
    for prev,curr in zip(records,records[1:]):
        lo0=D(prev["conditional_index_lower_exact"])
        hi0=D(prev["conditional_index_upper_exact"])
        lo1=D(curr["conditional_index_lower_exact"])
        hi1=D(curr["conditional_index_upper_exact"])
        status=("CERTAIN_RISE" if lo1>hi0 else
                "CERTAIN_FALL" if hi1<lo0 else
                "CHANGE_DIRECTION_UNDETERMINED")
        robust_directions.append({
            "from_month":prev["month"],"to_month":curr["month"],
            "direction":status,
        })
    if any(x["full_11_node_AICS"] is not None for x in records):
        raise ValueError("AICS index promoted without 11 PIT nodes")
    latest=records[-1]
    return {
        "schema":"aics-v59-24m-sharp-conditional-AICS-uncertainty-envelope-v1",
        "as_of":"2026-11-22",
        "original_source_schema":source["schema"],
        "research_proxy_not_real_historical_pit":True,
        "mathematical_monotone_interval_proof":
            "AICS(raw,h) is nondecreasing in every 0-100 node score; extrema occur at all unknown scores = 0 or all = 100. Unknowns are NOT observed or imputed.",
        "original_11_weights_total":1050,
        "hot_threshold_exclusive_greater_than":60,
        "original_multiplier_cap":1.35,
        "entry_if_strictly_below":450,
        "watch_from_450_through_500_inclusive":True,
        "exit_to_cash_if_strictly_above":500,
        "original_24_market_months":len(records),
        "months_with_certified_full_11_node_AICS":0,
        "months_with_unique_robust_trading_regime":sum(
            x["entry_450_watch_500_cash_threshold_identification"]!="UNDECIDABLE_INCOMPLETE_NODE_COVERAGE"
            for x in records),
        "months_with_risk_both_below_entry_and_above_exit":sum(
            x["feasible_both_under_450_and_over_500"] for x in records),
        "regime_classification_counts":classifications,
        "adjacent_research_months_with_certain_direction":sum(
            x["direction"]!="CHANGE_DIRECTION_UNDETERMINED"
            for x in robust_directions),
        "most_recent_month":latest["month"],
        "most_recent_conditional_index_interval":[
            latest["conditional_full_index_lower_if_all_missing_scores_ZERO_BOUND_CASE"],
            latest["conditional_full_index_upper_if_all_missing_scores_100_BOUND_CASE"]],
        "most_recent_top_missing_node_to_resolve_for_robust_interval":
            latest["missing_node_identification_priorities"][0]["unobserved_node"],
        "historical_11node_AICS":None,
        "independently_PIT_certified_11node_history":False,
        "no_24month_missing_source_data_fabricated":True,
        "no_probability_or_confidence_interval_claimed":True,
        "official_multiplier_weights_and_450_500_policy_unchanged":True,
        "production_trades_created":False,
        "monthly_24m_conditional_research_envelopes":records,
        "monthly_changes_without_false_identification":robust_directions,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,default=SOURCE)
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    if a.source.resolve()!=SOURCE.resolve():
        raise ValueError("Unknown substituted source for fixed 24-month study")
    raw=a.source.read_bytes()
    source=json.loads(raw)
    result=build(source)
    result["original_source_sha256"]=hashlib.sha256(raw).hexdigest()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "months":result["original_24_market_months"],
        "certified_AICS_months":result["months_with_certified_full_11_node_AICS"],
        "certain_regime_months":result["months_with_unique_robust_trading_regime"],
        "certain_direction_month_pairs":result["adjacent_research_months_with_certain_direction"],
        "latest_conditional_interval":result["most_recent_conditional_index_interval"],
        "highest_uncertainty_reduction_missing_node":result[
            "most_recent_top_missing_node_to_resolve_for_robust_interval"],
        "crisis_predictions_proven":False,
        "official_AICS":result["historical_11node_AICS"],
        "trades":result["production_trades_created"],
    },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
