"""Ten new AICS *model improvement* research agents; source collectors unchanged.

Independent of the previous 10 research-audit agents. All new agents perform
actual evidence checks or retrospective descriptive calculations. Prediction,
contagion, GPU payback and model reweighting remain gated until their required
real inputs and untouched chronological validation exist.

No artificial training labels, unverified future prices, imputed scores,
unstated capital exposures, or production orders.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_sec_quarter_cashflow_gate import audit as audit_cashflow
from scripts.aics_historical_crisis_analog import build as historical_crisis_analog
from scripts.aics_spv_funding_transmission_bridge import (
    build as spv_bridge_build, CORE as SPV_CORE, CLOUD as SPV_CLOUD,
    NSCALE as SPV_NSCALE, DFS as SPV_DFS,
)
from scripts.aics_early_imbalance_cashflow_shadow import (
    build as early_imbalance_build,
    Y2025 as EARLY_CASH_2025,
    Q42025 as EARLY_CASH_2025Q4,
    Q12026 as EARLY_CASH_2026Q1,
    Q22026 as EARLY_CASH_2026Q2,
    Q32026 as EARLY_CASH_2026Q3,
)

ROOT = Path("aics_data/research")
V17 = ROOT / "aics_24m_multi_node_publication_overlay_2026-11-21.json"
V18 = ROOT / "aics_v18_private_credit_24m_pit_proxy_overlay_2026-11-22.json"
SPX = ROOT / "sp500_24_month_closes_2026-11-21.json"
AI_SHADOW = ROOT / "ai_equities_aug_oct_2026_retrospective_shadow_2026-11-21.json"
NUMERICS = Path("aics_data/agent_runs/ten_real_collection_rounds/actual_sec_xbrl_facts_unverified.json")
FIN_AUDIT = Path("aics_data/agent_runs/ten_real_collection_rounds/sec_direct_quarter_cashflow_gate.json")
SOURCE_WAVES = Path("aics_data/agent_runs/ten_real_collection_rounds/ten_rounds_manifest.json")
OUTPUT = Path("aics_data/agent_runs/ten_real_collection_rounds/aics_model_improvement_agents.json")

NAMES = (
    "SECFinancialAnalyst",
    "AIEquitiesHistorian",
    "CreditContagionAnalyst",
    "GPUEconomicsAnalyst",
    "PowerBottleneckAnalyst",
    "LeadLagResearcher",
    "DrawdownLabelResearcher",
    "WalkForwardValidator",
    "ModelChallenger",
    "MLCalibrationGovernor",
)
assert len(NAMES) == 10 and sum(WEIGHTS.values()) == 1050
MIN_SUPERVISED_TRAIN = 36
OOS_MIN = 12


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def decimal(value):
    if isinstance(value, bool):
        raise ValueError("Invalid numeric boolean")
    x = Decimal(str(value))
    if not x.is_finite():
        raise ValueError("Nonfinite SEC or market number")
    return x


def fmt(value):
    return str(decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _validate(v17, v18, spx, shadow, as_of):
    if not isinstance(as_of, dt.date) or isinstance(as_of, dt.datetime):
        raise ValueError("Research cutoff date must be a date")
    if (v17.get("schema") != "aics-24m-multi-node-first-public-date-research-overlay-v1"
        or v18.get("schema") != "aics-v18-24m-private-credit-original-sec-expost-research-overlay-v1"
        or v18.get("historical_pit_source_bytes_independently_attested") is not False
        or v18.get("scores_are_expost_not_preregistered") is not True
        or v18.get("full_11node_index_months") != 0
        or v18.get("aics_sp500_spread_months") != 0
        or v18.get("trades_created") is not False
        or v17.get("node_weights") != WEIGHTS
        or spx.get("symbol") != "GSPC"
        or len(spx.get("points",[])) != 24
        or shadow.get("node") != "AI Equities"
        or shadow.get("node_weight") != 100
        or shadow.get("approved_historical_constituency") is not False
        or shadow.get("original_provider_historical_vintages_attested") is not False
        or shadow.get("score_eligible_at_2026_10_31") is not False
        or len(v18.get("monthly_last_weekday_market_proxy", [])) != 24
        or len(v18.get("monthly_calendar_end_research", [])) != 24):
        raise ValueError("Unexpected research input or unsupported certification")
    months = [r["month"] for r in v18["monthly_last_weekday_market_proxy"]]
    if months != [p["month"] for p in spx["points"]]:
        raise ValueError("Market sources and eligible observations have different months")
    for row in v18["monthly_last_weekday_market_proxy"]:
        if dt.date.fromisoformat(row["cutoff_date"]) > as_of:
            raise ValueError("Historical availability cutoff in the future")
        if (row.get("full_aics") is not None or row.get("aics_sp500_spread") is not None
            or row.get("historical_pit_certified") is not False):
            raise ValueError("Improper AICS promotion")
        if set(row["node_scores"]) | set(row["missing_nodes"]) != set(WEIGHTS):
            raise ValueError("AICS roster cannot be partially erased")
        if set(row["node_scores"]) & set(row["missing_nodes"]):
            raise ValueError("Duplicate known and missing node")
        for value in row["node_scores"].values():
            if dt.date.fromisoformat(value["research_eligible_date"]) > dt.date.fromisoformat(row["cutoff_date"]):
                raise ValueError("Source lookahead")
            if not 0 <= decimal(value["score"]) <= 100:
                raise ValueError("Invalid original node stress")
    symbols = shadow.get("research_symbols")
    if (not isinstance(symbols, list) or len(symbols) != 7
        or len(set(symbols)) != 7):
        raise ValueError("AI Equities candidate roster invalid")
    if dt.date.fromisoformat(shadow["research_asof"]) > as_of:
        raise ValueError("Cannot use an AI Equities roster established in the future")


def sec_financial_analyst(finance):
    if finance is None:
        return {"evidence_status":"BLOCKED_NO_CURRENT_SEC_NUMERIC_RECEIPTS",
                "direct_quarter_pairs":0,"node_scores_added":0}
    if (finance.get("schema") != "aics-sec-direct-three-month-cashflow-research-candidate-v1"
        or finance.get("source_bytes_historical_first_filing_verified") is not False
        or finance.get("independently_pit_attested") is not False
        or finance.get("node_scores_promoted") != 0
        or finance.get("full_11_node_aics") is not None
        or finance.get("weights_total") != 1050):
        raise ValueError("Invalid financial reconciliation or promoted SEC values")
    pairs = finance["candidate_quarter_pairs"]
    for pair in pairs:
        if (pair["accounting_period_3months"] is not True
            or pair["original_first_document_bytes_verified"] is not False
            or pair["historically_independent_pit_attested"] is not False
            or pair["aics_node_score"] is not None
            or pair["source_scope_consistency"] !=
               "single_accession_same_period_same_issuer_original_snapshot"):
            raise ValueError("SEC financial pair not a direct research candidate")
    return {
        "evidence_status":"CURRENT_SEC_SNAPSHOT_DIRECT_PERIOD_RESEARCH_CANDIDATES",
        "current_snapshot_numeric_rows":finance["original_numeric_rows_inspected"],
        "direct_quarter_pairs":len(pairs),
        "unique_issuers_with_direct_pairs":len({p["issuer_cik"] for p in pairs}),
        "ytd_records_rejected_without_subtraction":
            finance["reasons"].get("long_ytd_or_nonquarter_duration",0),
        "unit_and_source_match":"single_issuer_accession_period_and_snapshot",
        "earliest_public_timestamp_attested":False,
        "node_scores_added":0,
    }


def ai_equities_historian(shadow, as_of):
    return {
        "research_candidate_roster":shadow["research_symbols"],
        "research_roster_first_recorded_date":shadow["research_asof"],
        "earliest_possible_forward_roster_date":shadow["research_asof"],
        "historically_fixed_basket_proven":False,
        "approved_historical_2024_2026_points":0,
        "observations_retrospective_whatif":len(shadow["observations"]),
        "historical_corporate_actions_verified":False,
        "need":"Original historical contemporaneous constituents, splits, dividends and price publication timestamps",
        "scoring_history_backfilled":False,
    }


def credit_contagion_analyst(v18):
    current=v18["monthly_last_weekday_market_proxy"][-1]["node_scores"]
    nodes=("Private Credit","Insurers","Neoclouds","SPV")
    observed={n:current[n]["score"] if n in current else None for n in nodes}
    return {
        "nodes_examined":list(nodes),
        "latest_research_node_scores":observed,
        "source_level_credit_exposure_edges_verified":0,
        "verified_counterparty_exposure_matrix":None,
        "transmission_simulation":None,
        "ready_for_network_propagation":False,
        "reason":"No dated lender/borrower dollar exposure, recourse and SPV consolidation map",
        "weights_changed":False,
    }


def gpu_economics_analyst(finance, v18):
    pairs=finance["candidate_quarter_pairs"] if finance is not None else []
    hyp_ciks={str(c) for c in (789019,1018724,1652044,1326801)}
    relevant=[p for p in pairs if p["issuer_cik"] in hyp_ciks]
    current=v18["monthly_last_weekday_market_proxy"][-1]["node_scores"].get("Hyperscalers")
    return {
        "actual_hyperscaler_direct_cashflow_pairs":len(relevant),
        "latest_available_hyperscaler_research_stress_score":
            current["score"] if current else None,
        "gpu_specific_capex_separated":False,
        "gpu_utilization_actual_original_verified":False,
        "gpu_revenue_attribution_verified":False,
        "hardware_obsolescence_assumptions_locked":False,
        "payback_months":None,
        "ready_for_gpu_economics_score":False,
        "reason":"CFO and company-wide cash PPE are not attributable GPU capital cost or contracted GPU cashflow",
    }


def power_bottleneck_analyst(waves, v18):
    found = None
    if waves is not None:
        if waves.get("schema") != "aics-ten-real-source-acquisition-waves-with-companyfacts-v1":
            raise ValueError("Wrong source wave manifest")
        if waves.get("rounds") != 10 or waves.get("fixed_weights_total") != 1050:
            raise ValueError("Wrong primary publisher roster")
        for wave in waves["rounds_report"]:
            if wave["agent"] == "Power/Data Centers":
                found=next((x for x in wave["operations"]
                            if x["source_id"]=="EIA_RTO_DEMAND"),None)
    current=v18["monthly_last_weekday_market_proxy"][-1]["node_scores"].get("Power/Data Centers")
    return {
        "eia_rto_current_source_status":found["status"] if found else "source_not_provided",
        "current_power_node_research_candidate":current["score"] if current else None,
        "site_level_data_center_meter_data_verified":False,
        "interconnection_wait_time_originals_verified":False,
        "regional_grid_demand_equal_to_ai_specific_load":False,
        "bottleneck_forecast":None,
        "ready_for_dynamic_power_node_upgrade":False,
    }


def lead_lag_researcher(v18, spx):
    """As-of visible features and *subsequent observed* outcomes, no model fit."""
    rows=v18["monthly_last_weekday_market_proxy"]
    prices=[decimal(p["sp500_month_end_close"]) for p in spx["points"]]
    if any(p<=0 for p in prices):
        raise ValueError("Bad historical market index")
    eligible_counts={}
    for node in WEIGHTS:
        count=0
        for i in range(len(rows)-1):
            if node not in rows[i]["node_scores"]:
                continue
            # This observed next-month close is a retrospective LABEL, not
            # a contemporaneous feature. Nothing is trained or promoted here.
            if dt.date.fromisoformat(rows[i]["node_scores"][node]["research_eligible_date"]) > dt.date.fromisoformat(rows[i]["cutoff_date"]):
                raise ValueError("Lead lag feature violates information cutoff")
            count+=1
        eligible_counts[node]=count
    return {
        "outcome_horizon_months":1,
        "retrospective_1month_sp500_outcomes":len(rows)-1,
        "feature_outcome_pairs_by_node":eligible_counts,
        "historical_source_data_pit_attested":False,
        "lead_lag_correlations_ex_ante_validated":False,
        "causal_influence_established":False,
        "forecasting_weights_updated":False,
    }


def drawdown_label_researcher(spx):
    """Grounded future-realized min-close drawdown labels, not a prediction."""
    prices=[decimal(x["sp500_month_end_close"]) for x in spx["points"]]
    out={}
    for horizon in (1,3,6):
        values=[]
        for i in range(len(prices)-horizon):
            trough=min(prices[i+1:i+1+horizon])
            values.append(100*(trough/prices[i]-1))
        out[str(horizon)]={
            "retrospective_observed_outcome_labels":len(values),
            "historical_trough_below_minus_5_pct":sum(x<=-5 for x in values),
            "historical_trough_below_minus_10_pct":sum(x<=-10 for x in values),
            "forecast_probability":None,
        }
    return {
        "source":"original_24_month_sp500_month_end_closes",
        "drawdown_label_horizons":out,
        "label_is_future_result_not_feature":True,
        "historical_24m_oos_predictive_model":False,
        "supervised_training_executed":False,
    }


def walk_forward_validator(v18, labels):
    max_observed=sum(x["retrospective_observed_outcome_labels"]
                     for x in labels["drawdown_label_horizons"].values())
    available=len(v18["monthly_last_weekday_market_proxy"])
    return {
        "past_months_observed":available,
        "retrospective_outcome_label_pairs_across_horizons":max_observed,
        "pre_registered_historical_score_formula":False,
        "original_historical_pit_delivery_attested":False,
        "independent_out_of_sample_months":0,
        "walk_forward_trained_candidates":0,
        "forecast_skill_reportable":False,
        "status":"BLOCKED_RESEARCH_HISTORY_IS_EX_POST_AND_PIT_UNVERIFIED",
        "required_next":"Freeze formula and constituents prospectively; then collect as-of features and realized labels for truly untouched periods",
    }


def model_challenger(spx, validation):
    """Observed naïve zero-next-month return MAE; not AICS predictive success."""
    closes=[decimal(x["sp500_month_end_close"]) for x in spx["points"]]
    errors=[abs(100*(closes[i]/closes[i-1]-1))
            for i in range(1,len(closes))]
    if len(errors)!=23 or any(not x.is_finite() for x in errors):
        raise ValueError("Not 23 actual close/close observations")
    return {
        "baseline":"zero_return_one_month_naive_unchanged_price",
        "retrospective_monthly_baseline_absolute_error_pct":fmt(sum(errors)/len(errors)),
        "observed_next_month_pairs":len(errors),
        "aics_supervised_candidate_fitted":False,
        "aics_excess_predictive_skill_vs_baseline":None,
        "baseline_ex_ante_previously_proven":False,
        "release_comparison_status":"BLOCKED_UNTIL_SAME_VINTAGE_OUT_OF_SAMPLE",
    }


def ml_calibration_governor(v18, wf, challenger, finance):
    return {
        "supervised_model_candidate_ready":False,
        "realized_outcome_labels":23,
        "minimum_calibration_training_observations":MIN_SUPERVISED_TRAIN,
        "minimum_untouched_oos_labels":OOS_MIN,
        "independent_oos_labels_confirmed":0,
        "current_primary_numeric_candidate_pairs":(
            len(finance["candidate_quarter_pairs"]) if finance else 0),
        "historical_model_rule_pre_registered":False,
        "cross_validated_prediction_quality":None,
        "learned_new_node_weights":None,
        "production_weight_total_unchanged":1050,
        "ready_to_train_supervised_model":False,
        "calibration_action":"NO_WEIGHT_CHANGE_OR_PREDICTIVE_PROMOTION",
        "prerequisites":["prospective issuer universe", "historical source-public timestamps",
                         "unchanged label definition", "adequate training and untouched OOS",
                         "predictive comparison against fixed naive baseline"],
    }


def run(*, v17, v18, spx, shadow, finance=None, waves=None, as_of=None):
    as_of=as_of or dt.datetime.now(dt.timezone.utc).date()
    _validate(v17,v18,spx,shadow,as_of)
    if finance is not None:
        if dt.date.fromisoformat(finance["as_of"]) > as_of:
            raise ValueError("SEC numeric receipt observed after as-of")
    payloads = [
        sec_financial_analyst(finance),
        ai_equities_historian(shadow, as_of),
        credit_contagion_analyst(v18),
        gpu_economics_analyst(finance,v18),
        power_bottleneck_analyst(waves,v18),
        lead_lag_researcher(v18,spx),
        drawdown_label_researcher(spx),
    ]
    payloads += [
        walk_forward_validator(v18,payloads[6]),
    ]
    payloads += [
        model_challenger(spx,payloads[7]),
    ]
    # The original objective: compare current AI-chain stress with the
    # 2000 buildout crash AND 2008 shadow-banking funding panic.
    # Keep it inside the existing ModelChallenger role: ten model
    # improvement agents remain ten, historical numeric analogs remain null.
    payloads[8]["historical_crisis_analog"] = historical_crisis_analog(v18)
    # An original SEC +14 earnings/cash spending imbalance layer is tracked
    # SEPARATELY from the 11-node stress index and 2000/2008 numeric analog.
    # The earnings data are retrospective source research, not proof of
    # historically archived bytes or contemporaneous AI-specific CapEx.
    imbalance = early_imbalance_build(
        read(EARLY_CASH_2025),
        read(EARLY_CASH_2025Q4),
        read(EARLY_CASH_2026Q2),
        read(EARLY_CASH_2026Q3),
        q1=read(EARLY_CASH_2026Q1), as_of=as_of)
    if (imbalance["full_11_node_aics"] is not None
            or imbalance["similarity_to_2000_pct"] is not None
            or imbalance["similarity_to_2008_pct"] is not None
            or imbalance["primary_source_document_bytes_independently_historical_pit_attested"] is not False):
        raise ValueError("Precrisis cash imbalance improperly promoted")
    bridge = spv_bridge_build(
        read(SPV_CORE), read(SPV_CLOUD), read(SPV_NSCALE),
        read(SPV_DFS), imbalance=imbalance, as_of=as_of)
    if (bridge["full_11node_aics"] is not None
            or bridge["verified_2008_funding_contagion_matrix"] is not None
            or bridge["forecast_crisis_probability"] is not None
            or bridge["weights_total_unchanged"] != 1050
            or bridge["trades_created"] is not False):
        raise ValueError("Original SPV borrowing and economic cashflow cannot promote a crisis probability")
    payloads[2]["verified_instrument_balance_edges_not_named_lender_exposure"] = (
        bridge["proven_same_date_coreweave_facility_balance_edges"])
    payloads[2]["named_lender_current_exposure_edges"] = bridge["named_lender_to_borrower_current_exposure_edges"]
    payloads[2]["legal_recourse_and_dfs_rent_ledgers_only"] = (
        bridge["coreweave"] is not None and bridge["nscale"] is not None)
    payloads[8]["spv_recourse_and_buildout_research"] = {
        "coreweave_reported_spv_debt_usd_m":
            bridge["coreweave"]["separate_facility_reported_debt_sum_usd_m"] if bridge["coreweave"] else None,
        "coreweave_separate_facility_ceiling_usd_m":
            bridge["coreweave"]["separate_facility_ceiling_sum_usd_m"] if bridge["coreweave"] else None,
        "nscale_combined_ward_nc_gpu_contractual_ceiling_usd_m":
            bridge["nscale"]["combined_two_gpu_ceiling_usd_m"] if bridge["nscale"] else None,
        "nscale_lease_initial_rent_usd_m_not_drawn_debt":
            bridge["nscale"]["dell_initial_term_rent_usd_m_includes_financing_charges"] if bridge["nscale"] else None,
        "nscale_gpu_drawn_total_usd_m": None,
        "parent_enforceable_guarantee_total_usd_m": None,
        "named_lender_exposure_edges_verified": 0,
        "2008_funding_contagion_probability": None,
        "source_research_only": True,
    }
    payloads[8]["early_cash_imbalance_research"] = {
        "source_periods": [
            {"period":q["period"],"issuer_count":q["issuer_count"],
             "cash_ppe_over_ocf_pct":q["cash_ppe_over_ocf_pct"],
             "cash_gap_usd_m":q["four_issuer_cash_gap_usd_m"],
             "source_eligible_at":q["source_eligible_at"]}
            for q in imbalance["complete_or_partial_quarters"]],
        "same_issuer_q3_yoy":imbalance["same_issuer_yoy_q3"],
        "funding_crisis_2008_probability":None,
        "historical_2000_similarity_pct":None,
        "historical_2008_similarity_pct":None,
        "new_prod_aics_weight":None,
    }
    payloads += [
        ml_calibration_governor(v18,payloads[7],payloads[8],finance),
    ]
    if len(payloads)!=10:
        raise ValueError("All 10 model improvement agents must execute")
    agents=[]
    for name, result in zip(NAMES,payloads):
        agents.append({
            "name":name,
            "execution":"completed",
            "research_result":result,
            "new_aics_score_approved":False,
            "production_weights_changed":False,
            "trades_created":False,
        })
    return {
        "schema":"aics-v23-ten-model-improvement-agents-research-v1",
        "as_of":as_of.isoformat(), "additional_model_agents":10,
        "existing_source_agents":10, "existing_research_analytics_agents":10,
        "total_distinct_workflow_agent_roles":30,
        "actual_model_improvement_agents_executed":len(agents),
        "agents":agents,
        "original_quarter_finance_audit_loaded":finance is not None,
        "live_source_wave_manifest_loaded":waves is not None,
        "original_sec_numeric_scope_unverified":True,
        "full_aics":None,"aics_sp500_spread":None,
        "historical_provider_pit_certified":False,
        "trained_supervised_forecast":False,
        "untouched_oos_forecast_accuracy":None,
        "aics_node_weights_modified":False,
        "trades_created":False,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=OUTPUT)
    parser.add_argument("--sec-finance-audit",type=Path,default=FIN_AUDIT)
    parser.add_argument("--source-waves",type=Path,default=SOURCE_WAVES)
    args=parser.parse_args()
    finance=read(args.sec_finance_audit) if args.sec_finance_audit.exists() else None
    waves=read(args.source_waves) if args.source_waves.exists() else None
    result=run(v17=read(V17),v18=read(V18),spx=read(SPX),
               shadow=read(AI_SHADOW),finance=finance,waves=waves)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({
        "model_agents_executed":10,
        "cashflow_period_pairs":result["agents"][0]["research_result"]["direct_quarter_pairs"],
        "verified_ai_equities_history":False,
        "oos_forecast_skill":None,
        "original_scores_promoted":0,
        "total_agent_roles":30,
        "full_aics":None,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
