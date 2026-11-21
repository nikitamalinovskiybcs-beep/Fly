"""One auditable 30-role AICS research cycle: 10 live source waves + 10
historical-analysis roles + 10 model-improvement roles.

The source-wave and finance files must be produced by the existing live GitHub
workflow. Historical V17/V18 overlays are retrospective research, never training
on newly captured SEC receipts. This coordinator makes proposals, not model
promotions, index scores, crisis probabilities, or trades.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_ten_node_agents import NODE_TASKS
from scripts.aics_ten_analysis_agents import run_agents, read as read_analysis, V17, V18, SPX
from scripts.aics_ten_model_improvement_agents import (
    run as run_improvement, read as read_improvement, AI_SHADOW,
)

ROOT = Path("aics_data/agent_runs/ten_real_collection_rounds")
WAVES = ROOT / "ten_rounds_manifest.json"
FINANCE = ROOT / "sec_direct_quarter_cashflow_gate.json"
OUTPUT = ROOT / "aics_thirty_agent_research_cycle.json"


def _input_checks(waves, finance):
    if (waves.get("schema") != "aics-ten-real-source-acquisition-waves-with-companyfacts-v1"
            or waves.get("rounds") != 10
            or waves.get("source_agents") != 10
            or waves.get("fixed_weights_total") != 1050
            or waves.get("production_weights_changed") is not False
            or waves.get("trades_created") is not False
            or waves.get("complete_index") is not None
            or waves.get("independent_sp500_skill") is not None
            or waves.get("independently_pit_verified_node_count") != 0):
        raise ValueError("Invalid live source-wave lineage or unsafe model promotion")
    rows = waves.get("rounds_report")
    if (not isinstance(rows, list) or len(rows) != 10
            or [r["round"] for r in rows] != list(range(1, 11))
            or [r["agent"] for r in rows] != list(NODE_TASKS)
            or any(r["weight_unchanged"] != WEIGHTS[r["agent"]] for r in rows)
            or any(r.get("research_usable_scored_node") is not False for r in rows)):
        raise ValueError("Source-wave role/weight/score audit failed")
    total = waves.get("total_http_attempts")
    archived = waves.get("successful_http_archives")
    if (not isinstance(total, int) or isinstance(total, bool) or total < 1
            or not isinstance(archived, int) or isinstance(archived, bool)
            or archived < 0 or archived > total):
        raise ValueError("No accountable real publisher requests")
    for row in rows:
        if not isinstance(row.get("operations"), list):
            raise ValueError("Missing live source operation ledger")
        for op in row["operations"]:
            if op.get("node_score_eligible") is True:
                raise ValueError("A current source-wave receipt cannot certify a node score")
    if (finance.get("schema") != "aics-sec-direct-three-month-cashflow-research-candidate-v1"
            or finance.get("weights_total") != 1050
            or finance.get("source_bytes_historical_first_filing_verified") is not False
            or finance.get("independently_pit_attested") is not False
            or finance.get("node_scores_promoted") != 0
            or finance.get("full_11_node_aics") is not None
            or finance.get("production_weights_changed") is not False
            or finance.get("trades_created") is not False
            or finance.get("original_numeric_rows_inspected") !=
                 waves.get("actual_numeric_facts_extracted_current_sec_snapshots")
            or finance.get("direct_original_3month_pair_candidates") !=
                 len(finance.get("candidate_quarter_pairs", []))):
        raise ValueError("Unverified or inconsistent SEC finance receipts")
    cutoff = dt.datetime.fromisoformat(waves["captured_at_utc"].replace("Z", "+00:00"))
    if cutoff.tzinfo is None or cutoff.utcoffset() != dt.timedelta(0):
        raise ValueError("Capture must have an explicit UTC timestamp")
    as_of = cutoff.date()
    if dt.date.fromisoformat(finance["as_of"]) != as_of:
        raise ValueError("SEC finance cutoff differs from source wave date")
    for pair in finance["candidate_quarter_pairs"]:
        if (pair.get("aics_node_score") is not None
                or pair.get("historically_independent_pit_attested") is not False
                or pair.get("original_first_document_bytes_verified") is not False
                or dt.date.fromisoformat(pair["research_eligible_at_date_proxy"]) > as_of):
            raise ValueError("Ineligible direct cashflow pair")
    return as_of


def build(*, waves, finance, v17, v18, spx, shadow):
    """Deterministic evidence-to-improvement research loop; no live network."""
    as_of = _input_checks(waves, finance)
    analysis = run_agents(v17=v17, v18=v18, sp500=spx, as_of=as_of)
    improved = run_improvement(v17=v17, v18=v18, spx=spx, shadow=shadow,
                               finance=finance, waves=waves, as_of=as_of)
    if (analysis["agents_count"] != 10
            or len(analysis["results"]) != 10
            or any(x["status"] != "research_pass" for x in analysis["results"])
            or analysis["complete_aics_index"] is not None
            or analysis["aics_sp500_spread"] is not None
            or analysis["certified_pit"] is not False
            or analysis["production_model_updated"] is not False
            or analysis["trades_created"] is not False
            or improved["actual_model_improvement_agents_executed"] != 10
            or len(improved["agents"]) != 10
            or any(x["execution"] != "completed" or
                   x["new_aics_score_approved"] is not False or
                   x["production_weights_changed"] is not False or
                   x["trades_created"] is not False for x in improved["agents"])
            or improved["original_quarter_finance_audit_loaded"] is not True
            or improved["live_source_wave_manifest_loaded"] is not True
            or improved["total_distinct_workflow_agent_roles"] != 30
            or improved["full_aics"] is not None
            or improved["aics_sp500_spread"] is not None
            or improved["trained_supervised_forecast"] is not False
            or improved["historical_provider_pit_certified"] is not False
            or improved["aics_node_weights_modified"] is not False
            or improved["trades_created"] is not False):
        raise ValueError("AICS combined 30-role output failed independent safety gates")
    apr = analysis["results"]
    imp = improved["agents"]
    if (apr[9]["result"]["production_promotion"] != "BLOCKED"
            or imp[7]["research_result"]["independent_out_of_sample_months"] != 0
            or imp[9]["research_result"]["ready_to_train_supervised_model"] is not False):
        raise ValueError("AICS research improperly promoted to forecasting")

    unavailable = waves.get("unavailable_source_keys", [])
    if not isinstance(unavailable, list):
        raise ValueError("Source failures must be explicitly reported")
    earlier = imp[8]["research_result"]["early_cash_imbalance_research"]
    periods = earlier["source_periods"]
    q1_complete = any(
        str(p.get("period")).replace("-", " ").upper() in
        ("2026 Q1", "2026Q1", "2026 Q1 2026") and p.get("issuer_count") == 4
        for p in periods
    )
    topology = imp[8]["research_result"]["typed_lender_borrower_guarantor_network_research"]
    if (
        topology["source_gated_legal_relationship_edges"] != 9
        or topology["historical_facility_debt_edges"] != 2
        or topology["named_historical_financing_provider_relationships"] != 2
        or topology["named_affiliate_guarantor_links"] != 2
        or topology["nscale_kvandal_august_draws_usd_m_not_outstanding"] != "107.2"
        or topology["current_named_lender_borrower_exposure_edges"] != 0
        or topology["cross_instrument_total_credit_exposure_usd_m"] is not None
        or topology["verified_current_lender_contagion_matrix"] is not None
        or topology["2008_crisis_similarity_pct"] is not None
        or topology["new_spv_stress_score"] is not None
    ):
        raise ValueError("Improper current exposure inferred from historical legal network")
    refinancing = imp[8]["research_result"]["contractual_refinancing_maturity_research"]
    if (
        refinancing["eligible_contractual_terms"] != 3
        or refinancing["known_maturity_within_365d_count"] != int(0 <= (dt.date(2027,10,16)-as_of).days <= 365)
        or refinancing["earliest_contractual_maturity"] != "2027-10-16"
        or refinancing["coreweave_named_administrative_agents"] != 2
        or refinancing["citi_named_as_nebius_arranger_and_lender"] is not True
        or refinancing["contractual_maturity_is_actual_total_principal_due"] is not False
        or refinancing["current_named_lender_dollar_exposure_edges"] != 0
        or refinancing["actual_refinancing_need_usd_m"] is not None
        or refinancing["actual_coupon_including_term_sofr"] is not None
        or refinancing["historical_PIT_independently_attested"] is not False
        or refinancing["crisis_probability"] is not None
    ):
        raise ValueError("Cannot turn contractual refinancing dates into known current credit debt")
    funding=imp[8]["research_result"]["same_issuer_real_cashflow_financing_research"]
    if (funding["issuer_quarters_original_SEC_eligible"]!=4
        or funding["coreweave_q2_ocf_minus_cash_capex_usd_m"]!="-5743"
        or funding["coreweave_q2_net_financing_cash_usd_m"]!="10071"
        or funding["coreweave_q2_qoq_gap_deterioration_usd_m"]!="-1032"
        or funding["nebius_q2_ocf_minus_cash_purchases_usd_m"]!="-3411.3"
        or funding["nebius_q2_net_financing_cash_usd_m"]!="2864.9"
        or funding["nebius_q2_qoq_gap_deterioration_usd_m"]!="-3196.4"
        or funding["named_current_lender_funded_dollar_amount_usd_m"] is not None
        or funding["ddtl4_vs_ddtl5_same_instrument_repricing_established"] is not False
        or funding["matched_instrument_spread_repricing_bps"] is not None
        or funding["financial_contagion_causality_established"] is not False
        or funding["production_score"] is not None):
        raise ValueError("Matched original financing data must not imply reprice or contagion")
    interest=imp[8]["research_result"]["interest_repo_dual_clock_research"]
    sec_date_should_pass=as_of>=dt.date(2026,11,26)
    if (interest["coreweave_Q3_IR_interest_to_revenue_pct"]!="23.1"
        or interest["coreweave_Q3_IR_interest_expense_usd_m"]!=846
        or interest["coreweave_Q3_SEC_eligible_at"]!="2026-11-26"
        or interest["coreweave_Q3_SEC_date_gate_passed"] is not sec_date_should_pass
        or interest["interest_Q3_public_IR_only_not_AICS_eligible"] is not True
        or interest["repo_latest_month"]!="2026-10-31"
        or interest["repo_sofr_minus_iorb_bps"]!=4
        or interest["repo_monthly_spread_is_not_borrower_loan_repricing"] is not True
        or interest["same_loan_real_repricing_points"]!=0
        or interest["same_loan_credit_spread_change_bps"] is not None
        or interest["current_lender_debt_exposure_usd_m"] is not None
        or interest["independent_24m_OOS_skill"] is not None
        or interest["model_risk_score"] is not None):
        raise ValueError("IR and market repo rates cannot certify a current AICS credit warning")
    direct_pairs = imp[0]["research_result"]["direct_quarter_pairs"]
    if direct_pairs != finance["direct_original_3month_pair_candidates"]:
        raise ValueError("Agent cashflow evidence disagrees with original finance gate")

    # Proposed work is selected only from observed fail-closed limitations.
    experiments = []
    if not q1_complete:
        experiments.append({
            "priority": len(experiments) + 1,
            "experiment": "2026_Q1_4_ISSUER_CASHFLOW_GAP",
            "observed_gap": "No complete 2026 Q1 original-source cohort in cash-imbalance panel",
            "completion_evidence": "Four comparable original SEC quarterly OCF and cash PP&E statements, dated SEC+14",
            "decision": "RESEARCH",
        })
    if (finance["source_bytes_historical_first_filing_verified"] is False):
        experiments.append({
            "priority": len(experiments) + 1,
            "experiment": "ORIGINAL_SEC_NUMERIC_SOURCE_TO_NODE",
            "observed_direct_quarter_candidates": direct_pairs,
            "completion_evidence": "First-filed SEC 10-Q/10-K originals, contemporaneous provenance, reconciled issuer/period/unit, immutable node journal",
            "decision": "RESEARCH",
        })
    if imp[1]["research_result"]["approved_historical_2024_2026_points"] == 0:
        experiments.append({
            "priority": len(experiments) + 1,
            "experiment": "AI_EQUITIES_HISTORICAL_CONSTITUENTS",
            "completion_evidence": "Contemporaneous 2024-2026 constituent roster, splits, dividends, original quotes and availability timestamps",
            "decision": "RESEARCH",
        })
    spv_research = imp[8]["research_result"]["spv_recourse_and_buildout_research"]
    credit_research = imp[2]["research_result"]
    if (
        credit_research["verified_instrument_balance_edges_not_named_lender_exposure"] != 2
        or credit_research["named_lender_current_exposure_edges"] != 0
        or spv_research["coreweave_reported_spv_debt_usd_m"] != 3938
        or spv_research["coreweave_separate_facility_ceiling_usd_m"] != 11600
        or spv_research["nscale_combined_ward_nc_gpu_contractual_ceiling_usd_m"] != 3050
        or spv_research["nscale_lease_initial_rent_usd_m_not_drawn_debt"] != 2540
        or spv_research["nscale_gpu_drawn_total_usd_m"] is not None
        or spv_research["parent_enforceable_guarantee_total_usd_m"] is not None
        or spv_research["named_lender_exposure_edges_verified"] != 0
        or spv_research["2008_funding_contagion_probability"] is not None
        or spv_research["source_research_only"] is not True
    ):
        raise ValueError("SPV original-data bridge cannot be confused with lender exposures")
    if imp[2]["research_result"]["source_level_credit_exposure_edges_verified"] == 0:
        experiments.append({
            "priority": len(experiments) + 1,
            "experiment": "SPV_CREDIT_RECOURSE_NETWORK",
            "documented_named_spv_facility_balances": 2,
            "coreweave_same_date_reported_debt_usd_m": 3938,
            "named_current_lender_borrower_exposure_edges": 0,
            "historical_legal_relationships_mapped": 9,
            "named_historical_provider_relationships": 2,
            "named_affiliate_guarantors_mapped": 2,
            "new_sec_source_research_maturity_terms_count": 3,
            "real_q2_2026_issuers_with_same_issuer_cash_financing_bridge":2,
            "actual_cashflow_financing_gap_explained_but_not_bank_risk_calibrated":True,
            "nebius_contractual_maturity": "2027-10-16",
            "nebius_bridge_credit_dollar_exposure_to_citi_verified": False,
            "completion_evidence": "Original named lender-to-borrower outstanding exposure, dates, recourse and enforceable guarantees; never add commitments, lease rents or consolidated balances",
            "decision": "RESEARCH",
        })
    if imp[7]["research_result"]["independent_out_of_sample_months"] == 0:
        experiments.append({
            "priority": len(experiments) + 1,
            "experiment": "FROZEN_FORMULA_WALK_FORWARD",
            "completion_evidence": "Prior-frozen 11-node formulas, 24 untouched forward months, baseline score and independently verified outcomes",
            "decision": "BLOCKED_UNTIL_DATA",
        })
    if unavailable:
        experiments.append({
            "priority": len(experiments) + 1,
            "experiment": "RETRY_MISSING_PRIMARY_SOURCES",
            "missing_source_ids": unavailable,
            "completion_evidence": "Genuine original publisher responses and retained immutable byte hashes; no zero-filled substitutes",
            "decision": "RESEARCH",
        })
    return {
        "schema": "aics-30-agent-evidence-to-improvement-loop-v1",
        "cutoff_date": as_of.isoformat(),
        "observed_source_timestamp_utc": waves["captured_at_utc"],
        "agent_groups": {
            "live_source_wave_agents": 10,
            "historical_research_analysis_agents": 10,
            "model_improvement_research_agents": 10,
            "total_distinct_roles_executed": 30,
        },
        "source_collection": {
            "rounds": 10,
            "http_attempts": waves["total_http_attempts"],
            "successful_http_archives": waves["successful_http_archives"],
            "unique_source_ids_archived": waves["unique_original_source_ids_archived"],
            "unavailable_source_ids": unavailable,
            "current_numeric_snapshot_rows": finance["original_numeric_rows_inspected"],
            "direct_quarter_research_candidates": direct_pairs,
            "historical_first_document_receipt_verified": False,
        },
        "analysis": {
            "market_research_observability_pct": apr[2]["result"]["market"]["research_observability_pct"],
            "calendar_research_observability_pct": apr[2]["result"]["calendar"]["research_observability_pct"],
            "market_proxy_months": 24,
            "historical_full_aics_months": 0,
            "retrospective_source_anomaly_events": apr[8]["result"]["source_eligible_events"],
            "research_attention_flags": apr[8]["result"]["research_attention_flags"],
            "analysis_is_previous_V17_V18_not_new_sec_score_ingestion": True,
        },
        "model_improvement": {
            "model_challenger_executed": True,
            "historical_2000_2008_similarity_percent": None,
            "2026_q1_4issuer_cashflow_complete": q1_complete,
            "credit_exposure_edges_verified": 0,
            "v28_source_dated_credit_legal_edges": 9,
            "v29_contractual_maturity_records": 3,
            "v30_real_q2_issuer_funding_mechanisms_reconciled":2,
            "v31_q3_coreweave_ir_interest_to_revenue_pct_research_only":"23.1",
            "v31_q3_sec_date_eligible_at":"2026-11-26",
            "v31_sec_10q_date_gate_passed":sec_date_should_pass,
            "v31_repo_oct2026_sofr_minus_iorb_bps_retrospective":4,
            "v31_matched_same_loan_repricing_observations":0,
            "v31_independently_confirmed_early_warning_skill":None,
            "v30_coreweave_net_q2_financing_usd_m":"10071",
            "v30_nebius_net_q2_financing_usd_m":"2864.9",
            "v30_mixed_equity_vs_debt_mechanisms_not_same_loan_repricing":True,
            "v30_crisis_causal_skill":None,
            "v29_2027_10_16_nebius_maturity_within_365_days": 0 <= (dt.date(2027,10,16)-as_of).days <= 365,
            "v29_2027_maturity_actual_refinancing_need_usd_m": None,
            "v29_coreweave_named_admin_agents": 2,
            "v29_nebius_citi_named_lender_funded_usd_m": None,
            "v28_named_historical_provider_relationships": 2,
            "v28_named_affiliate_guarantor_links": 2,
            "v28_current_named_lender_dollar_exposure_edges": 0,
            "v28_historical_legal_topology_not_funding_contagion": True,
            "same_date_named_spv_borrower_facility_balance_edges": 2,
            "coreweave_same_date_reported_debt_usd_m": 3938,
            "nscale_ward_nc_gpu_drawn_balance_usd_m": None,
            "spv_parent_enforceable_guarantee_total_usd_m": None,
            "cross_issuer_causal_funding_transmission_established": False,
            "approved_ai_equities_history_points": 0,
            "untouched_oos_months": 0,
            "new_predictive_skill": None,
        },
        "next_experiments": experiments,
        "cycle_decision": "RESEARCH_ONLY_NOT_AUTONOMOUS_PRODUCTION",
        "complete_11_node_aics": None,
        "crisis_probability": None,
        "weights_total_unchanged": sum(WEIGHTS.values()),
        "weights_changed": False,
        "trades_created": False,
        "verdict_mutated": False,
        "eligible_for_production_promotion": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--waves", type=Path, default=WAVES)
    parser.add_argument("--finance", type=Path, default=FINANCE)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = build(
        waves=read_analysis(args.waves),
        finance=read_analysis(args.finance),
        v17=read_analysis(V17),
        v18=read_analysis(V18),
        spx=read_analysis(SPX),
        shadow=read_improvement(AI_SHADOW),
    )
    report["lineage_sha256"] = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (args.waves, args.finance, V17, V18, SPX, AI_SHADOW)
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps({
        "agents": report["agent_groups"]["total_distinct_roles_executed"],
        "source_http_attempts": report["source_collection"]["http_attempts"],
        "source_raw_archives": report["source_collection"]["successful_http_archives"],
        "direct_cashflow_pairs": report["source_collection"]["direct_quarter_research_candidates"],
        "research_experiments": len(report["next_experiments"]),
        "production_index": None,
        "auto_promotion": False,
        "trades": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
