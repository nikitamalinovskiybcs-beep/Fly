"""AICS V52 conductor: short/long credit channels and fragility falsification.

This is a MODEL-design experiment on V51's actual 24 historical partial
source months. It is NOT a trained model, independent OOS, historical first-feed
PIT, full AICS, or a trading signal. Horizon channel selection was proposed
AFTER seeing earlier V51 descriptive performance: a deliberately exploratory
design, to be locked before new unseen observations.

The 100 horizon x drawdown-threshold outcomes here are NOT 100 forecasts.
They are 100 retrospective sensitivity interrogations of the same overlapping
observations. Permutation/bootstrap significance and 2000/2008 foresight are
not inferred from them.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from scripts.aics_v51_credit_magnitude_early_warning import (
    ORIGINAL, V18, SPX, build as v51_build, dec, q2, auc
)
from scripts.aics_score_reproducibility_gate import WEIGHTS

OUT=Path("aics_data/research/aics_v52_horizon_credit_model_robustness_2026-11-22.json")
SRC_V51_SCHEMA="aics-V51-3BDC-credit-magnitude-and-early-warning-shadow-v1"
STRESS_THRESHOLDS=tuple(range(1,11))
STRESS_HORIZONS=tuple(range(1,11))
SELECTED=(1,3,6)
RESEARCH_SECONDARY_CRITERION=Decimal("5")
RESEARCH_PRIMARY_CRISIS_CRITERION=Decimal("10")


def shadow_channel(horizon):
    """Post-hoc architecture proposal: assign horizons by time scale ONLY.

    Do not allow observed future return outcomes, AUC, month or quarter to
    choose the model used for a given horizon.
    """
    if not isinstance(horizon,int) or isinstance(horizon,bool) or not 1<=horizon<=10:
        raise ValueError("Unsupported shadow horizon")
    if horizon<=2:
        return ("breadth_fast","1.00", "0.00")
    if horizon<=4:
        return ("equal_mid","0.50","0.50")
    return ("severity_slow","0.00","1.00")


def _auc(rows,key):
    return auc([x[key] for x in rows],[x["event"] for x in rows])


def _loss(closes,i,h):
    if i+h>=len(closes):
        raise ValueError("Forward monthly-closed horizon unavailable")
    return max(Decimal(0),(Decimal(1)-min(closes[i+1:i+h+1])/closes[i])*100)


def _event_episodes(rows):
    """Consecutive calendar months with a positive label form one episode.

    This is a descriptive dependence diagnostic, NOT n independent crashes.
    """
    episodes=[]
    for k,x in enumerate(rows):
        if not x["event"]:
            continue
        if episodes and k-episodes[-1]["last_row_position"]==1:
            episodes[-1]["positive_months"].append(x["month"])
            episodes[-1]["last_row_position"]=k
        else:
            episodes.append({"id":len(episodes)+1,"positive_months":[x["month"]],
                             "last_row_position":k})
    return [{"id":e["id"],"positive_months":e["positive_months"]}
            for e in episodes]


def _cohort_sample(v51,closes,horizon,threshold):
    months=v51["24_month_same_source_model_comparison"]
    _,legacy_share,hybrid_share=shadow_channel(horizon)
    mix_old=dec(legacy_share)
    mix_hybrid=dec(hybrid_share)
    out=[]
    for i,row in enumerate(months):
        # Same source panel and prior 3m market feature used for ALL variants;
        # exclude last h observations if their next closes are unobserved.
        if (i<3 or i+h>=len(closes)
            or row["matched_same_original_3BDC_source_family"] is not True):
            continue
        old=dec(row["fixed_cohort_breadth_legacy_normalized_NOT_AICS"])
        hybrid=dec(row["fixed_cohort_hybrid_shadow_normalized_NOT_AICS"])
        past=dec(row["backward_3m_SP500_loss_observed_feature"])
        selected=old*mix_old+hybrid*mix_hybrid
        loss=_loss(closes,i,horizon)
        out.append({
            "month":row["month"],
            "event":loss>=dec(threshold),
            "realized_forward_max_month_close_loss_pct":q2(loss),
            "old":old,
            "hybrid":hybrid,
            "split":selected,
            "market":past,
        })
    return out


def _paired_metrics(rows,horizon,threshold):
    scores={key:_auc(rows,key) for key in ("old","hybrid","split","market")}
    positive=sum(x["event"] for x in rows)
    return {
        "horizon_months":horizon,
        "drawdown_threshold_pct":str(threshold),
        "channel_architecture":shadow_channel(horizon)[0],
        "matched_history_months":len(rows),
        "positive_label_months":positive,
        "negative_label_months":len(rows)-positive,
        "distinct_positive_episodes":len(_event_episodes(rows)),
        "AUC_legacy_expost":scores["old"],
        "AUC_V51_severity_expost":scores["hybrid"],
        "AUC_V52_horizon_split_expost":scores["split"],
        "AUC_past_3month_market_loss_expost":scores["market"],
        "AUC_defined_both_classes":bool(positive and positive<len(rows)),
        "AUC_not_a_forward_certified_model_skill":True,
    }


def _jackknife(rows,horizon,threshold):
    original=_paired_metrics(rows,horizon,threshold)
    episode=[]
    for item in _event_episodes(rows):
        masked=set(item["positive_months"])
        remaining=[x for x in rows if x["month"] not in masked]
        metrics=_paired_metrics(remaining,horizon,threshold)
        delta=(metrics["AUC_V51_severity_expost"]-metrics["AUC_legacy_expost"]
               if metrics["AUC_defined_both_classes"] else None)
        episode.append({
            "held_out_event_episode_months":sorted(masked),
            "remaining_months":len(remaining),
            "remaining_positive_label_months":metrics["positive_label_months"],
            "remaining_positive_episodes":metrics["distinct_positive_episodes"],
            "AUC_legacy_expost_without_episode":metrics["AUC_legacy_expost"],
            "AUC_V51_expost_without_episode":metrics["AUC_V51_severity_expost"],
            "V51_minus_legacy_auc_gap_without_episode":round(delta,6) if delta is not None else None,
        })
    eligible=[z["V51_minus_legacy_auc_gap_without_episode"]
              for z in episode if z["V51_minus_legacy_auc_gap_without_episode"] is not None]
    reference=(original["AUC_V51_severity_expost"]-original["AUC_legacy_expost"]
               if original["AUC_defined_both_classes"] else None)
    return {
        "horizon_months":horizon,
        "threshold_pct":str(threshold),
        "observed_positive_episode_count":original["distinct_positive_episodes"],
        "reference_V51_minus_legacy_auc_gap":round(reference,6) if reference is not None else None,
        "leave_one_actual_positive_episode_out":episode,
        "all_remaining_episode_tests_improve_on_legacy":
            all(v>0 for v in eligible) if eligible else None,
        "minimum_remaining_auc_gap":min(eligible) if eligible else None,
        "maximum_remaining_auc_gap":max(eligible) if eligible else None,
        "no_significance_claim_due_to_overlapping_labels":True,
    }


def evaluate(v51):
    if (v51.get("schema")!=SRC_V51_SCHEMA
        or v51.get("as_of")!="2026-11-22"
        or v51.get("unchanged_official_AICS_11node_weights") is not True
        or v51.get("unchanged_official_private_credit_score") is not True
        or v51.get("this_is_not_walk_forward_OOS") is not True
        or v51.get("historical_independent_first_provider_delivery_verified") is not False
        or v51.get("certified_AICS_nodes")!=0
        or v51.get("full_11node_AICS") is not None
        or v51.get("production_signal") is not None
        or v51.get("trades_created") is not False
        or len(v51.get("24_month_same_source_model_comparison",[]))!=24
        or sum(WEIGHTS.values())!=1050):
        raise ValueError("V52 refuses to optimize a different or certified source")
    monthly=v51["24_month_same_source_model_comparison"]
    if monthly[0]["month"]!="2024-11" or monthly[-1]["month"]!="2026-10":
        raise ValueError("Historical observed model window changed")
    closes=[]
    for row in monthly:
        p=dec(row["same_month_SP500_close_source_observed"])
        if p<=0:
            raise ValueError("Invalid observed original S&P 500 close")
        closes.append(p)
    if sum(row["matched_same_original_3BDC_source_family"] is True
           for row in monthly)!=21:
        raise ValueError("The V51 source-family count changed")
    work=[]
    for h in STRESS_HORIZONS:
        for threshold in STRESS_THRESHOLDS:
            rows=_cohort_sample(v51,closes,h,Decimal(threshold))
            metrics=_paired_metrics(rows,h,Decimal(threshold))
            work.append({
                "task_id":f"MODEL52-{len(work)+1:03d}",
                "specialist":f"Horizon{h:02d}_StressDirector",
                "job":"retrospective_positive_and_negative_class_robustness",
                "output":metrics,
                "used_existing_observed_prices_only":True,
                "new_independent_trained_AIs":0,
                "out_of_sample_prediction_skill":None,
            })
    if (len(work)!=100 or
        len({x["task_id"] for x in work})!=100 or
        len({x["specialist"] for x in work})!=10 or
        any(sum(x["specialist"]==s for x in work)!=10
            for s in {x["specialist"] for x in work})):
        raise ValueError("100 model-side independent scenario assignments missing")
    primary=[]
    secondary=[]
    episode=[]
    for h in SELECTED:
        for threshold,selection in ((RESEARCH_SECONDARY_CRITERION,secondary),
                                    (RESEARCH_PRIMARY_CRISIS_CRITERION,primary)):
            rows=_cohort_sample(v51,closes,h,threshold)
            selection.append(_paired_metrics(rows,h,threshold))
            if threshold==RESEARCH_SECONDARY_CRITERION:
                episode.append(_jackknife(rows,h,threshold))
    for h,old in zip(SELECTED,
                      [x for x in v51["observed_real_SP500_hindsight_event_discrimination"]
                       if x["forward_minimum_month_close_drop_threshold_pct"]=="5"]):
        if old["forward_horizon_months"]!=h:
            raise ValueError("Existing retrospective target horizon roster changed")
        recomputed=next(x for x in secondary if x["horizon_months"]==h)
        for a,b in (("hindsight_ROC_AUC_original_breadth","AUC_legacy_expost"),
                    ("hindsight_ROC_AUC_hybrid_shadow","AUC_V51_severity_expost"),
                    ("hindsight_ROC_AUC_past_3month_SP500_loss_baseline",
                     "AUC_past_3month_market_loss_expost")):
            if old[a] is None and recomputed[b] is None:
                continue
            if old[a] is None or recomputed[b] is None or abs(old[a]-recomputed[b])>1e-12:
                raise ValueError("V52 source-to-outcome benchmark diverges from V51")
    if any(x["positive_label_months"]!=0 for x in primary):
        raise ValueError("Previously published 1/3/6m 10% crisis labels changed")
    six=next(x for x in episode if x["horizon_months"]==6)
    last_positive=next(x for x in secondary if x["horizon_months"]==6)
    six_robust=six["all_remaining_episode_tests_improve_on_legacy"]
    # Even if all ex-post leave-cluster gaps are positive, genuine OOS remains NULL.
    return {
        "schema":"aics-V52-horizon-credit-risk-and-episode-falsification-v1",
        "model_version":"V52_TIME_SCALE_SPLIT_UNAPPROVED",
        "as_of":"2026-11-22",
        "model_objective":"keep broad common-credit weakening for near-term warnings and severe concentrated shocks for longer horizons without backfilling absent nodes",
        "100_coordinated_model_falsification_scenarios":len(work),
        "number_of_horizon_director_roles":10,
        "actually_new_independently_trained_agents":0,
        "source_real_observed_months":24,
        "same_credit_source_family_months":21,
        "retrospective_market_outcome_threshold_grid_percent":[1,10],
        "retrospective_market_outcome_horizon_grid_months":[1,10],
        "horizon_split_shadow_prior":{"1_to_2_months":"original breadth only",
                                      "3_to_4_months":"50pct breadth / 50pct magnitude tail",
                                      "5_to_10_months":"magnitude tail hybrid only"},
        "horizon_split_proposed_after_observing_V51_results":True,
        "shadow_horizon_parameters_trainable_from_current_expost_grid":False,
        "primary_crisis_10pct_positive_months_by_1_3_6m":[x["positive_label_months"] for x in primary],
        "primary_crisis_AUC_all_undefined":all(x["AUC_V52_horizon_split_expost"] is None
                                               for x in primary),
        "secondary_5pct_same_month_model_comparison":secondary,
        "secondary_5pct_episode_deletion_robustness":episode,
        "six_month_v51_auc_better_after_every_positive_episode_omission":six_robust,
        "six_month_one_episode_omission_min_V51_auc_gap":six["minimum_remaining_auc_gap"],
        "six_month_positive_month_count":last_positive["positive_label_months"],
        "six_month_distinct_positive_episode_count":last_positive["distinct_positive_episodes"],
        "model_improved_independent_crisis_warning_performance":None,
        "original_11node_weights_and_formula_unchanged":True,
        "production_11node_AICS":None,
        "independent_first_publication_PIT_proven":False,
        "independent_out_of_sample_test":None,
        "production_trading_signal":None,
        "trades_created":False,
        "conductor_decision":"V52 horizon split remains a falsification-only shadow; positive long-horizon evidence is too thin and selection post-hoc",
        "100_expost_model_falsification_tasks":work,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original",type=Path,default=ORIGINAL)
    parser.add_argument("--v18",type=Path,default=V18)
    parser.add_argument("--sp500",type=Path,default=SPX)
    parser.add_argument("--out",type=Path,default=OUT)
    args=parser.parse_args()
    paths=(args.original,args.v18,args.sp500)
    source=v51_build(*(json.loads(p.read_text(encoding="utf-8")) for p in paths))
    report=evaluate(source)
    report["input_sha256"]={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="100_expost_model_falsification_tasks"},
                     ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
