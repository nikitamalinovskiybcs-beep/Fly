"""AICS V54 — chronological cutoff and five-expert de-duplication.

Refutes false top-five forecast skill after 100 candidate search by rebuilding
research selections from only labels actually observable at the 2025-10 cutoff.

Both the 100 formulas and 2025-10 split were proposed retrospectively in
November 2026. THIS IS NOT UNTOUCHED OOS or prospective validation.
The sample has one early (train) and one later (test) market drawdown EPISODE,
with 1/2 positive label months; all ROC-AUC outputs are descriptive.

Reuse exactly the previously executed 100 V53 model risk series with historical
source-family coverage, never fill 3 missing latest months, change official
weights, compute full AICS or execute trades.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from scripts.aics_v51_credit_magnitude_early_warning import ORIGINAL,V18,SPX,build as v51_build
from scripts.aics_v53_hundred_model_top5_ensemble import run as v53_run
from scripts.aics_score_reproducibility_gate import WEIGHTS

OUT=Path("aics_data/research/aics_v54_chronological_top5_debias_2026-11-22.json")
CUTOFF="2025-10"
HORIZONS=(1,3,6)
DRAWDOWN=5.0
DEDUPE_ABS_PEARSON=0.80


def auc(values, labels):
    if len(values)!=len(labels):
        raise ValueError("Unpaired scores/labels")
    yes=[float(x) for x,b in zip(values,labels) if b is True]
    no=[float(x) for x,b in zip(values,labels) if b is False]
    if not yes or not no:
        return None
    return sum(1.0 if x>y else 0.5 if x==y else 0.0
               for x in yes for y in no)/(len(yes)*len(no))


def corr(x,y):
    if len(x)!=len(y) or len(x)<3:
        raise ValueError("Missing original paired train risk scores")
    mx=math.fsum(x)/len(x);my=math.fsum(y)/len(y)
    xx=math.fsum((t-mx)**2 for t in x)
    yy=math.fsum((t-my)**2 for t in y)
    if xx==0 or yy==0:
        return 1.0 if xx==yy==0 else 0.0
    return math.fsum((a-mx)*(b-my) for a,b in zip(x,y))/math.sqrt(xx*yy)


def sources(v53,v51):
    if (v53.get("schema")!="aics-v53-100-model-experts-five-champions-fusion-v1"
        or v53.get("hundred_distinct_deterministic_model_expert_strategies_executed")!=100
        or v53.get("selection_uses_same_historical_outcomes_as_reported_performance") is not True
        or v53.get("selection_is_posthoc_100_candidate_multiple_testing") is not True
        or v53.get("selection_validation_failed_independent_OOS") is not True
        or v53.get("approved_live_AICS_index") is not None
        or v53.get("independently_historical_PIT_certified_nodes")!=0
        or v53.get("approved_trades_created") is not False
        or v51.get("schema")!="aics-V51-3BDC-credit-magnitude-and-early-warning-shadow-v1"
        or v51.get("full_11node_AICS") is not None
        or v51.get("historical_independent_first_provider_delivery_verified") is not False
        or len(v51.get("24_month_same_source_model_comparison",[]))!=24
        or sum(WEIGHTS.values())!=1050):
        raise ValueError("Cannot use promoted or incompatible research source")
    data=v53["100_separately_evaluated_model_experts"]
    if len(data)!=100 or len({m["agent_id"] for m in data})!=100:
        raise ValueError("Not 100 model candidates")
    months=None
    vectors={}
    models={}
    for m in data:
        if (m["ex_ante_trained_and_validated"] is not False or
            m["independent_unseen_OOS"] is not None or
            m["live_11node_AICS_score"] is not None):
            raise ValueError("Unexpected V53 forecast promotion")
        points=m["historical_risk_scores_not_AICS"]
        dates=[p["month"] for p in points]
        if months is None:
            months=dates
        if dates!=months:
            raise ValueError("100 specialists used incompatible original research months")
        values=[float(p["risk"]) for p in points]
        if any(not math.isfinite(x) or x<0 or x>100 for x in values):
            raise ValueError("Invalid past candidate model score")
        vectors[m["agent_id"]]=values
        models[m["agent_id"]]={"id":m["agent_id"],"family":m["family"],
                              "family_index":m["family_index"],"variant":m["variant"]}
    if len(months)!=18 or months[0]!="2025-02" or months[-1]!="2026-07":
        raise ValueError("Changed original 18-month 100-model feature range")
    observed=v51["24_month_same_source_model_comparison"]
    if ([x["month"] for x in observed][0]!="2024-11" or
        observed[-1]["month"]!="2026-10"):
        raise ValueError("Underlying 24-month research range changed")
    closes={}
    original={}
    severity={}
    market={}
    for row in observed:
        price=float(row["same_month_SP500_close_source_observed"])
        if not math.isfinite(price) or price<=0:
            raise ValueError("Bad actual market close")
        closes[row["month"]]=price
        if row["month"] in months:
            if row["matched_same_original_3BDC_source_family"] is not True:
                raise ValueError("Changed 3-BDC lineage eligibility")
            original[row["month"]]=float(row["fixed_cohort_breadth_legacy_normalized_NOT_AICS"])
            severity[row["month"]]=float(row["fixed_cohort_hybrid_shadow_normalized_NOT_AICS"])
            market[row["month"]]=float(row["backward_3m_SP500_loss_observed_feature"])
    return months,vectors,models,closes,original,severity,market


def split_months(months,closes,horizon,cutoff=CUTOFF):
    if cutoff not in closes:
        raise ValueError("Unknown train end date")
    available=list(closes)
    market_dates={month:i for i,month in enumerate(available)}
    cutoff_i=market_dates[cutoff]
    train=[]
    later=[]
    for k,month in enumerate(months):
        i=market_dates[month]
        if i+horizon>=len(available):
            continue
        # Exclude overlapping edge labels that could see beyond train cutoff.
        label_month=available[i+horizon]
        future_min=min(closes[available[j]] for j in range(i+1,i+horizon+1))
        positive=(1-future_min/closes[month])*100>=DRAWDOWN
        if market_dates[label_month]<=cutoff_i:
            train.append((k,positive))
        elif i>cutoff_i:
            later.append((k,positive))
        # Crossing the split => deliberately discarded, not leaked into fit.
    return train,later


def stats(vector,sample):
    ys=[bool(y) for _,y in sample]
    xs=[vector[i] for i,_ in sample]
    score=auc(xs,ys)
    return {"month_count":len(sample),"positive_months":sum(ys),
            "negative_months":len(ys)-sum(ys),
            "hindsight_auc":round(score,6) if score is not None else None}


def rank_100(months,vectors,models,closes):
    datasets={h:split_months(months,closes,h)[0] for h in HORIZONS}
    if any(not x for x in datasets.values()):
        raise ValueError("No strictly past-labelled training samples")
    results=[]
    for mid,vector in vectors.items():
        per={h:stats(vector,datasets[h]) for h in HORIZONS}
        aucs=[per[h]["hindsight_auc"] for h in HORIZONS]
        if any(x is None for x in aucs):
            raise ValueError("Train AUC undefined: cannot honestly rank 100")
        objective=0.6*min(aucs)+0.4*math.fsum(aucs)/3
        results.append({**models[mid],
                        "train_only_roc_auc_by_horizon":{str(h):per[h] for h in HORIZONS},
                        "train_only_objective":round(objective,6)})
    return sorted(results,key=lambda m:(-m["train_only_objective"],
                                        m["family_index"],m["variant"]))


def choose_top5(ranked,vectors,months,*,max_abs_corr=None):
    selected=[]
    train_index=[i for i,m in enumerate(months) if m<=CUTOFF]
    if len(train_index)!=9:
        raise ValueError("Expected nine pre-cutoff observed risk feature months")
    for model in ranked:
        if model["family"] in {p["family"] for p in selected}:
            continue
        if max_abs_corr is not None and any(
            abs(corr([vectors[model["id"]][i] for i in train_index],
                     [vectors[other["id"]][i] for i in train_index]))
               > max_abs_corr+1e-12 for other in selected
        ):
            continue
        selected.append(model)
        if len(selected)==5:
            break
    if len(selected)!=5:
        raise ValueError("No 5 family-distinct or sufficiently independent specialists")
    pairs=[]
    for i,a in enumerate(selected):
        for b in selected[i+1:]:
            value=corr([vectors[a["id"]][k] for k in train_index],
                       [vectors[b["id"]][k] for k in train_index])
            pairs.append(abs(value))
    return selected,max(pairs),math.fsum(pairs)/len(pairs)


def fusion(selected,vectors):
    data=[vectors[m["id"]] for m in selected]
    return {
        "median":[median(s[i] for s in data) for i in range(len(data[0]))],
        "mean":[math.fsum(s[i] for s in data)/5 for i in range(len(data[0]))],
    }


def evaluate(v53,v51):
    months,vectors,models,closes,old,severity,market=sources(v53,v51)
    ranked=rank_100(months,vectors,models,closes)
    winners,v53max,v53avg=choose_top5(ranked,vectors,months)
    diversified,v54max,v54avg=choose_top5(
        ranked,vectors,months,max_abs_corr=DEDUPE_ABS_PEARSON
    )
    f_winners=fusion(winners,vectors)
    f_diverse=fusion(diversified,vectors)
    naive_selected=[x["agent_id"] for x in v53["five_selected_unique_architecture_experts"]]
    naive_five=fusion([{"id":mid} for mid in naive_selected],vectors)
    med_months=lambda d:[d[m] for m in months]
    pool={
        "training_time_selected_five_median":f_winners["median"],
        "training_time_selected_five_mean":f_winners["mean"],
        "training_time_diversified_five_median":f_diverse["median"],
        "training_time_diversified_five_mean":f_diverse["mean"],
        "V53_best_five_from_future_viewed_history_median_NOT_OOS":naive_five["median"],
        "original_breadth":med_months(old),
        "V51_severity":med_months(severity),
        "prior_3month_SP500_loss_baseline":med_months(market),
    }
    table=[]
    for h in HORIZONS:
        before,after=split_months(months,closes,h)
        table.append({
            "horizon_months":h,
            "training_cutoff":CUTOFF,
            "train_score_observation_months":[months[i] for i,_ in before],
            "after_cutoff_score_observation_months":[months[i] for i,_ in after],
            "training_true_labels_at_cutoff":stats(pool["original_breadth"],before),
            "later_observed_labels_after_cutoff":stats(pool["original_breadth"],after),
            "train_auc_by_competitor":{name:stats(vec,before)["hindsight_auc"]
                                       for name,vec in pool.items()},
            "later_auc_by_competitor":{name:stats(vec,after)["hindsight_auc"]
                                       for name,vec in pool.items()},
            "later_positive_months":[months[i] for i,y in after if y],
            "time_windows_overlap_in_train_and_test":False,
        })
    if any(x["train_score_observation_months"][-1]>CUTOFF for x in table):
        raise ValueError("Unknown outcomes leaked into fit")
    if len(ranked)!=100:
        raise ValueError("All 100 actual V53 candidates must be trained via past-only labels")
    return {
        "schema":"aics-v54-train-then-later-100-model-selection-debias-v1",
        "as_of":"2026-11-22",
        "conductor_version":"V54_ANTI_OVERFIT_EVALUATION",
        "evaluation_question":"If only labels observable by 2025-10 were used to select 5 out of 100, how do the post-2025-10 labels rank?",
        "hundred_original_different_model_strategies_recomputed":100,
        "historical_model_risk_feature_months":18,
        "model_selection_training_date_cutoff":CUTOFF,
        "training_features_not_future_market_outcome_labels":True,
        "horizon_future_label_ends_before_training_cutoff":True,
        "overlapping_training_horizon_end_months_excluded":True,
        "cutoff_and_model_formulas_devised_after_full_history_seen":True,
        "post_cutoff_evaluation_NOT_prospective_or_untouched_OOS":True,
        "five_selected_using_only_train_end_date_labels":[m["id"] for m in winners],
        "five_selected_with_0_80_max_abs_correlation_using_only_train_features":
            [m["id"] for m in diversified],
        "train_selected_five_max_abs_pearson":round(v53max,6),
        "diversity_selected_five_max_abs_pearson":round(v54max,6),
        "train_selected_five_mean_abs_pearson":round(v53avg,6),
        "diversity_selected_five_mean_abs_pearson":round(v54avg,6),
        "training_only_model_rank_objective":"0.60*min(train_auc_1,3,6) + 0.40*mean(train_auc_1,3,6), with labels available by 2025-10",
        "diversity_constraint_previously_viewed_not_outcome_tuned_here":0.8,
        "comparison_against_V53_selected_on_all_history_separately_and_unequally_fitted":True,
        "honest_time_split_metrics":table,
        "positive_market_episode_in_earlier_train":"2025-02",
        "positive_market_episode_in_later_test":"2026-01 to 2026-02",
        "two_positive_episodes_are_not_independent_crisis_events":True,
        "full_AICS_index":None,
        "original_11_node_weights":1050,
        "certified_historical_first_delivery_PIT_nodes":0,
        "official_AICS_components_or_thresholds_changed":False,
        "proven_forecast_accuracy_gain":None,
        "production_trades":False,
        "decision":"Stop ranking 100 on same labels as scoring; even chronological retro-split is posthoc and too small for crisis forecasting.",
        "training_only_all_100_candidate_ranked_model_results":ranked,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original",type=Path,default=ORIGINAL)
    p.add_argument("--v18",type=Path,default=V18)
    p.add_argument("--sp500",type=Path,default=SPX)
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    files=(a.original,a.v18,a.sp500)
    source=[json.loads(x.read_text(encoding="utf-8")) for x in files]
    v51=v51_build(*source)
    v53=v53_run(v51)
    result=evaluate(v53,v51)
    result["input_sha256"]={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in files}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="training_only_all_100_candidate_ranked_model_results"},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
