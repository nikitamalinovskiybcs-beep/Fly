"""AICS V64 — complete 11-node RESEARCH nowcast, no fabricated historical scores.

Restore fixed 11-node 1050-point design and hot multiplier. Use actual 8
ex-post researched October 2026 node scores, and ONLY the six previously
explicitly unapproved V61 UST/Repo research scenario mappings plus historical
retrospective AI equity breadth to produce an illustrative scenario MEDIAN.

Neither the six scenarios, their median nor the V59 incomplete-source bounds
are real certified AICS, independent source-delivery PIT, probability
confidence bounds, or a trade signal. For earlier 24 months show only true
known-node coverage and mathematical [unknown=0,unknown=100] conditional
ranges. The five frozen predictive experts stay a SEPARATE layer with
zero prospective predictions so far. Never normalize a partial 3-node panel
as if it was the production AICS index.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_v59_24m_uncertainty_envelope import build as bounds24, multiplier
from scripts.aics_v61_repo_ai_source_to_score_model_risk import (
    V18,DGS30,VOL,REPO,AI,EQUITY_DIRECTORY,REHASH,build as scenarios61
)
from scripts.aics_v62_trusted_score_method_admission_gate import registry_frozen

PROGRESS=Path("aics_data/progress/status.json")
V56_LEDGER=Path("aics_data/research/aics_v56_prospective_forecast_outcome_ledger.json")
OUT=Path("aics_data/research/aics_v64_full_11node_research_nowcast_24m_2026-11-22.json")
D=Decimal
def two(x): return float(x.quantize(D("0.01"),rounding=ROUND_HALF_UP))

def build(source,scenario,progress,ledger):
    registry,_=registry_frozen()
    if (len(WEIGHTS)!=11 or sum(WEIGHTS.values())!=1050
        or registry["approved_method_count"]!=0
        or progress["milestones_completed"]!=22
        or progress["milestones_total"]!=66
        or progress["independently_certified_nodes"]!=0
        or progress["index_aics"] is not None
        or ledger["original_11node_AICS"] is not None
        or ledger["original_v55_forecast_snapshots"]!=[]
        or ledger["frozen_five_specialists"]!=[
            "EXPERT-078","EXPERT-052","EXPERT-041","EXPERT-001","EXPERT-021"]):
        raise ValueError("Untrusted or changed original 11-node governance")
    base=bounds24(source)
    months=base["monthly_24m_conditional_research_envelopes"]
    if len(months)!=24 or months[-1]["month"]!="2026-10":
        raise ValueError("Missing real 24-month ex-post research history")
    original=source["monthly_last_weekday_market_proxy"][-1]
    if (set(original["missing_nodes"])!={"UST 30Y","Repo","AI Equities"}
        or original["known_node_count"]!=8 or original["known_weight"]!=725):
        raise ValueError("Original October 2026 panel has changed")
    octr=scenario["three_months_2026Q3_research_model_definition_risk"][-1]
    if (octr["month"]!="2026-10"
        or octr["conditional_old_interval"]!=[322.06,801.07]
        or octr["equity_retro_7_symbol_research_score_NOT_ELIGIBLE"]!="57.14"):
        raise ValueError("Underlying six research scenarios changed")
    six=octr["six_nonofficial_score_combinations"]
    if len(six)!=6:
        raise ValueError("Not the six frozen posthoc UST/Repo sensitivity cases")
    values=[]
    for item in six:
        if (item["official_AICS"] is not None or item["trade_action"] is not None
            or item["still_missing_unscored_original_nodes"]!=[]):
            raise ValueError("An unapproved scenario claimed official completed index")
        values.append(D(str(item["risk_if_ALL_nonapproved_shadows_assumed_NOT_REAL_AICS"])))
    values.sort()
    median=(values[2]+values[3])/D(2)
    # Recompute the unrounded exact central point directly from ORIGINAL
    # October known-node values, UST hypothesized 49.8/24.9, Repo 0/20/40,
    # and one AI retrospective decliner fraction score 57.14.
    raw=sum(D(WEIGHTS[n])*D(v["score"])/D(100)
            for n,v in original["node_scores"].items())
    hot=sum(D(v["score"])>D(60) for v in original["node_scores"].values())
    if hot!=3 or raw!=D("268.385"):
        raise ValueError("Known October 8-node source raw/hotness changed")
    ust_center=(D("49.8")+D("24.9"))/D(2)
    repo_center=(D(0)+D(20)+D(40))/D(3)
    ai_retro=D(octr["equity_retro_7_symbol_research_score_NOT_ELIGIBLE"])
    if max(ust_center,repo_center,ai_retro)>D(60):
        raise ValueError("Central hot-multiplier state changed")
    central_raw=raw+D(125)*ust_center/D(100)+D(100)*repo_center/D(100)+D(100)*ai_retro/D(100)
    central=central_raw*multiplier(hot)
    if two(central)!=D("470.66") or two(median)!=D("470.66"):
        raise ValueError("Central source-to-score hypothesis grid changed")
    all_nodes=[]
    for name,weight in WEIGHTS.items():
        v=original["node_scores"].get(name)
        if v is not None:
            row={"node":name,"fixed_weight":weight,
                 "expost_research_score_0_to_100":float(v["score"]),
                 "raw_1050_point_contribution":two(D(weight)*D(v["score"])/D(100)),
                 "research_source_date":v["research_eligible_date"],
                 "score_status":"observed_expost_not_independent_pit"}
        else:
            tentative={"UST 30Y":ust_center,"Repo":repo_center,"AI Equities":ai_retro}[name]
            row={"node":name,"fixed_weight":weight,
                 "expost_research_score_0_to_100":None,
                 "scenario_only_reference_score_0_to_100":two(tentative),
                 "reference_raw_contribution_to_scenario_not_observation":two(D(weight)*tentative/D(100)),
                 "research_source_date":None,
                 "score_status":"unapproved_retro_only_not_pit"}
        all_nodes.append(row)
    monthly=[{
        "month":r["month"],
        "known_expost_research_node_count":r["known_node_count"],
        "known_weight_out_of_1050":r["known_weight"],
        "partial_raw_observed_points_not_AICS":r["observed_partial_weighted_sum_not_full_index"],
        "conditional_lower_if_missing_zero_BOUND_NOT_REAL_INDEX":r["conditional_full_index_lower_if_all_missing_scores_ZERO_BOUND_CASE"],
        "conditional_upper_if_missing_100_BOUND_NOT_REAL_INDEX":r["conditional_full_index_upper_if_all_missing_scores_100_BOUND_CASE"],
        "actual_full_11node_AICS":None}
        for r in months]
    zones={}
    for item in six:
        k=item["hypothetical_threshold_zone_NOT_ACTIONABLE"]
        zones[k]=zones.get(k,0)+1
    if set(zones)!={
        "HYPOTHETICAL_ENTRY_LT_450_NOT_ACTIONABLE",
        "HYPOTHETICAL_WATCH_450_TO_500_NOT_ACTIONABLE",
        "HYPOTHETICAL_CASH_GT_500_NOT_ACTIONABLE"} or sorted(zones.values())!=[1,1,4]:
        raise ValueError("Six scenarios no longer disagree across three trade thresholds")
    return {
        "schema":"aics-v64-full-eleven-node-24m-coverage-research-nowcast-v1",
        "as_of":"2026-11-22",
        "last_complete_historical_research_month":"2026-10",
        "eleven_nodes":11,
        "total_weights":1050,
        "official_hot_score_strictly_gt":60,
        "official_multiplier_formula":"clip(1+0.20*clip(H-2,0,1)+0.05*max(0,H-3),1,1.35)",
        "official_thresholds":{"entry_below":450,"watch_from_450_to_500_inclusive":True,"cash_above":500},
        "latest_original_8_of_11_expost_research_raw_points":two(raw),
        "latest_original_known_hot_nodes":hot,
        "latest_original_known_weight":725,
        "unknown_unapproved_original_nodes":["UST 30Y","Repo","AI Equities"],
        "hypothetical_11node_central_raw":two(central_raw),
        "hypothetical_11node_central_hot_multiplier":float(multiplier(hot)),
        "research_indicator_central_six_scenario_median_1050":two(central),
        "research_six_scenario_median_from_rounded_values":two(median),
        "research_six_scenario_min":float(values[0]),
        "research_six_scenario_max":float(values[-1]),
        "research_six_scenario_threshold_zone_counts":zones,
        "research_central_hypothetical_zone":"WATCH_NOT_TRADE",
        "trading_recommendation_from_research_indicator":None,
        "latest_original_model_free_conditional_bounds":[322.06,801.07],
        "october_full_11node_contributions_with_provenance":all_nodes,
        "six_unapproved_scenario_models":six,
        "history_24_months_observed_coverage_and_exact_missing_node_bounds":monthly,
        "five_frozen_predictive_specialists":ledger["frozen_five_specialists"],
        "new_matured_prospective_expert_forecast_count":0,
        "predictive_expert_output_latest":None,
        "official_aics_score":None,
        "independent_PIT_certified_nodes":0,
        "strict_project_readiness":"22/66",
        "trades_created":False,
        "source_selection_lookahead_avoided_for_future":False,
        "important":"The 470.66 is deterministic median of 6 retrospectively selected, UNAPPROVED scoring choices. It is not a statistically calibrated probability estimate, genuine PIT index, OOS validation or actionable signal. Only 8/11 original nodes had ex-post research scores; the 24 month full score remains NULL.",
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=OUT)
    args=parser.parse_args()
    paths=(V18,DGS30,VOL,REPO,AI,EQUITY_DIRECTORY,REHASH)
    data={str(p):p.read_bytes() for p in paths}
    sources=[json.loads(data[str(p)]) for p in paths]
    sha={name:hashlib.sha256(raw).hexdigest() for name,raw in data.items()}
    existing=scenarios61(*sources,hashes=sha)
    progress=json.loads(PROGRESS.read_text())
    ledger=json.loads(V56_LEDGER.read_text())
    result=build(sources[0],existing,progress,ledger)
    result["source_file_sha256"]=sha
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in (
        "october_full_11node_contributions_with_provenance",
        "six_unapproved_scenario_models","history_24_months_observed_coverage_and_exact_missing_node_bounds","source_file_sha256")},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
