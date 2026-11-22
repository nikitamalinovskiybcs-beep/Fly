"""AICS V35–V39: one unattended evidence-to-risk research batch.

V35 first observable four-hyperscaler cash-flow deterioration (SEC+14).
V36 2026 Q2→Q3 issuer attribution, not inferred bank borrowing.
V37 distinct CoreWeave debt vs Nebius equity funding cash identities.
V38 repo/IR/maturity signals with distinct publication and legal clocks.
V39 2000/2008 historical-onset and independent-certification stop gates.

Inputs: existing original-source audited AICS V26–V34 reports and the
genuine 30-role collector/analysis coordinator. No synthetic observation,
backfill, future outcome as a feature, changed model, weight or trade.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS

RUN=Path("aics_data/agent_runs/ten_real_collection_rounds")
ANALOG=RUN/"aics_2000_2008_2026_analog_research.json"
CASH=Path("aics_data/research/aics_precrisis_imbalance_4hyperscalers_2025_2026_research_2026-11-22.json")
FUND=RUN/"aics_v30_cashflow_financing_bridge.json"
INTEREST=RUN/"aics_v31_interest_repo_dual_clock_research.json"
MATURITY=RUN/"aics_v29_refinancing_maturity_research.json"
CYCLE=RUN/"aics_thirty_agent_research_cycle.json"
ROTATION=RUN/"aics_autonomous_v32_v34_research_rotation.json"
OUT=RUN/"aics_v35_v39_five_version_result.json"

ROSTER={"Microsoft","Amazon","Alphabet","Meta"}


def d(x):
    if isinstance(x,bool):raise ValueError("Financial bool instead of number")
    y=Decimal(str(x))
    if not y.is_finite():raise ValueError("Non-finite source value")
    return y


def fmt(x,places="0.01"):
    return str(x.quantize(Decimal(places),rounding=ROUND_HALF_UP))


def validate_date(value):
    if isinstance(value,dt.date) and not isinstance(value,dt.datetime):return value
    if isinstance(value,str):return dt.date.fromisoformat(value)
    raise ValueError("Invalid date cutoff")


def v35_cash_signal(cash,as_of):
    if (cash.get("schema")!="aics-precrisis-four-hyperscaler-source-gated-cash-imbalance-research-v1"
        or cash.get("as_of")!=as_of.isoformat()
        or cash.get("economic_issuer_count")!=4
        or cash.get("fixed_original_aics_node_weights_total")!=1050
        or cash.get("primary_source_document_bytes_independently_historical_pit_attested") is not False
        or cash.get("similarity_to_2000_pct") is not None
        or cash.get("similarity_to_2008_pct") is not None
        or cash.get("full_11_node_aics") is not None
        or cash.get("production_weight_change") is not False
        or cash.get("trading") is not False):
        raise ValueError("Four issuer SEC cash ledger falsely certified")
    rows=cash.get("quarterly_original_issuer_records",[])
    if len({(r["period"],r["issuer"]) for r in rows})!=len(rows):
        raise ValueError("Duplicated issuer-quarter cash record")
    by_period={}
    for row in rows:
        if row["issuer"] not in ROSTER:
            raise ValueError("Unknown hyperscaler issuer")
        if row["first_complete_source_eligible_at_sec_plus14"]>as_of.isoformat():
            raise ValueError("Future SEC record before filed+14")
        if d(row["ocf_usd_m"])-d(row["gross_cash_ppe_usd_m"])!=d(row["cash_gap_usd_m"]):
            raise ValueError("SEC cash gap arithmetic differs")
        if d(row["gross_cash_ppe_usd_m"])<0:
            raise ValueError("Cash purchases must be positive magnitude")
        by_period.setdefault(row["period"],[]).append(row)
    timeline=[]
    for quarter in cash.get("complete_or_partial_quarters",[]):
        period=quarter["period"];members=by_period.get(period,[])
        if len(members)!=quarter["issuer_count"]:
            raise ValueError("Quarter member count inconsistent")
        if quarter["source_eligible_at"]!=max(x["first_complete_source_eligible_at_sec_plus14"] for x in members):
            raise ValueError("Original issuer publication date missing")
        if quarter["four_issuer_complete"] is not (len(members)==4):
            raise ValueError("Partial cash quarter marked complete")
        if len(members)!=4:continue
        if {x["issuer"] for x in members}!=ROSTER:
            raise ValueError("Cohort changed between quarters")
        cash_gap=sum((d(x["cash_gap_usd_m"]) for x in members),Decimal(0))
        if cash_gap!=d(quarter["four_issuer_cash_gap_usd_m"]):
            raise ValueError("Four company SEC total mismatch")
        ocf=sum((d(x["ocf_usd_m"]) for x in members),Decimal(0))
        ppe=sum((d(x["gross_cash_ppe_usd_m"]) for x in members),Decimal(0))
        if ocf!=d(quarter["four_issuer_ocf_usd_m"]) or ppe!=d(quarter["four_issuer_cash_ppe_usd_m"]):
            raise ValueError("Four company OCF and CapEx totals mismatch")
        if sorted(x["issuer"] for x in members if d(x["cash_gap_usd_m"])<0)!=quarter["observed_negative_cash_gap_issuers"]:
            raise ValueError("Per-issuer cash gap status inconsistent")
        timeline.append({
            "quarter":period,"first_complete_eligible_at":quarter["source_eligible_at"],
            "ocf_usd_m":str(ocf),"gross_cash_ppe_usd_m":str(ppe),
            "ocf_minus_cash_ppe_usd_m":str(cash_gap),
            "negative_issuer_count":len(quarter["observed_negative_cash_gap_issuers"]),
            "issuer_count":4,
        })
    if len(timeline)>7:raise ValueError("Unexpected extra cash observation")
    first_negative=next((x for x in timeline if d(x["ocf_minus_cash_ppe_usd_m"])<0),None)
    return {
        "name":"V35_FIRST_OBSERVABLE_INVESTMENT_OVERHANG",
        "observed_complete_calendar_quarters":len(timeline),
        "calendar_quarter_points":timeline,
        "first_four_issuer_negative_gap_quarter":first_negative["quarter"] if first_negative else None,
        "first_eligible_source_date":first_negative["first_complete_eligible_at"] if first_negative else None,
        "first_negative_gap_does_not_prove_bank_refinancing_distress":True,
        "monthly_11node_index_published":False,
    }


def v36_issuer_attribution(cash,v35,as_of):
    rows={(x["period"],x["issuer"]):x for x in cash["quarterly_original_issuer_records"]}
    periods={x["quarter"]:x for x in v35["calendar_quarter_points"]}
    if "2026-Q2" not in periods or "2026-Q3" not in periods:
        return {"name":"V36_ISSUER_Q2_TO_Q3_ATTRIBUTION",
                "missing_fully_eligible_comparison":True,"issuer_attribution":[],
                "total_observed_deterioration_usd_m":None,"largest_contributing_issuer":None}
    deltas=[]
    for name in sorted(ROSTER):
        a,b=rows[("2026-Q2",name)],rows[("2026-Q3",name)]
        delta=d(b["cash_gap_usd_m"])-d(a["cash_gap_usd_m"])
        deltas.append({
            "issuer":name,"Q2_gap_usd_m":a["cash_gap_usd_m"],
            "Q3_gap_usd_m":b["cash_gap_usd_m"],
            "gap_change_usd_m":str(delta),
            "Q3_source_eligible_at":b["first_complete_source_eligible_at_sec_plus14"],
            "component_of_cash_gap_not_issuer_specific_debt_draw":True,
        })
    total=sum((d(x["gap_change_usd_m"]) for x in deltas),Decimal(0))
    expected=(d(periods["2026-Q3"]["ocf_minus_cash_ppe_usd_m"])
              -d(periods["2026-Q2"]["ocf_minus_cash_ppe_usd_m"]))
    if total!=expected:
        raise ValueError("Q2/Q3 issuer attribution does not sum to aggregate deterioration")
    largest=min(deltas,key=lambda x:d(x["gap_change_usd_m"]))
    share=fmt(d(largest["gap_change_usd_m"])/total*100) if total<0 else None
    return {
        "name":"V36_ISSUER_Q2_TO_Q3_ATTRIBUTION",
        "missing_fully_eligible_comparison":False,
        "issuer_attribution":deltas,
        "total_observed_deterioration_usd_m":str(total),
        "largest_contributing_issuer":largest["issuer"],
        "largest_contributor_share_of_net_deterioration_pct":share,
        "contributions_can_be_negative_or_positive_not_a_loss_exposure_allocation":True,
    }


def v37_funding(financing,as_of):
    if (financing.get("schema")!="aics-v30-issuer-cashflow-financing-identity-source-gated-research-v1"
        or financing.get("as_of")!=as_of.isoformat()
        or financing.get("source_first_pit_provider_delivery_attested") is not False
        or financing.get("cashflow_financing_identity_not_causal_allocation") is not True
        or financing.get("full_aics") is not None
        or financing.get("crisis_probability") is not None
        or financing.get("trades_created") is not False):
        raise ValueError("Financing data not original or wrongly promoted")
    q2={x["issuer"]:x for x in financing.get("issuer_quarter_observations",[])
        if x["period"]=="2026-Q2"}
    if q2 and set(q2)!={"CoreWeave","Nebius"}:
        raise ValueError("Q2 missing an independently original issuer")
    rows=[]
    for name in ("CoreWeave","Nebius"):
        if name not in q2:continue
        x=q2[name]
        if x["source_eligible_at"]>as_of.isoformat():raise ValueError("Future funding observation")
        comp=x["q2_financing_components_usd_m"]
        if name=="CoreWeave":
            debt=d(comp["debt_issuance_net_of_costs"])+d(comp["debt_repayments"])
            equity=d(comp["private_placement_net_of_costs"])
            if debt!=Decimal(9573) or d(x["net_financing_cash_usd_m"])!=Decimal(10071):
                raise ValueError("CoreWeave actual debt and financing mismatched")
        else:
            debt=None
            equity=d(comp["treasury_share_sale"])+d(comp["treasury_share_issuance_costs"])
            if equity!=Decimal("2811.1") or d(x["net_financing_cash_usd_m"])!=Decimal("2864.9"):
                raise ValueError("Nebius actual equity financing mismatched")
        rows.append({
            "issuer":name,"source_available_at":x["source_eligible_at"],
            "q2_capital_purchase_gap_usd_m":x["ocf_less_purchases_usd_m"],
            "companywide_net_financing_usd_m":x["net_financing_cash_usd_m"],
            "observed_debt_issuance_net_of_costs_less_repayments_usd_m":
                str(debt) if debt is not None else None,
            "reported_equity_net_cash_receipts_usd_m":str(equity),
            "actual_restricted_plus_unrestricted_cash_change_usd_m":
                x["net_change_cash_including_restricted_usd_m"],
            "cashflow_funding_mix_not_evidence_of_lender_loss":True,
        })
    if as_of>=dt.date(2026,8,26) and len(rows)!=2:raise ValueError("Original Q2 financing pair missing")
    return {
        "name":"V37_DEBT_VS_EQUITY_FUNDING_MECHANISMS",
        "source_eligible_q2_issuers":len(rows),"same_quarter_issuer_financing_evidence":rows,
        "current_lender_funded_dollar_exposure_matrix":None,
        "real_time_financing_denial_detected":False,
    }


def v38_credit_crosscheck(maturity,interest,as_of):
    if (maturity.get("schema")!="aics-v29-three-contracts-maturity-funding-terms-research-v1"
        or maturity.get("as_of")!=as_of.isoformat()
        or maturity.get("full_aics") is not None
        or maturity.get("current_credit_loss_matrix") is not None
        or maturity.get("trades_created") is not False
        or interest.get("schema")!="aics-v31-dual-clock-interest-repo-matched-loan-research-v1"
        or interest.get("as_of")!=as_of.isoformat()
        or interest.get("matched_same_loan_spread_repricing_events_verified")!=0
        or interest.get("matched_same_loan_repricing_bps") is not None
        or interest.get("full_11node_aics") is not None):
        raise ValueError("Invalid current credit/repo or embargo data")
    legal=maturity.get("contractual_term_records",[])
    for r in legal:
        if r["sec_available_at"]>as_of.isoformat():
            raise ValueError("Future contract used before filing+14")
        if r["current_outstanding_usd_m"] is not None:
            raise ValueError("Unconfirmed funded loan converted from maximum commitment")
    ir=interest["issuer_IR_Q3_research"]
    if ir and ir["AICS_model_eligible"] is not False:
        raise ValueError("IR release falsely promoted")
    secok=as_of>=dt.date(2026,11,26)
    if interest["Q3_SEC_10Q_date_gate_passed_as_of"] is not secok:
        raise ValueError("CoreWeave 10-Q SEC+14 gate contradicts date")
    return {
        "name":"V38_REFINANCING_VERSUS_WHOLESALE_RATE",
        "eligible_contractual_facility_count":len(legal),
        "near_term_365d_contractual_maturity_count":maturity["loan_maturities_within_365_calendar_days"],
        "earliest_known_contract_maturity":maturity["first_known_contractual_maturity"],
        "coreweave_Q3_IR_net_interest_over_revenue_pct_research_only":
            ir["net_interest_expense_divided_by_revenue_pct"] if ir else None,
        "coreweave_Q3_SEC_10Q_calendar_gate_passed":secok,
        "coreweave_Q3_historical_first_provider_receipt_verified":False,
        "latest_retrospective_repo_sofr_minus_iorb_bps":interest["repo_latest_month_sofr_minus_iorb_bps"],
        "repo_spread_is_not_a_matched_issuer_loan_spread":True,
        "matched_instrument_new_spread_change_bps":None,
        "actual_refinancing_need_usd_m":None,
        "certified_2008_wholesale_contagion":False,
    }


def v39_governance(cycle,rotation,analog,as_of):
    if (cycle.get("schema")!="aics-30-agent-evidence-to-improvement-loop-v1"
        or cycle.get("cutoff_date")!=as_of.isoformat()
        or cycle.get("agent_groups",{}).get("total_distinct_roles_executed")!=30
        or cycle.get("cycle_decision")!="RESEARCH_ONLY_NOT_AUTONOMOUS_PRODUCTION"
        or cycle.get("complete_11_node_aics") is not None
        or cycle.get("eligible_for_production_promotion") is not False
        or cycle.get("weights_changed") is not False
        or cycle.get("trades_created") is not False
        or rotation.get("schema")!="aics-v32-v34-auto-research-batch-gated-v1"
        or rotation.get("utc_as_of")!=as_of.isoformat()
        or rotation.get("agents_exec_group_count")!=30
        or rotation.get("production_trading_enabled") is not False
        or rotation.get("self_modifying_production_model_enabled") is not False
        or rotation["v34_evidence_governance"]["certified_11node_aics"] is not None
        or rotation["v34_evidence_governance"]["verified_current_named_lender_dollar_exposure_edges"]!=0
        or analog.get("feature_axis_count")!=8
        or analog.get("quantitative_similarity_percent_2000") is not None
        or analog.get("quantitative_similarity_percent_2008") is not None):
        raise ValueError("Certified index or historical crisis skill was falsely promoted")
    for episode in ("telecom2000","subprime2008"):
        t=analog["comparison_eras"][episode]["timing_audit"]
        if t["early_warning_of_crisis_onset_status"]!="OLD_CROSSING_AFTER_OBSERVED_CRISIS_ONSET":
            raise ValueError("Old alleged early warning was not before actual crisis onset")
    if cycle["source_collection"]["successful_http_archives"]>cycle["source_collection"]["http_attempts"]:
        raise ValueError("Publisher archives exceed actual attempts")
    tasks=cycle.get("next_experiments",[])
    if (not tasks or
        [x.get("priority") for x in tasks]!=list(range(1,len(tasks)+1))
        or rotation["automatic_next_research_priority"]!=tasks[0]["experiment"]):
        raise ValueError("Automatic research priorities disagree with evidence queue")
    return {
        "name":"V39_HISTORICAL_COMPARABILITY_AND_RELEASE_GOVERNANCE",
        "actual_agent_roles_executed":30,
        "source_http_attempts":cycle["source_collection"]["http_attempts"],
        "publisher_response_archives":cycle["source_collection"]["successful_http_archives"],
        "2000_historical_first_crisis_warning_reproduced":False,
        "2008_historical_first_crisis_warning_reproduced":False,
        "2000_and_2008_numeric_similarity_pct":None,
        "untouched_24month_oos_confirmed":False,
        "same_lender_current_dollar_exposure_matrix":None,
        "approved_full_AICS":None,
        "evidence_ranked_open_experiments":[x["experiment"] for x in tasks],
        "automatic_next_experiment":tasks[0]["experiment"],
        "production_weights_total":1050,
        "model_auto_promotion_enabled":False,
        "trading_enabled":False,
    }


def build(cash,finance,interest,maturity,cycle,rotation,analog,*,as_of):
    as_of=validate_date(as_of)
    if sum(WEIGHTS.values())!=1050:
        raise ValueError("Frozen 11-node weights no longer sum 1050")
    a=v35_cash_signal(cash,as_of)
    b=v36_issuer_attribution(cash,a,as_of)
    c=v37_funding(finance,as_of)
    e=v38_credit_crosscheck(maturity,interest,as_of)
    f=v39_governance(cycle,rotation,analog,as_of)
    return {
        "schema":"aics-v35-v39-source-validated-five-version-batch-v1",
        "as_of":as_of.isoformat(),
        "versions":[a,b,c,e,f],
        "version_count":5,
        "source_research_only":True,
        "synthetic_rows_added":0,
        "historical_2000_2008_prediction_skill":None,
        "PIT_attested_full_11_node_index":None,
        "production_weights_changed":False,
        "trades_created":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    paths=[CASH,FUND,INTEREST,MATURITY,CYCLE,ROTATION,ANALOG]
    vals=[json.loads(x.read_text(encoding="utf-8")) for x in paths]
    result=build(*vals,as_of=a.as_of)
    result["input_file_sha256"]={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "versions":[x["name"].split("_")[0] for x in result["versions"]],
        "seven_quarter_original_cashflow_count":result["versions"][0]["observed_complete_calendar_quarters"],
        "q2q3_gap_change_usd_m":result["versions"][1]["total_observed_deterioration_usd_m"],
        "q2_source_backed_funding_issuers":result["versions"][2]["source_eligible_q2_issuers"],
        "same_instrument_spread_repricing":None,
        "approved_index":None,"trades":False,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
