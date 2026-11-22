"""AICS V57: 10,000 REAL computations of a five-model research ensemble.

The data are eight REAL, formerly observed training-label pairs from the
existing 2024-2026 ex-post SEC/S&P research panel. The original five V53
experts are locked by Git blob in V55; do not change them.

10,000 gradient steps are NOT 10,000 new examples or 10,000 independently
trained agents. An additional eight leave-one-training-month-out checks use
only the same eight historical labels. The subsequent nine observed source
months are evaluated only after the weights have been fitted. Both the
algorithms AND the split were designed after these outcomes were known:
the later period is NOT untouched prospective OOS.

Loss is a NON-PROBABILISTIC squared ordinal risk surrogate. Risk/100 is not
a calibrated chance of future S&P drawdown. No official AICS, crisis forecast
skill, production weights or trading action can be promoted from this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from scripts.aics_v51_credit_magnitude_early_warning import (
    ORIGINAL, V18, SPX, build as v51_build
)
from scripts.aics_v53_hundred_model_top5_ensemble import run as v53_run
from scripts.aics_v54_chronological_top5_debias import sources, split_months, auc
from scripts.aics_v55_forward_prospective_conductor import (
    FROZEN, SELECTED, validate_freeze
)
from scripts.aics_score_reproducibility_gate import WEIGHTS

OUTPUT=Path("aics_data/research/aics_v57_ten_thousand_real_gradient_steps_2026-11-22.json")
TRAIN_CUTOFF="2025-10"
HORIZON=1
SECONDARY_DRAWDOWN_PCT=5
STEPS=10000
LEARNING_RATE=0.10
RIDGE_TO_EQUAL_VOTES=0.5
MIN_W=0.15
MAX_W=0.40
LOO_STEPS=1000
EPS=1e-10

def _project_simplex(v):
    """Exact capped-simplex projection, 5 fixed experts, weights sum to 1."""
    if len(v)!=5 or any(not math.isfinite(x) for x in v):
        raise ValueError("Five finite expert weights required")
    if 5*MIN_W>1 or 5*MAX_W<1:
        raise ValueError("Bounded simplex is mathematically infeasible")
    low=min(v)-MAX_W
    high=max(v)-MIN_W
    for _ in range(64):
        midpoint=(low+high)/2
        mass=math.fsum(min(MAX_W,max(MIN_W,x-midpoint)) for x in v)
        if mass>1:
            low=midpoint
        else:
            high=midpoint
    midpoint=(low+high)/2
    result=[min(MAX_W,max(MIN_W,x-midpoint)) for x in v]
    if abs(math.fsum(result)-1)>1e-10:
        raise ValueError("Gradient learner projection did not conserve 100% weight")
    return result

def _observations(v51,v53):
    validate_freeze(json.loads(FROZEN.read_text(encoding="utf-8")))
    months, vectors, models, closes, old, severity, market=sources(v53,v51)
    if len(months)!=18 or len(vectors)!=100:
        raise ValueError("Original real monthly research panel changed")
    if len(set(SELECTED))!=5 or not all(mid in vectors for mid in SELECTED):
        raise ValueError("Unfrozen five-expert roster")
    train, later=split_months(months,closes,HORIZON,cutoff=TRAIN_CUTOFF)
    if (len(train)!=8 or len(later)!=9 or
        sum(y for _,y in train)!=1 or sum(y for _,y in later)!=1):
        raise ValueError("Retrospective source split differs from V54")
    data=[]
    for split,records in (("earlier",train),("later",later)):
        for i,label in records:
            features=[vectors[m][i]/100 for m in SELECTED]
            if not all(0<=a<=1 and math.isfinite(a) for a in features):
                raise ValueError("An original model contains an out-of-bound risk")
            data.append({"month":months[i],"split":split,
                         "risk_by_frozen_expert":features,
                         "observed_real_drawdown_5pct_label":bool(label),
                         "legacy":old[months[i]]/100,
                         "market":min(1,max(0,market[months[i]]/100))})
    return data,months,closes

def _predict(weights,features):
    return math.fsum(weights[i]*features[i] for i in range(5))

def _loss(rows,weights):
    if not rows:
        raise ValueError("Historical training rows missing")
    return math.fsum((_predict(weights,r["risk_by_frozen_expert"])
                      -float(r["observed_real_drawdown_5pct_label"]))**2
                     for r in rows)/len(rows)

def _fit(rows,steps=STEPS):
    if steps<1 or steps>STEPS or not rows:
        raise ValueError("Unbounded or empty model training is not permitted")
    equal=[0.2]*5
    w=list(equal)
    trace=[]
    for step in range(steps):
        prediction=[_predict(w,r["risk_by_frozen_expert"])-
                    float(r["observed_real_drawdown_5pct_label"])
                    for r in rows]
        grad=[(2/len(rows))*math.fsum(prediction[k]*
                   rows[k]["risk_by_frozen_expert"][j] for k in range(len(rows)))+
                   2*RIDGE_TO_EQUAL_VOTES*(w[j]-equal[j])
              for j in range(5)]
        w=_project_simplex([w[j]-LEARNING_RATE*grad[j] for j in range(5)])
        if (step+1)%1000==0:
            trace.append({"optimizer_step":step+1,
                          "train_real_observations_NOT_new_examples":len(rows),
                          "research_only_squared_ordinal_surrogate":round(_loss(rows,w),9),
                          "weights":[round(x,9) for x in w]})
    return w,trace

def _roc(rows,values):
    if len(rows)!=len(values):
        raise ValueError("Unpaired actual source outcomes")
    return auc(values,[r["observed_real_drawdown_5pct_label"] for r in rows])

def _metrics(rows,weights):
    prediction=[_predict(weights,r["risk_by_frozen_expert"]) for r in rows]
    original_equal=[_predict([0.2]*5,r["risk_by_frozen_expert"]) for r in rows]
    original_median=[median(r["risk_by_frozen_expert"]) for r in rows]
    baseline=[r["legacy"] for r in rows]
    market=[r["market"] for r in rows]
    def mse(v):
        return round(math.fsum((p-float(r["observed_real_drawdown_5pct_label"]))**2
                               for p,r in zip(v,rows))/len(rows),9)
    return {
        "real_observed_label_months":len(rows),
        "positive_months":sum(r["observed_real_drawdown_5pct_label"] for r in rows),
        "learner_auc_EXPOST":round(_roc(rows,prediction),6),
        "original_equal_auc_EXPOST":round(_roc(rows,original_equal),6),
        "original_robust_median_auc_EXPOST":round(_roc(rows,original_median),6),
        "legacy_credit_auc_EXPOST":round(_roc(rows,baseline),6),
        "lagged_market_auc_EXPOST":round(_roc(rows,market),6),
        "learner_bounded_ordinal_squared_surrogate":mse(prediction),
        "original_equal_bounded_ordinal_squared_surrogate":mse(original_equal),
        "original_median_bounded_ordinal_squared_surrogate":mse(original_median),
        "not_calibrated_crisis_probability":True,
    }

def build(v51,v53):
    if (v51["full_11node_AICS"] is not None or
        v53["approved_live_AICS_index"] is not None or
        v53["new_model_superior_forecast_skill_proven"] is not None):
        raise ValueError("Never optimize a promoted AICS index")
    records,months,closes=_observations(v51,v53)
    train=[r for r in records if r["split"]=="earlier"]
    later=[r for r in records if r["split"]=="later"]
    if len(train)!=8 or len(later)!=9 or len(records)!=17:
        raise ValueError("Retrospective training is not allowed to move train/test cut")
    weights,trace=_fit(train)
    loow=[]
    for i,r in enumerate(train):
        fit,_=_fit(train[:i]+train[i+1:],steps=LOO_STEPS)
        loow.append({
            "omitted_original_training_month":r["month"],
            "remaining_original_training_pairs":len(train)-1,
            "research_weight_l1_distance_from_full_fit":
                round(math.fsum(abs(a-b) for a,b in zip(fit,weights)),9),
            "holdback_5pct_event":r["observed_real_drawdown_5pct_label"],
        })
    train_stats=_metrics(train,weights)
    later_stats=_metrics(later,weights)
    observed_later_worse=(
        later_stats["learner_bounded_ordinal_squared_surrogate"]>
        later_stats["original_equal_bounded_ordinal_squared_surrogate"]+EPS
    )
    rejected=True  # Post-hoc model-design source cannot be production-promoted.
    return {
        "schema":"aics-v57-ten-thousand-real-history-gradient-steps-research-v1",
        "model":"V57_10K_GRADIENT_RESEARCH_ONLY",
        "research_date":"2026-11-22",
        "actual_gradient_optimization_steps_executed":STEPS,
        "additional_leave_one_month_out_research_fit_steps":8*LOO_STEPS,
        "optimizer_steps_are_repeated_training_on_same_8_real_examples":True,
        "number_of_new_market_observations_generated":0,
        "number_of_new_real_prospective_forecasts":0,
        "separate_autonomous_trained_AI_agents_created":0,
        "frozen_five_ids":list(SELECTED),
        "model_weights_trained_on_historical_eight_real_train_labels":{
            k:round(weights[i],10) for i,k in enumerate(SELECTED)
        },
        "frozen_5_model_code_unchanged":True,
        "source_from_retrospective_2024_2026_original_observations":True,
        "model_and_2025_10_split_chosen_AFTER_history_observed":True,
        "this_does_NOT_establish_untouched_OOS_skill":True,
        "training_month_count":len(train),
        "later_month_count":len(later),
        "training_positive_label_months":train_stats["positive_months"],
        "later_positive_label_months":later_stats["positive_months"],
        "train_5pct_model_comparison":train_stats,
        "later_5pct_model_comparison":later_stats,
        "later_trained_model_squared_surrogate_worse_than_equal_baseline":observed_later_worse,
        "optimization_research_only_not_deployable_regardless_in_sample_or_later_result":rejected,
        "leave_one_real_training_month_out_weight_sensitivity":loow,
        "maximum_l1_weight_instability_omitting_one_training_month":
            max(x["research_weight_l1_distance_from_full_fit"] for x in loow),
        "optimizer_trace_every_1000_steps":trace,
        "the_new_weights_supersede_live_V56_equal_weights":False,
        "current_true_prospective_learning_weights_remain_equal":{k:0.2 for k in SELECTED},
        "10pct_crisis_warning_accuracy":None,
        "whole_11node_index":None,
        "independently_verified_historical_PIT_nodes":0,
        "production_AICS_weights_changed":False,
        "official_hot_multiplier_or_thresholds_changed":False,
        "trades_created":False,
        "decision":"Research model fitter executed, but historical eight-label training cannot justify deployment; continue V56 future-only learner without backfill.",
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=OUTPUT)
    a=p.parse_args()
    raw=[json.loads(p.read_text(encoding="utf-8")) for p in (ORIGINAL,V18,SPX)]
    v51=v51_build(*raw)
    v53=v53_run(v51)
    result=build(v51,v53)
    result["original_source_sha256"]={
        str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ORIGINAL,V18,SPX,FROZEN)
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary={k:v for k,v in result.items()
             if k not in ("optimizer_trace_every_1000_steps","leave_one_real_training_month_out_weight_sensitivity")}
    print(json.dumps(summary,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
