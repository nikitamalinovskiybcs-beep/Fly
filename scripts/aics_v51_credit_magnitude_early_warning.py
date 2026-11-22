"""AICS V51 model improvement: material credit worsening, not just issuer breadth.

Replaces the research-only 3-BDC Private Credit *shadow* component with a
pre-specified 40% breadth + 30% magnitude + 30% largest issuer shock model.
Original 11 node weights, the official Private Credit score, and AICS index
remain untouched. Only issuer-quarter facts already recorded in the source
ledger and the 24 observed S&P 500 monthly closes are used.

A single future 10% S&P event is required for crisis discrimination; if there
are zero observed events, AUC is NULL, never zero or one. All scores are
retrospective date-only source candidates, no historical first-feed proof.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS

BASE=Path("aics_data/research")
ORIGINAL=BASE/"private_credit_2024q2_2026q1_first_sec_cost_breadth_2026-11-22.json"
V18=BASE/"aics_v18_private_credit_24m_pit_proxy_overlay_2026-11-22.json"
SPX=BASE/"sp500_24_month_closes_2026-11-21.json"
OUT=BASE/"aics_v51_credit_magnitude_early_warning_shadow_2026-11-22.json"
ISSUERS=("ARCC","BXSL","OBDC")
NODE_COHORT=("Private Credit","Insurers","Semiconductors Supply")
QUARTERS=("2024-Q2","2024-Q3","2024-Q4","2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q1")
# Untrained design priors, not found through optimizing observed future returns.
BREADTH_SHARE=Decimal("0.40")
MAGNITUDE_SHARE=Decimal("0.30")
TAIL_SHARE=Decimal("0.30")
MAGNITUDE_ANCHOR_PP=Decimal("1.0")
TWO=Decimal("0.01")
BREADTH_POLICY="original_3bdc_cost_direction_expost_2026_formula_dateonly_plus1"
assert sum(WEIGHTS.values())==1050 and len(WEIGHTS)==11


def dec(value):
    if isinstance(value,bool):
        raise ValueError("Boolean cannot be accounting or market number")
    try:
        number=Decimal(str(value))
    except (ValueError,TypeError,ArithmeticError) as e:
        raise ValueError("Non-numeric financial source value") from e
    if not number.is_finite():
        raise ValueError("Non-finite original financial source value")
    return number


def q2(value):
    return str(value.quantize(TWO,rounding=ROUND_HALF_UP))


def original_quarter_hybrids(ledger):
    if (ledger.get("schema")!="aics-private-credit-2024q2-2026q1-8quarter-original-sec-cost-breadth-expost-v1"
        or ledger.get("quarter_roster")!=list(QUARTERS)
        or ledger.get("node")!="Private Credit"
        or ledger.get("weight")!=WEIGHTS["Private Credit"]
        or ledger.get("weight_total")!=1050
        or ledger.get("provenance",{}).get("pre_registered_2024_formula") is not False
        or ledger.get("not_computed",{}).get("certified_2024_2026_aics") is not None
        or len(ledger.get("original_issuer_quarter_observations",[]))!=24
        or len(ledger.get("source_event_breadth_series",[]))!=7):
        raise ValueError("Historic three-BDC issuer-cost research contract changed")
    groups={}
    for row in ledger["original_issuer_quarter_observations"]:
        q=row["quarter"]
        issuer=row["issuer"]
        if q not in QUARTERS or issuer not in ISSUERS:
            raise ValueError("Unexpected research issuer/quarter")
        groups.setdefault(q,{})
        if issuer in groups[q]:
            raise ValueError("Duplicate issuer quarter")
        if row["cik"]!={
            "ARCC":"1287750","BXSL":"1736035","OBDC":"1655888",
        }[issuer] or not row["original_numeric_source_url"].startswith("https://www.sec.gov/Archives/edgar/data/"):
            raise ValueError("Wrong issuer original SEC provenance")
        value=dec(row["nonaccrual_amortized_cost_pct"])
        if not 0<=value<=100:
            raise ValueError("Invalid original disclosed cost-rate")
        groups[q][issuer]=value
    if len(groups)!=8 or any(set(groups[q])!=set(ISSUERS) for q in QUARTERS):
        raise ValueError("Incomplete 3x8 original cost observations")
    result={}
    for i,q in enumerate(QUARTERS[1:],1):
        older=groups[QUARTERS[i-1]]
        newer=groups[q]
        delta={ticker:newer[ticker]-older[ticker] for ticker in ISSUERS}
        worsening=sorted(n for n,d in delta.items() if d>0)
        improving=sorted(n for n,d in delta.items() if d<0)
        stable=sorted(n for n,d in delta.items() if d==0)
        source=ledger["source_event_breadth_series"][i-1]
        breadth=Decimal(100)*Decimal(len(worsening))/Decimal(len(ISSUERS))
        positive={n:max(Decimal(0),d) for n,d in delta.items()}
        capped={n:min(Decimal(1),positive[n]/MAGNITUDE_ANCHOR_PP) for n in ISSUERS}
        magnitude=Decimal(100)*sum(capped.values())/Decimal(len(ISSUERS))
        tail=Decimal(100)*max(capped.values())
        composite=BREADTH_SHARE*breadth+MAGNITUDE_SHARE*magnitude+TAIL_SHARE*tail
        if (source["quarter"]!=q or source["previous_quarter"]!=QUARTERS[i-1]
            or source["worsening_issuers"]!=worsening
            or source["improving_issuers"]!=improving
            or source["unchanged_issuers"]!=stable
            or source["issuer_count"]!=3
            or dec(source["score_0_100_descriptive_2026_formula_applied_ex_post"])!=dec(q2(breadth))):
            raise ValueError("Actual issuer cost changes differ from old AICS research breadth")
        for x in (breadth,magnitude,tail,composite):
            if not 0<=x<=100:
                raise ValueError("Model component unbounded")
        result[q]={
            "source_quarter":q,
            "source_research_eligible_date_only_proxy":source["available_at_source_date_plus1_proxy"],
            "issuer_cost_changes_percentage_points":{n:q2(delta[n]) for n in ISSUERS},
            "worsening_issuers":worsening,
            "breadth_legacy_score_0_100":q2(breadth),
            "positive_shock_magnitude_0_100":q2(magnitude),
            "largest_single_issuer_positive_shock_0_100":q2(tail),
            "hybrid_40_30_30_shadow_0_100":q2(composite),
            "is_original_sec_source_history_not_exante_registered":True,
        }
    return result


def auc(scores,labels):
    """Exact ties-half ROC AUC for positive event labels; undefined for one class."""
    if len(scores)!=len(labels):
        raise ValueError("AUC labels must align")
    pos=[dec(s) for s,l in zip(scores,labels) if l is True]
    neg=[dec(s) for s,l in zip(scores,labels) if l is False]
    if not pos or not neg:
        return None
    wins=sum(Decimal(1) if p>n else Decimal("0.5") if p==n else Decimal(0)
             for p in pos for n in neg)
    return float(wins/Decimal(len(pos)*len(neg)))


def table(ledger,v18,spx):
    quarter=original_quarter_hybrids(ledger)
    monthly=v18.get("monthly_last_weekday_market_proxy",[])
    prices=spx.get("points",[])
    if (v18.get("schema")!="aics-v18-24m-private-credit-original-sec-expost-research-overlay-v1"
        or v18.get("full_11node_index_months")!=0
        or v18.get("aics_sp500_spread_months")!=0
        or v18.get("scores_are_expost_not_preregistered") is not True
        or v18.get("trades_created") is not False
        or v18.get("historical_pit_source_bytes_independently_attested") is not False
        or spx.get("symbol")!="GSPC"
        or spx.get("independent_pit_verified") is not False
        or len(monthly)!=24 or len(prices)!=24
        or [r["month"] for r in monthly]!=[r["month"] for r in prices]):
        raise ValueError("24-month real observed original panel is not comparable")
    close=[]
    for p in prices:
        value=dec(p["sp500_month_end_close"])
        if value<=0:
            raise ValueError("Nonpositive S&P500 close")
        close.append(value)
    rows=[]
    for i,row in enumerate(monthly):
        known=row["node_scores"]
        missing=row["missing_nodes"]
        if (not isinstance(known,dict)
            or not isinstance(missing,list)
            or set(known)|set(missing)!=set(WEIGHTS)
            or set(known)&set(missing)
            or row["known_node_count"]!=len(known)
            or row["known_weight"]!=sum(WEIGHTS[n] for n in known)
            or row["full_aics"] is not None
            or row["aics_sp500_spread"] is not None
            or row["historical_pit_certified"] is not False):
            raise ValueError("Uncertified source coverage unexpectedly altered")
        date=dt.date.fromisoformat(row["cutoff_date"])
        for n,obs in known.items():
            if dt.date.fromisoformat(obs["research_eligible_date"])>date:
                raise ValueError("Future node observation used for past monthly feature")
            if not 0<=dec(obs["score"])<=100:
                raise ValueError("Out-of-range original observed issuer model score")
        old=known.get("Private Credit")
        same=(old is not None and old.get("source_policy")==BREADTH_POLICY
              and old.get("quarter_source") in quarter
              and all(n in known for n in NODE_COHORT))
        if same:
            q=quarter[old["quarter_source"]]
            if (old["research_eligible_date"]!=q["source_research_eligible_date_only_proxy"]
                or dec(old["score"])!=dec(q["breadth_legacy_score_0_100"])
                or dt.date.fromisoformat(q["source_research_eligible_date_only_proxy"])>date):
                raise ValueError("Shadow candidate applied to unmatched cohort or future quarterly source")
            weighted=Decimal(sum(WEIGHTS[n] for n in NODE_COHORT))
            baseline=(sum(dec(known[n]["score"])*WEIGHTS[n] for n in NODE_COHORT)/weighted)
            candidate=(baseline+
                       (dec(q["hybrid_40_30_30_shadow_0_100"])-dec(old["score"]))
                       *WEIGHTS["Private Credit"]/weighted)
        else:
            baseline=candidate=None
        result={
            "month":row["month"],
            "market_cutoff_date":row["cutoff_date"],
            "matched_same_original_3BDC_source_family":bool(same),
            "quarter_source":old.get("quarter_source") if same else None,
            "fixed_first_month_three_node_cohort_weight":325,
            "fixed_cohort_breadth_legacy_normalized_NOT_AICS":q2(baseline) if same else None,
            "fixed_cohort_hybrid_shadow_normalized_NOT_AICS":q2(candidate) if same else None,
            "market_known_weight":row["known_weight"],
            "same_month_SP500_close_source_observed":str(close[i]),
            "backward_3m_SP500_loss_observed_feature":
                q2(max(Decimal(0),(1-close[i]/close[i-3])*100)) if i>=3 else None,
            "original_historical_first_feed_PIT_certified":False,
            "official_AICS_score":None,
            "trades_created":False,
        }
        rows.append(result)
    return quarter,rows,close


def diagnostics(quarter,rows,closes):
    # 10% is the defined crisis target; 5% is an independently named
    # exploratory secondary endpoint. NEVER optimize a threshold on outcome.
    results=[]
    for h in (1,3,6):
        for threshold in (Decimal(5),Decimal(10)):
            matched=[]
            for i,row in enumerate(rows):
                if (not row["matched_same_original_3BDC_source_family"]
                    or i<3 or i+h>=len(closes)):
                    continue
                lowest=min(closes[i+1:i+h+1])
                draw=max(Decimal(0),(1-lowest/closes[i])*100)
                label=draw>=threshold
                # Momentum baseline is past 3m loss, known as of month-end.
                matched.append({
                    "month":row["month"],
                    "event":label,
                    "realized_loss_from_prediction_close_pct":q2(draw),
                    "old":dec(row["fixed_cohort_breadth_legacy_normalized_NOT_AICS"]),
                    "hybrid":dec(row["fixed_cohort_hybrid_shadow_normalized_NOT_AICS"]),
                    "market":dec(row["backward_3m_SP500_loss_observed_feature"]),
                })
            positives=sum(x["event"] for x in matched)
            negatives=len(matched)-positives
            scores={key:auc([x[key] for x in matched],[x["event"] for x in matched])
                    for key in ("old","hybrid","market")}
            results.append({
                "forward_horizon_months":h,
                "forward_minimum_month_close_drop_threshold_pct":str(threshold),
                "same_eligible_month_sample_size":len(matched),
                "observed_positive_event_months":positives,
                "observed_negative_event_months":negatives,
                "hindsight_ROC_AUC_original_breadth":scores["old"],
                "hindsight_ROC_AUC_hybrid_shadow":scores["hybrid"],
                "hindsight_ROC_AUC_past_3month_SP500_loss_baseline":scores["market"],
                "scorable_for_crisis_discrimination":positives>0 and negatives>0,
                "explicitly_expost_not_out_of_sample":True,
                "month_outcomes":[{"month":x["month"],"label":x["event"],
                                   "forward_loss_pct":x["realized_loss_from_prediction_close_pct"]}
                                  for x in matched],
            })
    return results


def build(ledger,v18,spx):
    quarters,rows,close=table(ledger,v18,spx)
    evaluation=diagnostics(quarters,rows,close)
    ten=[x for x in evaluation if x["forward_minimum_month_close_drop_threshold_pct"]=="10"]
    five=[x for x in evaluation if x["forward_minimum_month_close_drop_threshold_pct"]=="5"]
    if any(x["observed_positive_event_months"]!=0 for x in ten):
        # Not a required truth: a future public 10% drawdown would be legitimate.
        pass
    changed=[q for q in quarters.values()
             if q["breadth_legacy_score_0_100"]!=q["hybrid_40_30_30_shadow_0_100"]]
    matched=sum(x["matched_same_original_3BDC_source_family"] for x in rows)
    assert len(rows)==24 and len(quarters)==7 and len(evaluation)==6
    return {
        "schema":"aics-V51-3BDC-credit-magnitude-and-early-warning-shadow-v1",
        "model_version":"V51_RESEARCH_SHADOW",
        "as_of":"2026-11-22",
        "objective":"reduce false systemic stress from breadth-only tiny loan deterioration while retaining concentrated shock information",
        "unchanged_official_AICS_11node_weights":True,
        "unchanged_official_private_credit_score":True,
        "unchanged_official_hot_multiplier_and_450_500_thresholds":True,
        "shadow_fixed_subelement_shares":{"breadth":"0.40","magnitude":"0.30","largest_issuer_shock":"0.30"},
        "shadow_magnitude_stress_cap_percentage_points_per_issuer":"1.0",
        "issuer_quarters_observed":24,
        "quarterly_breadth_replay_events":7,
        "quarterly_issuer_cohorts_with_shadow_vs_legacy_difference":len(changed),
        "historical_market_months_examined":24,
        "same_original_source_family_months_comparable":matched,
        "same_source_months_excluded_no_2026Q2Q3_original_cohort":24-matched,
        "historical_independent_first_provider_delivery_verified":False,
        "forward_10pct_crisis_target_scored":any(x["scorable_for_crisis_discrimination"] for x in ten),
        "forward_5pct_secondary_target_scored":any(x["scorable_for_crisis_discrimination"] for x in five),
        "no_future_source_observation_as_feature":True,
        "retrospective_outcome_labels_separate_from_features":True,
        "declared_model_subelement_weights_optimized_using_outcomes":False,
        "this_is_not_walk_forward_OOS":True,
        "model_accuracy_improvement_proven":None,
        "baseline_outperformance_proven":None,
        "full_11node_AICS":None,
        "certified_AICS_nodes":0,
        "production_signal":None,
        "trades_created":False,
        "quarterly_actual_original_3BDC_model_comparison":list(quarters.values()),
        "24_month_same_source_model_comparison":rows,
        "observed_real_SP500_hindsight_event_discrimination":evaluation,
        "model_recommendation":"keep a magnitude+tail shadow; reject promotion until 11-node PIT and previously untouched OOS stress events appear",
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original",type=Path,default=ORIGINAL)
    p.add_argument("--v18",type=Path,default=V18)
    p.add_argument("--sp500",type=Path,default=SPX)
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    paths=(a.original,a.v18,a.sp500)
    output=build(*(json.loads(x.read_text(encoding="utf-8")) for x in paths))
    output["input_sha256"]={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in paths}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in output.items() if k not in (
        "quarterly_actual_original_3BDC_model_comparison",
        "24_month_same_source_model_comparison",
        "observed_real_SP500_hindsight_event_discrimination",
    )}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
