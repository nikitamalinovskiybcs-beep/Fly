"""AICS V32–V34 unattended research rotation: evidence, gaps, next experiments.

No synthetic prices, no unseen bank balances, no retroactive SEC eligibility.
Every scheduled run uses real archived source inventories and the verified
30-role cycle. No automatic code/weight/threshold changes or trades.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_v29_refinancing_maturity_overlay import TERMS,_checked
from scripts.aics_v30_cashflow_financing_bridge import FUNDING,CASH,SEC,build as funding_build,read
from scripts.aics_v31_interest_repo_dual_clock import INTEREST,REPO,build as interest_build

RUN_ROOT=Path("aics_data/agent_runs/ten_real_collection_rounds")
CYCLE=RUN_ROOT/"aics_thirty_agent_research_cycle.json"
OUT=RUN_ROOT/"aics_autonomous_v32_v34_research_rotation.json"


def num(x):
    if isinstance(x,bool):
        raise ValueError("Boolean financial value")
    n=Decimal(str(x))
    if not n.is_finite():raise ValueError("Nonfinite financial input")
    return n


def as_str(x):
    return format(x.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP),"f")


def build(contracts,funding,interest,cycle,*,as_of):
    if isinstance(as_of,str):as_of=dt.date.fromisoformat(as_of)
    if not isinstance(as_of,dt.date) or isinstance(as_of,dt.datetime):
        raise ValueError("UTC date cutoff required")
    rows=_checked(contracts)
    if (sum(WEIGHTS.values())!=1050
        or funding.get("schema")!="aics-v30-issuer-cashflow-financing-identity-source-gated-research-v1"
        or funding.get("as_of")!=as_of.isoformat()
        or interest.get("schema")!="aics-v31-dual-clock-interest-repo-matched-loan-research-v1"
        or interest.get("as_of")!=as_of.isoformat()
        or funding.get("full_aics") is not None
        or funding.get("crisis_probability") is not None
        or funding.get("trades_created") is not False
        or interest.get("full_11node_aics") is not None
        or interest.get("matched_same_loan_repricing_bps") is not None
        or interest.get("matched_same_loan_spread_repricing_events_verified")!=0
        or interest.get("Q3_SEC_10Q_date_gate_passed_as_of") is not (as_of>=dt.date(2026,11,26))
        or interest.get("trades_created") is not False
        or cycle.get("schema")!="aics-30-agent-evidence-to-improvement-loop-v1"
        or cycle.get("cutoff_date")!=as_of.isoformat()
        or cycle.get("agent_groups",{}).get("total_distinct_roles_executed")!=30
        or cycle.get("cycle_decision")!="RESEARCH_ONLY_NOT_AUTONOMOUS_PRODUCTION"
        or cycle.get("complete_11_node_aics") is not None
        or cycle.get("crisis_probability") is not None
        or cycle.get("weights_total_unchanged")!=1050
        or cycle.get("weights_changed") is not False
        or cycle.get("eligible_for_production_promotion") is not False
        or cycle.get("trades_created") is not False):
        raise ValueError("V32–V34 research rotation requires 30 real research roles and fails closed")
    if (cycle["model_improvement"]["credit_exposure_edges_verified"]!=0
        or cycle["model_improvement"]["v29_nebius_citi_named_lender_funded_usd_m"] is not None
        or cycle["model_improvement"]["v30_crisis_causal_skill"] is not None
        or cycle["model_improvement"]["v31_independently_confirmed_early_warning_skill"] is not None
        or cycle["model_improvement"]["v31_matched_same_loan_repricing_observations"]!=0):
        raise ValueError("Unsupported causal bank repricing or forecast")
    source_scored=cycle.get("source_collection",{})
    if (source_scored.get("http_attempts",0)<1
        or source_scored.get("successful_http_archives",0)<1
        or source_scored["successful_http_archives"]>source_scored["http_attempts"]):
        raise ValueError("No current real publisher receipt archive")
    raw_experiments=cycle.get("next_experiments",[])
    if (not isinstance(raw_experiments,list) or len(raw_experiments)<1
        or [e.get("priority") for e in raw_experiments]!=list(range(1,len(raw_experiments)+1))
        or any(e.get("decision") not in ("RESEARCH","BLOCKED_UNTIL_DATA") for e in raw_experiments)):
        raise ValueError("No evidence-ranked improvement queue")
    contracts_available=[r for r in rows if dt.date.fromisoformat(r["available_at"])<=as_of]
    ids=[r["facility_id"] for r in contracts_available]
    if len(ids)!=len(set(ids)):raise ValueError("Duplicate contractual facility")
    # Each known facility has only one pinned pricing document in current corpus.
    # Comparing 225bps DDTL 4.0 with 450bps DDTL 5.0 is NOT repricing.
    rate_events=[{
        "facility":r["facility_id"],
        "source_first_eligible":r["available_at"],
        "legal_maturity":r["contractual_maturity"],
        "floating_spread_bps":(r["daily_compounded_sofr_float_margin_bps"]
                               if r["facility_id"]!="NBIS_CITI_BRIDGE"
                               else r["term_sofr_initial_margin_bps"]),
        "pricing_amendment_verified":False,
        "realized_coupon":None,
        "funded_by_named_lender_usd_m":None,
    } for r in contracts_available]
    financing=[]
    for q in funding["issuer_quarter_observations"]:
        if q["period"]!="2026-Q2":continue
        if q["source_eligible_at"]>as_of.isoformat():
            raise ValueError("Future as-of issuer source leaked into financing")
        if q["issuer"] not in ("CoreWeave","Nebius"):
            raise ValueError("Unexpected neocloud issuer")
        if q["issuer"]=="CoreWeave":
            comp=q["q2_financing_components_usd_m"]
            if (num(comp["debt_issuance_net_of_costs"])!=13457
                or num(comp["debt_repayments"])!=-3884
                or num(q["net_financing_cash_usd_m"])!=10071):
                raise ValueError("Company-wide debt issuance/repaid amounts changed")
            observed_debt_net=num(comp["debt_issuance_net_of_costs"])+num(comp["debt_repayments"])
            equity_net=num(comp["private_placement_net_of_costs"])
        else:
            comp=q["q2_financing_components_usd_m"]
            if (num(comp["treasury_share_sale"])!=Decimal("2846.7")
                or num(comp["treasury_share_issuance_costs"])!=Decimal("-35.6")
                or num(q["net_financing_cash_usd_m"])!=Decimal("2864.9")):
                raise ValueError("Real equity proceeds corrupted")
            observed_debt_net=None
            equity_net=(num(comp["treasury_share_sale"])
                        +num(comp["treasury_share_issuance_costs"]))
        if (num(q["ocf_usd_m"])-num(q["cash_purchases_usd_m"])
            !=num(q["ocf_less_purchases_usd_m"])):
            raise ValueError("Q2 operation and cash PPE identity mismatch")
        financing.append({
            "issuer":q["issuer"],"available_at":q["source_eligible_at"],
            "actual_q2_ocf_minus_cash_purchases_usd_m":q["ocf_less_purchases_usd_m"],
            "actual_companywide_net_financing_cash_usd_m":q["net_financing_cash_usd_m"],
            "actual_cash_change_including_restricted_usd_m":
                q["net_change_cash_including_restricted_usd_m"],
            "observed_net_debt_issuance_less_repayments_usd_m":
                as_str(observed_debt_net) if observed_debt_net is not None else None,
            "observed_equity_issuance_or_treasury_sale_net_usd_m":as_str(equity_net),
            "net_debt_flows_are_not_ddtl4_ddtl5_specific":True,
            "equity_proceeds_not_bank_credit":True,
            "cash_gap_not_proof_loan_denial":True,
            "cash_runway_months":None,
            "current_lender_credit_loss_usd_m":None,
        })
    financing.sort(key=lambda z:z["issuer"])
    if as_of>=dt.date(2026,8,26) and [x["issuer"] for x in financing]!=["CoreWeave","Nebius"]:
        raise ValueError("Q2 source-backed financing issuer pair missing")
    sec_q3=as_of>=dt.date(2026,11,26)
    if interest["issuer_IR_Q3_research"] is not None:
        if (interest["issuer_IR_Q3_research"]["AICS_model_eligible"] is not False
            or interest["issuer_IR_Q3_research"]["SEC_date_gate_passed"] is not sec_q3):
            raise ValueError("IR issuer news cannot backdate SEC eligibility")
    return {
        "schema":"aics-v32-v34-auto-research-batch-gated-v1",
        "utc_as_of":as_of.isoformat(),
        "agents_exec_group_count":cycle["agent_groups"]["total_distinct_roles_executed"],
        "live_source_http_attempts":source_scored["http_attempts"],
        "archived_original_publisher_responses":source_scored["successful_http_archives"],
        "v32_matched_loan_pricing_audit":{
            "different_facility_loan_contracts_date_eligible":len(rate_events),
            "single_disclosed_price_per_contract_events":rate_events,
            "same_facility_two_eligible_amendments_verified":0,
            "net_spread_repricing_basis_points":None,
            "actual_coupon_paid":None,
            "borrower_DSCR_breach":None,
            "repo_market_spread_not_same_issuer_credit_spread":True,
            "finding":"NO_PROVEN_SAME_LOAN_REPRICING_IN_PINNED_SOURCES",
        },
        "v33_issuer_funding_and_liquidity_audit":{
            "source_eligible_2026Q2_issuer_bridges":financing,
            "q2_actual_sources_completely_reconciled":len(financing)==2,
            "cross_issuer_same_borrower_cash_flow_causation_proven":False,
            "funding_depletion_or_debt_rollover_default_proven":False,
            "current_bank_funding_contagion_proven":False,
        },
        "v34_evidence_governance":{
            "current_sec_date_gate_coreweave_2026Q3":sec_q3,
            "coreweave_IR_earnings_research_is_model_score_eligible":False,
            "historical_first_delivery_vintage_independently_attested":False,
            "24_month_independent_forward_test_available":False,
            "verified_current_named_lender_dollar_exposure_edges":0,
            "2000_numeric_similarity_pct":None,
            "2008_numeric_similarity_pct":None,
            "crisis_probability":None,
            "certified_11node_aics":None,
            "production_aics_score_promotion":False,
            "fixed_weights_total":1050,
            "production_weights_changed":False,
            "trading_enabled":False,
        },
        "next_experiments_from_current_30_role_evidence":raw_experiments,
        "automatic_next_research_priority":raw_experiments[0]["experiment"],
        "autonomous_cycle_scope":"SCHEDULED_EVIDENCE_COLLECTION_RESEARCH_ANALYSIS_AND_PRIORITIZATION",
        "self_modifying_production_model_enabled":False,
        "production_trading_enabled":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--cycle",type=Path,default=CYCLE)
    args=p.parse_args()
    funding=funding_build(read(FUNDING),read(CASH),read(SEC),as_of=args.as_of)
    interest=interest_build(read(INTEREST),read(REPO),funding,as_of=args.as_of)
    cycle=read(args.cycle)
    data=build(read(TERMS),funding,interest,cycle,as_of=args.as_of)
    data["source_inputs_sha256"]={str(q):hashlib.sha256(q.read_bytes()).hexdigest()
                                  for q in (TERMS,FUNDING,CASH,SEC,INTEREST,REPO,args.cycle)}
    data["github_execution_context"]={
        "workflow_run_id":os.environ.get("GITHUB_RUN_ID"),
        "event_type":os.environ.get("GITHUB_EVENT_NAME"),
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({
        "agents":data["agents_exec_group_count"],
        "research_batch_versions":["V32","V33","V34"],
        "current_priority":data["automatic_next_research_priority"],
        "source_receipts":data["archived_original_publisher_responses"],
        "loan_repricing_pairs_verified":0,
        "production_score":None,
        "trading":False,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
