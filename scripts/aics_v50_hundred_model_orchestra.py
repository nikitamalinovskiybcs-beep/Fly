"""AICS V50 100-role model orchestra: model logic, not data collection.

10 squads x 10 deterministic, separately reported model-design experiments.
Every historical feature is drawn from the *existing* 24 actual monthly
retrospective research rows. Hypothetical score perturbations and unknown-node
endpoints are mathematical sensitivity tests, never fabricated market history.

The 11 node weights and official discrete hot multiplier stay unchanged;
the continuous hot multiplier is explicitly an unapproved shadow candidate.
All 24 incomplete months remain non-PIT-certified, no backfilled AICS, no
registered OOS forecast skill or automated trades.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS

SOURCE=Path("aics_data/research/aics_v18_private_credit_24m_pit_proxy_overlay_2026-11-22.json")
SPX=Path("aics_data/research/sp500_24_month_closes_2026-11-21.json")
OUT=Path("aics_data/research/aics_v50_hundred_model_orchestra_2026-11-22.json")
ENTRY=450.0
EXIT=500.0
HOT=60.0
assert len(WEIGHTS)==11 and sum(WEIGHTS.values())==1050


def _score(x):
    if isinstance(x,bool):
        raise ValueError("Boolean model observation")
    value=float(x)
    if not math.isfinite(value) or not 0<=value<=100:
        raise ValueError("Non-finite or out-of-bound observed research node score")
    return value


def discrete_multiplier(hot_count):
    return min(1.35,max(1.0,1.0+0.20*min(max(hot_count-2,0),1)+0.05*max(hot_count-3,0)))


def soft_hot(score,*,center=HOT,width=10.0):
    if not 0<width<=100 or not 0<=center<=100:
        raise ValueError("Invalid mathematical smoothing experiment")
    return min(1.0,max(0.0,(score-center+width/2)/width))


def continuous_multiplier(scores,*,center=HOT,width=10.0):
    activity=math.fsum(soft_hot(_score(s),center=center,width=width) for s in scores)
    return min(1.35,max(1.0,1.0+0.20*min(max(activity-2,0),1)+0.05*max(activity-3,0)))


def zone(low,high,entry=ENTRY,exit=EXIT):
    if entry>=exit or not (0<=low<=high<=1417.5+1e-8):
        raise ValueError("Invalid uncertainty interval or action thresholds")
    if high<entry:
        return "ROBUST_ENTRY_SHADOW_NOT_TRADE"
    if low>exit:
        return "ROBUST_CASH_SHADOW_NOT_TRADE"
    if low>=entry and high<=exit:
        return "ROBUST_WATCH_SHADOW_NOT_TRADE"
    return "ABSTAIN_SIGNAL_UNIDENTIFIED"


def bounds(observed, *,model="legacy",center=HOT,width=10.0,
           missing_upper_cap=100.0):
    """Exact monotone endpoints for unspecified node ranges, not imputation."""
    if not isinstance(observed,dict) or not set(observed).issubset(WEIGHTS):
        raise ValueError("Unknown node in original research panel")
    if not 0<=missing_upper_cap<=100:
        raise ValueError("Invalid upper-bound research assumption")
    known={n:_score(s) for n,s in observed.items()}
    missing=sorted(set(WEIGHTS)-set(known))
    low_raw=math.fsum(WEIGHTS[n]*s/100 for n,s in known.items())
    high_raw=low_raw+math.fsum(WEIGHTS[n]*missing_upper_cap/100 for n in missing)
    low_scores=list(known.values())+[0.0]*len(missing)
    high_scores=list(known.values())+[missing_upper_cap]*len(missing)
    if model=="legacy":
        low_hot=sum(x>HOT for x in low_scores)
        high_hot=sum(x>HOT for x in high_scores)
        low_mult=discrete_multiplier(low_hot)
        high_mult=discrete_multiplier(high_hot)
    elif model=="continuous":
        low_mult=continuous_multiplier(low_scores,center=center,width=width)
        high_mult=continuous_multiplier(high_scores,center=center,width=width)
    else:
        raise ValueError("Only the frozen old and continuous shadow model variants exist")
    return {
        "low":round(low_raw*low_mult,4),
        "high":round(high_raw*high_mult,4),
        "missing_nodes":missing,
        "missing_weight":sum(WEIGHTS[n] for n in missing),
        "known_weight":sum(WEIGHTS[n] for n in known),
        "known_nodes":len(known),
        "zero_or_100_missing_are_mathematical_extrema_not_observations":True,
    }


def pearson(a,b):
    if len(a)!=len(b) or len(a)<6:
        return None
    mx=math.fsum(a)/len(a)
    my=math.fsum(b)/len(b)
    xx=math.fsum((x-mx)**2 for x in a)
    yy=math.fsum((y-my)**2 for y in b)
    if xx<=0 or yy<=0:
        return None
    return round(math.fsum((x-mx)*(y-my) for x,y in zip(a,b))/math.sqrt(xx*yy),4)


def validate(v18,prices):
    if (v18.get("schema")!="aics-v18-24m-private-credit-original-sec-expost-research-overlay-v1"
        or v18.get("scores_are_expost_not_preregistered") is not True
        or v18.get("full_11node_index_months")!=0
        or v18.get("aics_sp500_spread_months")!=0
        or v18.get("trades_created") is not False
        or v18.get("historical_pit_source_bytes_independently_attested") is not False
        or prices.get("symbol")!="GSPC"
        or prices.get("independent_pit_verified") is not False):
        raise ValueError("Model research source unexpectedly certified or modified")
    months=v18.get("monthly_last_weekday_market_proxy",[])
    closes=prices.get("points",[])
    if (len(months)!=24 or len(closes)!=24 or
        [x["month"] for x in months]!=[x["month"] for x in closes] or
        months[0]["month"]!="2024-11" or months[-1]["month"]!="2026-10"):
        raise ValueError("No exact original observed 24-month model research window")
    result=[]
    for row,px in zip(months,closes):
        present=row["node_scores"]
        missing=row["missing_nodes"]
        if (row.get("full_aics") is not None
            or row.get("aics_sp500_spread") is not None
            or row.get("historical_pit_certified") is not False
            or not isinstance(present,dict)
            or not isinstance(missing,list)
            or set(present)&set(missing)
            or set(present)|set(missing)!=set(WEIGHTS)
            or len(missing)!=len(set(missing))
            or row["known_weight"]!=sum(WEIGHTS[n] for n in present)
            or row["known_node_count"]!=len(present)):
            raise ValueError("Incomplete source was erroneously promoted or distorted")
        cutoff=dt.date.fromisoformat(row["cutoff_date"])
        known={}
        for n,x in present.items():
            if dt.date.fromisoformat(x["research_eligible_date"])>cutoff:
                raise ValueError("Original candidate node used from the future")
            known[n]=_score(x["score"])
        p=float(px["sp500_month_end_close"])
        if not math.isfinite(p) or p<=0:
            raise ValueError("Nonpositive or non-finite observed S&P500 close")
        result.append({"month":row["month"],"known":known,"close":p,
                       "cutoff":row["cutoff_date"]})
    return result


def model_orchestra(v18,prices):
    rows=validate(v18,prices)
    scenarios=[]
    def assign(squad,role,params,result):
        assert len(scenarios)<100
        scenarios.append({
            "task_id":f"MODEL-{len(scenarios)+1:03d}",
            "squad":squad,
            "specialization":role,
            "parameters":params,
            "result":result,
            "execution":"COMPLETED_RESEARCH_MATHEMATICS_ONLY",
            "historical_PIT_forecast_accuracy":None,
            "production_change_approved":False,
        })
    original_bounds=[bounds(row["known"]) for row in rows]
    current_bounds=[bounds(row["known"],model="continuous") for row in rows]
    saved_discrete_cliff=(discrete_multiplier(3)-discrete_multiplier(2))*500
    if not math.isclose(saved_discrete_cliff,100.0):
        raise ValueError("Frozen legacy hot multiplier suddenly changed")
    epsilons=[0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1.0,2.0]

    # Squad 01: finite-size stress around the third-hot-node threshold.
    for eps in epsilons:
        lo=continuous_multiplier([100,100,HOT-eps])
        hi=continuous_multiplier([100,100,HOT+eps])
        diff=round((hi-lo)*500,6)
        assign("01_cliff_mechanics","threshold_crossing",{"epsilon":eps,"raw_fixed":500},
               {"official_legacy_cliff_points":100.0,
                "continuous_shadow_difference_points":diff,
                "shadow_reduction_pct":round(100*(1-diff/100),4)})

    # Squad 02: ten possible transition widths, no optimizing on outcomes.
    for width in range(2,21,2):
        lo=continuous_multiplier([100,100,59.9],width=float(width))
        hi=continuous_multiplier([100,100,60.1],width=float(width))
        assign("02_smooth_hotness_band","width_stress",{"bandwidth_points":width,"epsilon":0.1},
               {"small_threshold_crossing_shadow_change_points":round((hi-lo)*500,6),
                "original_legacy_0_1_crossing_change_points":100.0})

    # Squad 03: shift the not-yet-approved smooth center using REAL observed source nodes.
    for center in range(51,70,2):
        vals=[bounds(row["known"],model="continuous",center=float(center)) for row in rows]
        assign("03_hot_center_robustness","continuous_center_stress",
               {"center":center,"bandwidth":10},
               {"observed_months":len(vals),
                "mean_lower_endpoint_not_full_index":round(math.fsum(v["low"] for v in vals)/24,4),
                "months_with_robust_legacy_like_decision":
                    sum(zone(v["low"],v["high"])!="ABSTAIN_SIGNAL_UNIDENTIFIED" for v in vals)})

    # Squad 04: actual early / late historical monthly uncertainty-bound diagnoses.
    selected=[0,1,2,3,4,19,20,21,22,23]
    for index in selected:
        raw=original_bounds[index]
        shadow=current_bounds[index]
        assign("04_missing_node_envelopes","observed_month_bounds",
               {"source_month":rows[index]["month"]},
               {"missing_node_count":len(raw["missing_nodes"]),
                "missing_weight_out_of_1050":raw["missing_weight"],
                "legacy_interval":[raw["low"],raw["high"]],
                "continuous_shadow_interval":[shadow["low"],shadow["high"]],
                "decision_policy_result":zone(raw["low"],raw["high"])})

    # Squad 05: stress purely hypothetical limits on UNKNOWN scores, never fills history.
    for cap in range(10,101,10):
        envelope=[bounds(row["known"],missing_upper_cap=float(cap)) for row in rows]
        assign("05_missing_assumption_stress","unknown_score_upper_cap_counterfactual",
               {"max_unknown_score_assumption":cap,"is_observed_data":False},
               {"months":24,
                "ambiguous_decisions":sum(zone(v["low"],v["high"])=="ABSTAIN_SIGNAL_UNIDENTIFIED" for v in envelope),
                "mean_interval_width":round(math.fsum(v["high"]-v["low"] for v in envelope)/24,4)})

    # Squad 06: threshold robustness; official 450/500 remain frozen.
    for trial_exit in range(460,551,10):
        assign("06_policy_threshold_sensitivity","exit_threshold_counterfactual",
               {"official_entry_unchanged":450,"hypothetical_exit":trial_exit},
               {"months":24,
                "robust_cash_months":sum(zone(v["low"],v["high"],exit=trial_exit)=="ROBUST_CASH_SHADOW_NOT_TRADE" for v in original_bounds),
                "robust_entry_months":sum(zone(v["low"],v["high"],exit=trial_exit)=="ROBUST_ENTRY_SHADOW_NOT_TRADE" for v in original_bounds),
                "abstention_months":sum(zone(v["low"],v["high"],exit=trial_exit)=="ABSTAIN_SIGNAL_UNIDENTIFIED" for v in original_bounds)})

    # Prepare one ORIGINAL first-month cohort, never survivor-selected from future.
    fixed=tuple(sorted(rows[0]["known"]))
    fixed_weight=sum(WEIGHTS[n] for n in fixed)
    risks=[math.fsum(WEIGHTS[n]*r["known"][n] for n in fixed)/fixed_weight
           if all(n in r["known"] for n in fixed) else None for r in rows]
    targets=[(rows[i+1]["close"]/rows[i]["close"]-1)*100 for i in range(23)]
    # Squad 07: ten consecutive trailing means vs next observed month S&P500;
    # all correlations are hindsight diagnostics, not selected model improvements.
    for window in range(1,11):
        xs=[];ys=[]
        for i in range(23):
            if i+1<window:
                continue
            fragment=risks[i-window+1:i+1]
            if any(x is None for x in fragment):
                continue
            xs.append(math.fsum(fragment)/window)
            ys.append(targets[i])
        assign("07_next_month_target_falsification","fixed_cohort_lag_diagnostic",
               {"trailing_observation_months":window,"selected_before_looking_at_outcome":False},
               {"retrospective_real_return_pairs":len(xs),
                "pearson_expost_not_OOS":pearson(xs,ys),
                "ex_ante_PIT_validated":False,
                "do_not_select_best_correlation":True})

    # Squad 08: exploratory persistence of fixed first-month cohort, never AICS band.
    for persistence in range(1,11):
        active=0;alarms=0;episodes=0
        previous=False
        for risk in risks:
            active=active+1 if risk is not None and risk>=35 else 0
            triggered=active>=persistence
            if triggered:
                alarms+=1
                if not previous:
                    episodes+=1
            previous=triggered
        assign("08_chattering_resistance","fixed_cohort_alarm_persistence_study",
               {"consecutive_observed_months":persistence,
                "normalized_fixed_cohort_alarm_threshold":35,
                "is_official_AICS_signal":False},
               {"research_only_alarms":alarms,"research_only_episodes":episodes,
                "observed_source_months":24})

    # Squad 09: ten specified frozen node weights undergo +1 point mathematical
    # local perturbations ONLY WHEN that node was actually observed.
    for node in list(WEIGHTS)[:10]:
        deltas=[]
        for row,b in zip(rows,original_bounds):
            if node not in row["known"] or row["known"][node]>99:
                continue
            moved=dict(row["known"]);moved[node]+=1
            next_bound=bounds(moved)
            deltas.append(next_bound["low"]-b["low"])
        assign("09_node_weight_and_local_sensitivity","one_point_node_counterfactual",
               {"node":node,"official_weight":WEIGHTS[node],
                "perturbation_score_points":1,"is_observed_new_event":False},
               {"months_with_existing_original_candidate_node":len(deltas),
                "max_lower_bound_shift_due_to_one_point":round(max(deltas),4) if deltas else None,
                "mean_lower_bound_shift":round(math.fsum(deltas)/len(deltas),4) if deltas else None})

    # Squad 10: model quality / no-lookahead / no-fake-signal constraints.
    validations=[
        ("eleven_weights_immutable",len(WEIGHTS)==11 and sum(WEIGHTS.values())==1050),
        ("official_thresholds_450_500_frozen",ENTRY==450 and EXIT==500),
        ("all_24_months_original",len(rows)==24),
        ("zero_full_AICS_months",v18["full_11node_index_months"]==0),
        ("zero_historical_PIT_promotions",v18["historical_pit_source_bytes_independently_attested"] is False),
        ("no_fabricated_missing_node_scores",all(len(b["missing_nodes"])>0 for b in original_bounds)),
        ("original_one_month_forward_prices_not_features",len(targets)==23 and all(math.isfinite(x) for x in targets)),
        ("continuous_multiplier_monotone",all(continuous_multiplier([100,100,float(i)])<=
                                             continuous_multiplier([100,100,float(i+1)]) for i in range(100))),
        ("original_legacy_cliff_quantified",math.isclose(saved_discrete_cliff,100.0)),
        ("no_production_or_trading_authorization",v18["trades_created"] is False and
                                                  v18["production_index_changed"] is False),
    ]
    for name,passed in validations:
        if not passed:
            raise ValueError("MODEL orchestra safety invariant failed: "+name)
        assign("10_adversarial_governance","hard_invariant_gate",
               {"invariant":name},
               {"passed":True,"production_status":"RESEARCH_ONLY"})
    counts={}
    for scenario in scenarios:
        counts[scenario["squad"]]=counts.get(scenario["squad"],0)+1
    if (len(scenarios)!=100 or len({x["task_id"] for x in scenarios})!=100
        or len(counts)!=10 or any(v!=10 for v in counts.values())):
        raise ValueError("100 unique model experiment assignments were not completed")
    official_labels=[zone(x["low"],x["high"]) for x in original_bounds]
    shadow_labels=[zone(x["low"],x["high"]) for x in current_bounds]
    last=original_bounds[-1];last_soft=current_bounds[-1]
    return {
        "schema":"aics-v50-100-model-experiment-orchestra-v1",
        "model_iteration":"V50_MODEL_ARCHITECTURE_SHADOW",
        "as_of":"2026-11-22",
        "actual_deterministic_model_experiments_executed":100,
        "model_experiment_squads":counts,
        "separately_trained_AI_agents_started":0,
        "observed_months_evaluated":len(rows),
        "original_11_node_weights_total":1050,
        "original_11_node_weights_changed":False,
        "original_450_500_threshold_policy_changed":False,
        "original_discrete_hot_multiplier_changed":False,
        "legacy_hot_third_node_cliff_points_at_raw_500":saved_discrete_cliff,
        "continuous_shadow_10wide_third_hot_cliff_points_at_0_1_epsilon":
            round((continuous_multiplier([100,100,60.1])-
                   continuous_multiplier([100,100,59.9]))*500,6),
        "shadow_candidate":"SMOOTH_HOT_NODE_ACTIVITY_PLUS_EVIDENCE_INTERVAL_ABSTENTION",
        "fixed_first_observed_month_source_cohort":list(fixed),
        "fixed_source_cohort_weight":fixed_weight,
        "monthly_historical_partial_source_coverages":{
            "first_month_weight":original_bounds[0]["known_weight"],
            "last_month_weight":last["known_weight"],
        },
        "last_observed_month":rows[-1]["month"],
        "last_month_unknown_nodes":last["missing_nodes"],
        "last_month_exact_legacy_mathematical_interval_NOT_AICS":[last["low"],last["high"]],
        "last_month_continuous_shadow_interval_NOT_AICS":[last_soft["low"],last_soft["high"]],
        "official_legacy_model_envelope_ambiguous_months":
            sum(x=="ABSTAIN_SIGNAL_UNIDENTIFIED" for x in official_labels),
        "continuous_shadow_model_envelope_ambiguous_months":
            sum(x=="ABSTAIN_SIGNAL_UNIDENTIFIED" for x in shadow_labels),
        "unambiguous_legacy_decision_months":
            sum(x!="ABSTAIN_SIGNAL_UNIDENTIFIED" for x in official_labels),
        "smoothing_proven_out_of_sample_forecast_improvement":None,
        "backtest_accuracy_improvement":None,
        "independent_historical_24_month_PIT_forecast_accuracy":None,
        "full_11_node_AICS":None,
        "certified_AICS_nodes":0,
        "production_signal":None,
        "trades_created":False,
        "honest_result":"Improved diagnosability and mathematical continuity, not proven predictive skill",
        "monthly_original_model_robustness":[
            {
                "month":r["month"],
                "observed_nodes":a["known_nodes"],
                "observed_weight":a["known_weight"],
                "unobserved_weight":a["missing_weight"],
                "legacy_range_NOT_AICS":[a["low"],a["high"]],
                "continuous_shadow_range_NOT_AICS":[b["low"],b["high"]],
                "legacy_policy_identifiability":lab,
                "continuous_shadow_identifiability":sh,
            }
            for r,a,b,lab,sh in zip(rows,original_bounds,current_bounds,
                                     official_labels,shadow_labels)],
        "100_model_experiments":scenarios,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,default=SOURCE)
    p.add_argument("--sp500",type=Path,default=SPX)
    p.add_argument("--out",type=Path,default=OUT)
    args=p.parse_args()
    report=model_orchestra(
        json.loads(args.source.read_text(encoding="utf-8")),
        json.loads(args.sp500.read_text(encoding="utf-8"))
    )
    report["input_sha256"]={
        str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in (args.source,args.sp500)
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items()
                      if k not in ("100_model_experiments","monthly_original_model_robustness")}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
