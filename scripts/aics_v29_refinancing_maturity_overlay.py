"""AICS V29: chronology-safe contractual debt maturity and funding cost terms.

Named administrative agents and arrangers are NOT dollar loan exposures.
A contractual capacity is NOT a funded balance; 90-day margin step-ups are
NOT observed coupons or confirmed defaults. Source availability is SEC filed
+14 days, with June 2026 CoreWeave numeric debt observed only after August 26.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_v28_credit_relationship_topology import from_originals
from scripts.aics_spv_funding_transmission_bridge import (
    build as build_spv, read, CORE, CLOUD, NSCALE, DFS,
)

ROOT=Path("aics_data/research")
TERMS=ROOT/"aics_v29_contractual_refinancing_terms_primary_sec_2026-11-22.json"
OUTPUT=ROOT/"aics_v29_refinancing_maturity_research_2026-11-22.json"

# Exact primary SEC filing IDs, documented contractual terms. Do not change
# these expectations without returning to actual first-filed SEC originals.
EXPECTED={
    "CRWV_DDTL4":{
        "filed_at":"2026-03-31","available_at":"2026-04-14",
        "source_url":"https://www.sec.gov/Archives/edgar/data/1769628/000176962826000129/crwv-20260330.htm",
        "accession":"0001769628-26-000129",
        "borrower":"CoreWeave Compute Acquisition Co. VIII, LLC",
        "capacity_usd_m":8500,"contractual_maturity":"2032-03-31",
        "commitment_termination":"2027-06-30",
        "daily_compounded_sofr_float_margin_bps":225,
        "base_rate_margin_bps":125,"dscr_minimum_x":"1.15",
        "parent_recourse":"limited_bad_acts_carveouts",
        "administrative_agent":"MUFG Bank, Ltd.",
        "co_arrangers":["MUFG Bank, Ltd.","Morgan Stanley Asset Funding, Inc."],
        "collateral_agent":"U.S. Bank Trust Company, National Association",
        "historical_reported_debt_usd_m":2837,
        "historical_reported_debt_source_date":"2026-06-30",
        "historical_reported_debt_eligible_at":"2026-08-26",
    },
    "CRWV_DDTL5":{
        "filed_at":"2026-05-18","available_at":"2026-06-01",
        "source_url":"https://www.sec.gov/Archives/edgar/data/1769628/000176962826000236/crwv-20260515.htm",
        "accession":"0001769628-26-000236",
        "borrower":"CoreWeave Financing DDTL V, LLC",
        "capacity_usd_m":3100,"contractual_maturity":"2031-11-15",
        "commitment_termination":"2026-09-30",
        "daily_compounded_sofr_float_margin_bps":450,
        "base_rate_margin_bps":350,"dscr_minimum_x":"1.35",
        "parent_recourse":"unconditional_parent_guarantee_amount_not_valued",
        "administrative_agent":"Morgan Stanley Senior Funding, Inc.",
        "co_arrangers":["MUFG Bank, Ltd.","Morgan Stanley Senior Funding, Inc."],
        "collateral_agent":"U.S. Bank Trust Company, National Association",
        "historical_reported_debt_usd_m":1101,
        "historical_reported_debt_source_date":"2026-06-30",
        "historical_reported_debt_eligible_at":"2026-08-26",
    },
    "NBIS_CITI_BRIDGE":{
        "filed_at":"2026-10-22","available_at":"2026-11-05",
        "source_url":"https://www.sec.gov/Archives/edgar/data/1513845/000110465926117978/tm2628078d1_6k.htm",
        "accession":"0001104659-26-117978",
        "borrower":"Nebius Group N.V.; Nebius Inc.; Nebius B.V. (three co-borrowers, one facility)",
        "capacity_usd_m":3500,"contractual_maturity":"2027-10-16",
        "commitment_termination":None,
        "daily_compounded_sofr_float_margin_bps":None,
        "term_sofr_initial_margin_bps":275,
        "margin_step_up_bps_per_90_days":25,
        "margin_cap_bps":350,
        "margin_step_up_start_anchor":"2026-10-17",
        "mandated_lead_arranger_and_lender":"Citibank, N.A.",
        "parent_recourse":None,
        "historical_reported_debt_usd_m":None,
        "historical_reported_debt_source_date":None,
        "historical_reported_debt_eligible_at":None,
        "actual_total_drawn_usd_m":None,
    }
}


def _day(x):
    return dt.date.fromisoformat(x)


def _checked(terms):
    if (terms.get("schema")!="aics-v29-three-original-sec-contractual-refinancing-terms-v1"
        or terms.get("fixed_aics_weights_total")!=1050
        or sum(WEIGHTS.values())!=1050
        or terms.get("sec_timing_rule")!="filed_at+14 calendar days"
        or terms.get("historical_first_delivery_provider_pit_certified") is not False
        or terms.get("source_raw_bytes_independently_rehashed_for_this_8k_6k_ledger") is not False
        or terms.get("contractual_refinancing_exposure_not_additive_to_outstanding_debt") is not True
        or terms.get("lender_arranger_agent_roles_are_not_funded_dollar_exposure") is not True
        or terms.get("known_current_lender_dollar_exposures")!=0
        or terms.get("unverified_current_draws_are_null") is not True
        or terms.get("unmodified_11node_aics") is not None
        or terms.get("crisis_probability") is not None
        or terms.get("production_weights_changed") is not False
        or terms.get("trades_created") is not False):
        raise ValueError("Unsafe or unverified contract source ledger")
    contracts=terms.get("contracts",[])
    if (len(contracts)!=3 or [x.get("facility_id") for x in contracts]
        !=list(EXPECTED)):
        raise ValueError("Three source-dated facilities required")
    for r in contracts:
        x=EXPECTED[r["facility_id"]]
        if any(r.get(k)!=v for k,v in x.items()):
            raise ValueError("SEC filing id, role, maturity, covenant or pricing drift")
        if (r.get("facility_capacity_not_outstanding") is not True
            or r.get("lender_by_lender_amount_usd_m") is not None
            or r.get("full_lender_roster_verified") is not False
            or r.get("parent_enforceable_guarantee_amount_usd_m") is not None
            or _day(r["available_at"])!=_day(r["filed_at"])+dt.timedelta(days=14)):
            raise ValueError("Facility roles or SEC+14 availability misstated")
        if r["facility_id"]!="NBIS_CITI_BRIDGE" and (
            r.get("interest_rate_swap_hedge_required_pct_of_expected_floating_notional")!=95
            or r.get("mandated_lead_arranger_and_lender") is not None
            or r.get("capacity_usd_m",0)<=0):
            raise ValueError("CoreWeave facility hedging and agent semantics invalid")
        if r["facility_id"]=="NBIS_CITI_BRIDGE" and (
            r.get("contractual_margin_adjustments_possible") is not True
            or r.get("collateral_summary") is None
            or r.get("covenant") is None
            or r.get("co_arrangers")!=[]
            or r.get("administrative_agent") is not None):
            raise ValueError("Citi loan role or floating-pricing exception not captured")
    return contracts


def build(terms, spv, topology, *, as_of):
    if isinstance(as_of,str):as_of=_day(as_of)
    if not isinstance(as_of,dt.date) or isinstance(as_of,dt.datetime):
        raise ValueError("Calendar as-of required")
    contracts=_checked(terms)
    if (
        spv.get("schema")!="aics-v27-spv-and-buildout-pit-gated-recourse-bridge-v1"
        or spv.get("as_of")!=as_of.isoformat()
        or spv.get("historical_crisis_2008_similarity_pct") is not None
        or spv.get("full_11node_aics") is not None
        or spv.get("trades_created") is not False
        or topology.get("schema")!="aics-v28-source-gated-credit-relationship-topology-research-v1"
        or topology.get("as_of")!=as_of.isoformat()
        or topology.get("current_named_lender_to_borrower_dollar_exposure_edges")!=0
        or topology.get("current_lender_borrower_dollar_exposure_matrix") is not None
        or topology.get("index_aics") is not None
        or topology.get("trades_created") is not False):
        raise ValueError("Input credit evidence falsely promotes a current or crisis exposure")

    live=[]
    for r in contracts:
        if _day(r["available_at"])>as_of:
            continue
        if _day(r["contractual_maturity"])<_day(r["filed_at"]):
            raise ValueError("Contract maturity before SEC filing")
        known_balance=None
        if r["historical_reported_debt_eligible_at"] is not None and (
                _day(r["historical_reported_debt_eligible_at"])<=as_of):
            if spv.get("coreweave") is None:
                raise ValueError("Earlier numeric debt must have SEC 10-Q trace")
            facility=(spv["coreweave"]["facilities"][0]
                      if r["facility_id"]=="CRWV_DDTL4"
                      else spv["coreweave"]["facilities"][1])
            if (facility["borrower"]!=r["borrower"]
                or facility["reported_debt_usd_m"]!=r["historical_reported_debt_usd_m"]
                or spv["coreweave"]["source_available_at"]!=r["historical_reported_debt_eligible_at"]):
                raise ValueError("June 2026 reported debt mismatches separate original 10-Q")
            known_balance=r["historical_reported_debt_usd_m"]
        days=(_day(r["contractual_maturity"])-as_of).days
        commit_days=(None if r["commitment_termination"] is None else
                     (_day(r["commitment_termination"])-as_of).days)
        live.append({
            "facility_id":r["facility_id"],"legal_borrower":r["borrower"],
            "sec_filed_at":r["filed_at"],"sec_available_at":r["available_at"],
            "original_primary_source_url":r["source_url"],
            "contractual_capacity_usd_m_not_debt":r["capacity_usd_m"],
            "maturity":r["contractual_maturity"],
            "calendar_days_to_contract_maturity":days,
            "contract_matures_within_365d":0<=days<=365,
            "commitment_termination":r["commitment_termination"],
            "calendar_days_to_commitment_termination":commit_days,
            "commitment_period_ended_by_asof":commit_days is not None and commit_days<0,
            "most_recent_verified_numeric_debt_usd_m_at_2026_06_30_not_current":known_balance,
            "verified_numeric_debt_availability":r["historical_reported_debt_eligible_at"] if known_balance is not None else None,
            "current_outstanding_usd_m":None,
            "named_administrative_agent":r.get("administrative_agent"),
            "named_mandated_arranger_and_lender":r.get("mandated_lead_arranger_and_lender"),
            "named_co_arrangers":r.get("co_arrangers",[]),
            "named_collateral_agent":r.get("collateral_agent"),
            "named_lender_funded_amount_usd_m":None,
            "floating_rate_formula":(
                "daily_compounded_SOFR_plus_margin_bps"
                if r["facility_id"]!="NBIS_CITI_BRIDGE"
                else "Term_SOFR_plus_initial_and_stepup_margin"),
            "initial_or_contractual_floating_spread_bps":(
                r.get("daily_compounded_sofr_float_margin_bps")
                if r["facility_id"]!="NBIS_CITI_BRIDGE"
                else r["term_sofr_initial_margin_bps"]),
            "contractual_term_sofr_stepup_bps_every_90d":r.get("margin_step_up_bps_per_90_days"),
            "contractual_max_margin_bps_subject_to_adjustments":r.get("margin_cap_bps"),
            "dscr_contractual_minimum_x_not_actual":r.get("dscr_minimum_x"),
            "parent_recourse_type":r.get("parent_recourse"),
            "contractual_coupon_paid_or_funding_cost":None,
            "dscr_actual_achieved_x":None,
            "covenant_violation_proven":False,
            "actual_refinancing_requirement_today_usd_m":None,
            "contractual_maturity_does_not_equal_total_capacity_due":True,
        })
    identifiers=[r["facility_id"] for r in live]
    if len(identifiers)!=len(set(identifiers)):
        raise ValueError("Duplicate debt facility")
    citi=[r for r in live if r["facility_id"]=="NBIS_CITI_BRIDGE"]
    if citi and not any(x["id"]=="NEBIUS_6K_CAPACITY" for x in topology["relationships"]):
        raise ValueError("Citi role has no source-gated Nebius borrower topology")
    return {
        "schema":"aics-v29-three-contracts-maturity-funding-terms-research-v1",
        "as_of":as_of.isoformat(),
        "eligible_contract_count":len(live),
        "contractual_term_records":live,
        "loan_maturities_within_365_calendar_days":sum(x["contract_matures_within_365d"] for x in live),
        "first_known_contractual_maturity":min((x["maturity"] for x in live),default=None),
        "first_known_contractual_maturity_is_outstanding_principal_due":False,
        "coreweave_admin_agents_named":sum(x["named_administrative_agent"] is not None for x in live),
        "nebius_citi_mandated_arranger_and_lender_named":bool(citi),
        "named_arranger_agent_or_lender_relationships_are_not_credit_exposure_dollars":True,
        "individual_lender_allocations_verified":0,
        "current_named_lender_borrower_dollar_exposure_edges":0,
        "current_credit_loss_matrix":None,
        "actual_coupon_including_base_rate":None,
        "actual_credit_refinancing_need_usd_m":None,
        "actual_dscr_breach_count":None,
        "2027_bridge_maturity_capacity_is_not_drawn_borrowing":True,
        "independent_historical_first_delivery_pit_certified":False,
        "independent_fixed_24m_oos":False,
        "2000_similarity_percent":None,"2008_similarity_percent":None,
        "crisis_probability":None,"full_aics":None,
        "production_model_changed":False,"trades_created":False,
        "weights_total_unchanged":1050,
        "missing_information":[
            "CoreWeave DDTL 4.0/5.0 precise participant-level funded outstanding balances",
            "Nebius actual draw, current loan principal and Citi vs other lender allocation",
            "Actual Term SOFR and daily compounded SOFR observations per payment period",
            "Covenant tested DSCR and relevant cash reserve amortization schedules",
            "Loan maturity buckets for Nscale Ward/NC and 2008-style lender collateral repo spillovers",
        ],
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=OUTPUT)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    args=p.parse_args()
    core=build_spv(*(read(p) for p in (CORE,CLOUD,NSCALE,DFS)),as_of=args.as_of)
    topology=from_originals(core,as_of=args.as_of)
    rep=build(read(TERMS),core,topology,as_of=args.as_of)
    rep["original_source_ledger_sha256"]=hashlib.sha256(TERMS.read_bytes()).hexdigest()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"eligible_contracts":rep["eligible_contract_count"],
                      "contractual_maturities_within_365d":rep["loan_maturities_within_365_calendar_days"],
                      "earliest_maturity":rep["first_known_contractual_maturity"],
                      "named_current_lender_dollar_exposure_edges":0,
                      "production_aics":None,"trades":False}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
