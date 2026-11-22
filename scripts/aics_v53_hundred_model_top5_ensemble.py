"""AICS V53 conductor: 100 different deterministic risk models, choose five,
then make a five-specialist shadow ensemble.

The five "best" are ranked only on RETROSPECTIVE >=5% S&P500 monthly-close
drawdown discrimination at +1,+3,+6 months. It is a multiple-comparison,
previously viewed, 18/15-month in-sample selection, NOT model-validation skill.
Unknown original nodes stay unknown. Independent original first-delivery PIT,
full AICS, OOS, trade and >10% crash forecast remain unapproved/null.

100 specialist roles = 10 different feature architecture families x 10
different parameterized strategies, actually evaluated on the same real source
months. 0 independently trained external AI processes are falsely claimed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from scripts.aics_v51_credit_magnitude_early_warning import (
    ORIGINAL,V18,SPX,build as v51_build,dec,auc,
)
from scripts.aics_score_reproducibility_gate import WEIGHTS

OUT=Path("aics_data/research/aics_v53_hundred_model_top5_ensemble_2026-11-22.json")
FAMILIES=(
    "breadth_persistence_specialist",
    "severity_memory_specialist",
    "credit_mix_architect",
    "agreement_divergence_analyst",
    "breadth_acceleration_sentinel",
    "severity_acceleration_sentinel",
    "market_credit_confirmation_analyst",
    "one_month_market_shock_analyst",
    "market_volatility_credit_analyst",
    "dual_tempo_credit_consensus",
)
HORIZONS=(1,3,6)
TARGET5=5.0
TARGET10=10.0


def finite(x):
    value=float(x)
    if isinstance(x,bool) or not math.isfinite(value):
        raise ValueError("Non-finite or Boolean source number")
    return value


def clamp(x):
    if not math.isfinite(x):
        raise ValueError("Non-finite model component")
    return min(100.0,max(0.0,x))


def source_rows(v51):
    """Extract dated available model features; never touch future return labels."""
    if (v51.get("schema")!="aics-V51-3BDC-credit-magnitude-and-early-warning-shadow-v1"
        or v51.get("unchanged_official_AICS_11node_weights") is not True
        or v51.get("unchanged_official_private_credit_score") is not True
        or v51.get("historical_independent_first_provider_delivery_verified") is not False
        or v51.get("this_is_not_walk_forward_OOS") is not True
        or v51.get("model_accuracy_improvement_proven") is not None
        or v51.get("full_11node_AICS") is not None
        or v51.get("certified_AICS_nodes")!=0
        or v51.get("production_signal") is not None
        or v51.get("trades_created") is not False
        or sum(WEIGHTS.values())!=1050 or len(WEIGHTS)!=11):
        raise ValueError("V53 cannot promote an uncertified AICS input")
    rows=v51.get("24_month_same_source_model_comparison",[])
    if (len(rows)!=24 or rows[0]["month"]!="2024-11"
        or rows[-1]["month"]!="2026-10"
        or sum(x["matched_same_original_3BDC_source_family"] is True for x in rows)!=21):
        raise ValueError("V51 original dated 24-month source-family sample changed")
    closes=[]
    for row in rows:
        value=finite(row["same_month_SP500_close_source_observed"])
        if value<=0:
            raise ValueError("Nonpositive original S&P500 close")
        closes.append(value)
    features={}
    for i,row in enumerate(rows):
        if i<3 or row["matched_same_original_3BDC_source_family"] is not True:
            continue
        b=finite(row["fixed_cohort_breadth_legacy_normalized_NOT_AICS"])
        s=finite(row["fixed_cohort_hybrid_shadow_normalized_NOT_AICS"])
        if not (0<=b<=100 and 0<=s<=100):
            raise ValueError("Original source-cohort normalized risk out of bounds")
        past3=finite(row["backward_3m_SP500_loss_observed_feature"])
        if past3<0:
            raise ValueError("Negative market drawdown")
        observed=[j for j in range(max(0,i-2),i+1)
                  if rows[j]["matched_same_original_3BDC_source_family"] is True]
        def rolling(key,n):
            recent=observed[-n:]
            if not recent:
                raise ValueError("Insufficient already observed source history")
            return math.fsum(finite(rows[j][key]) for j in recent)/len(recent)
        prior=rows[i-1]
        old_b=(finite(prior["fixed_cohort_breadth_legacy_normalized_NOT_AICS"])
               if prior["matched_same_original_3BDC_source_family"] is True else b)
        old_s=(finite(prior["fixed_cohort_hybrid_shadow_normalized_NOT_AICS"])
               if prior["matched_same_original_3BDC_source_family"] is True else s)
        past1_loss=clamp(max(0,closes[i-1]/closes[i]-1)*1000)
        backwards_abs=[abs(closes[j]/closes[j-1]-1)*100
                       for j in range(max(1,i-2),i+1)]
        features[i]={
            "month":row["month"],
            "B":b,
            "S":s,
            "BM2":rolling("fixed_cohort_breadth_legacy_normalized_NOT_AICS",2),
            "SM2":rolling("fixed_cohort_hybrid_shadow_normalized_NOT_AICS",2),
            "BM3":rolling("fixed_cohort_breadth_legacy_normalized_NOT_AICS",3),
            "SM3":rolling("fixed_cohort_hybrid_shadow_normalized_NOT_AICS",3),
            "loss3":clamp(past3*10),
            "loss1":past1_loss,
            "vol":clamp(math.fsum(backwards_abs)/len(backwards_abs)*15),
            "accelB":clamp(max(0,b-old_b)*2.5),
            "accelS":clamp(max(0,s-old_s)*2.5),
        }
    if (len(features)!=18 or
        [features[i]["month"] for i in sorted(features)][:1]!=["2025-02"] or
        features[max(features)]["month"]!="2026-07"):
        raise ValueError("Original paired comparison calendar no longer comparable")
    return rows,closes,features


def candidate_score(family,variant,x):
    """10 independent architectures with 10 meaningful parameter versions each."""
    if (not isinstance(family,int) or isinstance(family,bool) or
        not isinstance(variant,int) or isinstance(variant,bool) or
        family not in range(10) or variant not in range(1,11)):
        raise ValueError("Unrecognized model specialist")
    w=variant/11.0
    b=x["B"];s=x["S"]
    formula=(
        (1-w)*b+w*x["BM2"],
        (1-w)*s+w*x["SM3"],
        (1-w)*b+w*s,
        (1-w)*max(b,s)+w*min(b,s),
        (1-w)*b+w*x["accelB"],
        (1-w)*s+w*x["accelS"],
        (1-w)*b+w*x["loss3"],
        (1-w)*s+w*x["loss1"],
        (1-w)*(0.5*b+0.5*s)+w*x["vol"],
        (1-w)*x["BM3"]+w*x["SM2"],
    )
    out=formula[family]
    if not 0<=out<=100:
        raise ValueError("Bad specialized model risk score")
    return out


def labels(closes,indices,horizon,drawdown):
    ids=[i for i in indices if i+horizon<len(closes)]
    outcomes=[]
    for i in ids:
        # Only retrospective target generation, never fed into candidate_score.
        future_low=min(closes[i+1:i+horizon+1])
        loss=max(0,(1-future_low/closes[i])*100)
        outcomes.append(loss>=drawdown)
    return ids,outcomes


def roc(closes,score,all_ids,horizon,drawdown):
    ids,y=labels(closes,all_ids,horizon,drawdown)
    value=auc([score[i] for i in ids],y)
    return {
        "n":len(ids),"positive_month_labels":sum(y),
        "negative_month_labels":len(y)-sum(y),
        "hindsight_AUC":round(value,6) if value is not None else None,
    }


def correlation(a,b):
    if len(a)!=len(b) or len(a)<3:
        return None
    ma=math.fsum(a)/len(a); mb=math.fsum(b)/len(b)
    vx=math.fsum((x-ma)**2 for x in a)
    vy=math.fsum((y-mb)**2 for y in b)
    if vx<=0 or vy<=0:
        return None
    return math.fsum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(vx*vy)


def choose(models):
    """Diversify by architecture family, never claim an untouched holdout.

    60% of ranking favors the worst of +1,+3,+6m AUC; 40% their
    arithmetic mean. This objective and family diversity are EXPLORATORY
    after model design and the same historical market outcomes were viewed.
    """
    grouped={}
    for model in models:
        grouped.setdefault(model["family"],[]).append(model)
    if len(grouped)!=10 or any(len(x)!=10 for x in grouped.values()):
        raise ValueError("No 10-by-10 model orchestra")
    leaders=[]
    for family in FAMILIES:
        candidates=grouped[family]
        leaders.append(sorted(candidates,
                              key=lambda x:(-x["exploratory_multi_horizon_rank"],
                                            x["variant"]))[0])
    top=sorted(leaders,key=lambda x:(-x["exploratory_multi_horizon_rank"],
                                    x["family_index"]))[:5]
    if len(top)!=5 or len({x["family"] for x in top})!=5:
        raise ValueError("Five family-distinct model leaders not selected")
    return leaders,top


def run(v51):
    rows,closes,features=source_rows(v51)
    all_ids=sorted(features)
    models=[]
    score_vectors={}
    signatures=set()
    for family in range(10):
        for variant in range(1,11):
            scores={i:candidate_score(family,variant,features[i]) for i in all_ids}
            signature=tuple(round(scores[i],9) for i in all_ids)
            if signature in signatures:
                raise ValueError("Two alleged distinct model agents make identical scores")
            signatures.add(signature)
            aucs={}
            for horizon in HORIZONS:
                aucs[horizon]=roc(closes,scores,all_ids,horizon,TARGET5)
                if aucs[horizon]["hindsight_AUC"] is None:
                    raise ValueError("Unscorable historical secondary 5pct research comparison")
            av=[aucs[h]["hindsight_AUC"] for h in HORIZONS]
            rank=0.6*min(av)+0.4*math.fsum(av)/3
            agent_id=f"EXPERT-{len(models)+1:03d}"
            models.append({
                "agent_id":agent_id,
                "family_index":family,
                "family":FAMILIES[family],
                "variant":variant,
                "variant_weight":round(variant/11,6),
                "independent_model_architecture":FAMILIES[family],
                "n_actual_observed_months_scored":len(scores),
                "outcome_discrimination_5pct_expost":{str(k):v for k,v in aucs.items()},
                "exploratory_multi_horizon_rank":round(rank,6),
                "ex_ante_trained_and_validated":False,
                "independent_unseen_OOS":None,
                "live_11node_AICS_score":None,
                "role_execution":"ACTUAL_DETERMINISTIC_MODEL_EXPERT_NOT_SEPARATE_LLM",
                "historical_risk_scores_not_AICS":[
                    {"month":features[i]["month"],"risk":round(scores[i],6)}
                    for i in all_ids
                ],
            })
            score_vectors[agent_id]=scores
    if len(models)!=100 or len({m["agent_id"] for m in models})!=100:
        raise ValueError("100 distinct model candidates were not executed")
    leaders,top=choose(models)
    chosen=[score_vectors[m["agent_id"]] for m in top]
    median_score={i:median(s[i] for s in chosen) for i in all_ids}
    mean_score={i:math.fsum(s[i] for s in chosen)/5 for i in all_ids}
    old_score={i:features[i]["B"] for i in all_ids}
    severity={i:features[i]["S"] for i in all_ids}
    market={i:features[i]["loss3"] for i in all_ids}
    perf=[]
    for horizon in HORIZONS:
        for drawdown in (TARGET5,TARGET10):
            scores={
                "official_still_unapproved_legacy_fixed_cohort":old_score,
                "V51_severity_fixed_cohort":severity,
                "market_past_3month_drop":market,
                "five_experts_unweighted_mean":mean_score,
                "five_experts_robust_median":median_score,
            }
            metrics={name:roc(closes,v,all_ids,horizon,drawdown)
                     for name,v in scores.items()}
            perf.append({
                "horizon_months":horizon,
                "minimum_future_month_close_drawdown_pct":drawdown,
                "all_variants_same_months":True,
                "n":metrics["five_experts_robust_median"]["n"],
                "observed_positive_month_labels":metrics["five_experts_robust_median"]["positive_month_labels"],
                "hindsight_AUC_by_variant":{k:v["hindsight_AUC"] for k,v in metrics.items()},
                "historical_untouched_holdout_certified":False,
            })
    pairwise=[]
    for j,x in enumerate(top):
        for y in top[j+1:]:
            corr=correlation(
                [score_vectors[x["agent_id"]][i] for i in all_ids],
                [score_vectors[y["agent_id"]][i] for i in all_ids])
            pairwise.append({"expert_a":x["agent_id"],
                             "expert_b":y["agent_id"],
                             "risk_score_pearson_correlation":round(corr,6) if corr is not None else None})
    high=sum(x["risk_score_pearson_correlation"] is not None and
             abs(x["risk_score_pearson_correlation"])>=0.98 for x in pairwise)
    primary=[p for p in perf if p["minimum_future_month_close_drawdown_pct"]==TARGET10]
    if any(p["observed_positive_month_labels"]>0 for p in primary):
        raise ValueError("Original 1/3/6m 10pct negative crisis evidence changed")
    latest=rows[-1]["month"]
    return {
        "schema":"aics-v53-100-model-experts-five-champions-fusion-v1",
        "as_of":"2026-11-22",
        "conductor_role":"ensemble design and independent fail-closed result arbitration",
        "hundred_distinct_deterministic_model_expert_strategies_executed":100,
        "ten_specialist_teams":list(FAMILIES),
        "variants_per_specialist_team":10,
        "actual_independently_running_new_LLM_agents":0,
        "five_selected_unique_architecture_experts":[
            {
                "rank":pos+1,
                "agent_id":x["agent_id"],
                "family":x["family"],
                "variant":x["variant"],
                "exploratory_ranking_score":x["exploratory_multi_horizon_rank"],
                "hindsight_5pct_auc_1m":x["outcome_discrimination_5pct_expost"]["1"]["hindsight_AUC"],
                "hindsight_5pct_auc_3m":x["outcome_discrimination_5pct_expost"]["3"]["hindsight_AUC"],
                "hindsight_5pct_auc_6m":x["outcome_discrimination_5pct_expost"]["6"]["hindsight_AUC"],
            } for pos,x in enumerate(top)
        ],
        "family_champions":[x["agent_id"] for x in leaders],
        "selection_objective":"0.6 times minimum of 1m,3m,6m hindsight ROC-AUC plus 0.4 times their mean, 5pct drawdown; one champion per family",
        "selection_uses_same_historical_outcomes_as_reported_performance":True,
        "selection_is_posthoc_100_candidate_multiple_testing":True,
        "ensemble_research_fusion_rules":{
            "unweighted_mean":"sum(top 5 risk)/5",
            "robust_median":"median(top 5 risk)",
            "no_calibration_or_live_threshold":"yes",
            "median_selected_for_robustness_after_observing_historical_outcomes":True,
        },
        "selection_validation_failed_independent_OOS":True,
        "historical_months_in_original_panel":24,
        "historical_source_family_months":21,
        "research_source_and_prior_market_comparable_months":18,
        "most_recent_original_research_month":latest,
        "most_recent_ensemble_eligible_month":features[max(all_ids)]["month"],
        "missing_recent_original_private_credit_cohort_not_filled":3,
        "primary_crisis_10pct_auc_all_UNDEFINED":all(
            all(x is None for x in p["hindsight_AUC_by_variant"].values()) for p in primary
        ),
        "actual_sp500_hindsight_metrics":perf,
        "high_pairwise_correlation_selected_expert_pairs_ge_0_98":high,
        "pairwise_selected_expert_correlations":pairwise,
        "new_model_superior_forecast_skill_proven":None,
        "approved_live_AICS_index":None,
        "independently_historical_PIT_certified_nodes":0,
        "original_11_node_weights_1050_unchanged":True,
        "original_hot_multiplier_and_450_500_thresholds_unchanged":True,
        "approved_trades_created":False,
        "provisional_conductor_decision":"five selected and two ensembles assembled, but NO ex-ante crash-prediction winner can be certified; new untouched history required",
        "monthly_five_champion_shadow":[
            {
                "month":rows[i]["month"],
                "model_eligible_source":i in features,
                "mean_five_shadow_risk_NOT_AICS":round(mean_score[i],6) if i in features else None,
                "median_five_shadow_risk_NOT_AICS":round(median_score[i],6) if i in features else None,
                "historical_first_delivery_verified":False,
                "AICS_production_score":None,
            }
            for i in range(24)
        ],
        "100_separately_evaluated_model_experts":models,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original",type=Path,default=ORIGINAL)
    parser.add_argument("--v18",type=Path,default=V18)
    parser.add_argument("--sp500",type=Path,default=SPX)
    parser.add_argument("--out",type=Path,default=OUT)
    args=parser.parse_args()
    paths=(args.original,args.v18,args.sp500)
    original=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
    out=run(v51_build(*original))
    out["input_sha256"]={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in out.items() if k not in (
        "100_separately_evaluated_model_experts","monthly_five_champion_shadow",
        "actual_sp500_hindsight_metrics","pairwise_selected_expert_correlations",
    )},ensure_ascii=False))
    for x in out["actual_sp500_hindsight_metrics"]:
        if x["minimum_future_month_close_drawdown_pct"]==TARGET5:
            print("HORIZON",x["horizon_months"],"n=",x["n"],
                  "positive_months=",x["observed_positive_month_labels"],
                  "AUC=",x["hindsight_AUC_by_variant"])
    return 0


if __name__=="__main__":
    raise SystemExit(main())
