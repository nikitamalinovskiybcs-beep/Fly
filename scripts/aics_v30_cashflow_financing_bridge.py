"""AICS V30: original SEC+14 quarterly cash and financing bridge.

Shows 2026 Q1-to-Q2 cash PP&E financing dependence of CoreWeave and
Nebius from independently source-linked SEC research ledgers. Q2 net
financing flows are NOT allocated to DDTL 4/5, Citi, lenders or investor
losses. No claims of 2008 contagion or market timing skill.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_v29_refinancing_maturity_overlay import read as read_maturity, TERMS
from scripts.aics_v28_credit_relationship_topology import from_originals
from scripts.aics_spv_funding_transmission_bridge import (
    build as build_spv, read, CORE, CLOUD, NSCALE, DFS
)

ROOT=Path("aics_data/research")
FUNDING=ROOT/"neocloud_q2_funding_2026.json"
CASH=ROOT/"neocloud_cash_coverage_2026_h1.json"
SEC=Path("aics_data/source_registry/neocloud_cash_h1_sec.json")
OUT=ROOT/"aics_v30_cashflow_financing_bridge_2026-11-22.json"
EXPECTED={
    "CoreWeave":{
        "q1":{"operating_cash_flow":"2984","cash_purchases":"7695","operating_cash_less_purchases":"-4711",
              "source":"crwv_26_q1","available":"2026-05-22"},
        "q2":{"operating_cash_flow":"679","cash_purchases":"6422","operating_cash_less_purchases":"-5743",
              "available":"2026-08-26"},
        "net_investing_cash":"-7166","net_financing_cash":"10071",
        "components":{
            "debt_issuance_net_of_costs":"13457","debt_repayments":"-3884",
            "private_placement_net_of_costs":"997","capped_calls":"-492",
            "other_financing":"-7",
        },
        "cash_with_restricted_start":"3320","cash_with_restricted_end":"6904",
        "cash_with_restricted_change":"3584",
        "cash_no_restricted_start":"2244","cash_no_restricted_end":"5524",
        "restricted_start":"1076","restricted_end":"1380",
        "scope":"cash_ppe_purchases_and_capitalized_internal_use_software",
        "financing_type":"large_debt_issuance_and_repayment_plus_equity_and_hedge_costs",
    },
    "Nebius":{
        "q1":{"operating_cash_flow":"2258.0","cash_purchases":"2472.9","operating_cash_less_purchases":"-214.9",
              "source":"nbis_26_q1","available":"2026-05-27"},
        "q2":{"operating_cash_flow":"2246.1","cash_purchases":"5657.4","operating_cash_less_purchases":"-3411.3",
              "available":"2026-08-26"},
        "net_investing_cash":"-5645.7","net_financing_cash":"2864.9",
        "components":{
            "convertible_notes_issued":"0","convertible_notes_issuance_costs":"0",
            "treasury_share_sale":"2846.7","treasury_share_issuance_costs":"-35.6",
            "prefunded_warrant_issuance":"0","option_exercises":"53.8","withholding_tax":"0",
        },
        "cash_with_restricted_start":"9626.9","cash_with_restricted_end":"9098.1",
        "cash_with_restricted_change":"-528.8",
        "cash_no_restricted_start":"9298.2","cash_no_restricted_end":"8042.1",
        "restricted_start":"328.7","restricted_end":"1056.0",
        "scope":"ppe_and_intangibles_cash_purchases_continuing_operations",
        "financing_type":"mostly_treasury_equity_sales_not_bank_debt",
    },
}
QUARTER_SOURCE_IDS={
    "CoreWeave":["crwv_26_q1","crwv_26_release","crwv_26_h1"],
    "Nebius":["nbis_26_q1","nbis_26_release","nbis_26_h1"],
}
SOURCE_IDS=sorted({k for v in QUARTER_SOURCE_IDS.values() for k in v})
H1_END="2026-06-30"


def money(value):
    if isinstance(value,bool):
        raise ValueError("Boolean as finance input")
    v=Decimal(str(value))
    if not v.is_finite():
        raise ValueError("Infinite/NaN financial value")
    return v


def json_dec(v):
    """Canonical non-synthetic sourced decimal without trailing zero noise."""
    return format(v.normalize(),"f")


def first_eligible(registry, ids):
    dates=[]
    for key in ids:
        if key not in registry:
            raise ValueError("Unknown original SEC accession")
        r=registry[key]
        filed=dt.date.fromisoformat(r["filed_at"])
        avail=dt.date.fromisoformat(r["available_at"])
        if avail!=filed+dt.timedelta(days=14):
            raise ValueError("SEC source availability must be filing +14 calendar days")
        if (not str(r["source_page"]).startswith("https://www.sec.gov/Archives/edgar/data/")
                or not str(r["original"]["url"]).startswith("https://www.sec.gov/Archives/edgar/data/")
                or len(r["original"]["sha256"])!=64
                or len(r["document_text_sha256"])!=64
                or int(r["original"]["bytes"])<1):
            raise ValueError("Unverified original source lineage")
        dates.append(avail)
    return max(dates)


def build(finance,cash,registry,*,as_of):
    if isinstance(as_of,str):
        as_of=dt.date.fromisoformat(as_of)
    if (not isinstance(as_of,dt.date) or isinstance(as_of,dt.datetime)
            or sum(WEIGHTS.values())!=1050):
        raise ValueError("Invalid cutoff or AICS weights")
    if (finance.get("as_of")!="2026-11-18"
        or finance.get("units")!="USD million unless specified"
        or cash.get("source_cutoff")!="2026-11-18"
        or cash.get("units")!="USD million, except percentages"
        or finance.get("source_registry")!=str(SEC)
        or cash.get("registry")!=str(SEC)
        or finance.get("node_score") is not None
        or finance.get("index_aics") is not None
        or cash.get("node_score") is not None
        or cash.get("index_aics") is not None
        or finance.get("trades_created") is not False
        or cash.get("trades_created") is not False
        or set(registry)<set(SOURCE_IDS)):
        raise ValueError("Source ledger cannot be promoted or merged with unrelated units")
    obs=cash.get("observations")
    bridges=finance.get("cash_bridges")
    if (not isinstance(obs,list) or len(obs)!=8
        or not isinstance(bridges,list) or len(bridges)!=2
        or set(r.get("issuer") for r in bridges)!=set(EXPECTED)
        or len({r["issuer"] for r in bridges})!=2):
        raise ValueError("Expected original two issuer quarterly bridges")
    by={(x["issuer"],x["period"]):x for x in obs}
    if (len(by)!=len(obs)
        or set(x["issuer"] for x in obs)!=set(EXPECTED)
        or any(x["period"] not in ("2025-H1","2026-Q1","2026-Q2","2026-H1") for x in obs)):
        raise ValueError("Original cash statement rows missing or duplicated")
    visible=[]
    for b in bridges:
        issuer=b["issuer"]
        expected=EXPECTED[issuer]
        if (b["period"]!="2026-Q2"
            or b["sources"]!=QUARTER_SOURCE_IDS[issuer]
            or b["available_with_all_checks"]!="2026-08-26"
            or b.get("separately_reported_exchange_effect") != ("5.9" if issuer=="Nebius" else None)
            or str(b["net_investing_cash"])!=expected["net_investing_cash"]
            or str(b["net_financing_cash"])!=expected["net_financing_cash"]):
            raise ValueError("Original full Q2 identity/availability changed")
        for key,value in expected["components"].items():
            if b["financing_components_signed"].get(key)!=value:
                raise ValueError("Debt and equity components do not match original filing")
        if set(b["financing_components_signed"])!=set(expected["components"]):
            raise ValueError("Unverified extra financing components")
        if sum((money(x) for x in b["financing_components_signed"].values()),
                Decimal(0))!=money(b["net_financing_cash"]):
            raise ValueError("Financing statement does not reconcile")
        for kind,first,last in (
            ("cash_including_restricted","cash_with_restricted_start","cash_with_restricted_end"),
            ("cash_and_equivalents_excluding_restricted","cash_no_restricted_start","cash_no_restricted_end"),
            ("restricted_cash_and_equivalents","restricted_start","restricted_end"),
        ):
            if (money(b[kind]["start"])!=money(expected[first])
                or money(b[kind]["end"])!=money(expected[last])
                or money(b[kind]["change"])!=money(b[kind]["end"])-money(b[kind]["start"])):
                raise ValueError("Actual reported cash stock mismatch")
        q1,q2=by[(issuer,"2026-Q1")],by[(issuer,"2026-Q2")]
        if (q1["source"]!=expected["q1"]["source"]
            or q1["cross_checks"]!=[]
            or q2["source"]!=QUARTER_SOURCE_IDS[issuer][1]
            or q2["cross_checks"]!=[QUARTER_SOURCE_IDS[issuer][0],QUARTER_SOURCE_IDS[issuer][2]]
            or q2["available_from_cited_source"]!=registry[q2["source"]]["available_at"]
            or q2["all_cited_checks_available"]!="2026-08-26"):
            raise ValueError("Original cash source crosschecks or +14 chain altered")
        for q,period in ((q1,"q1"),(q2,"q2")):
            for field in ("operating_cash_flow","cash_purchases","operating_cash_less_purchases"):
                if str(q[field])!=expected[period][field]:
                    raise ValueError("Original issuer quarterly amount differs")
            if money(q["operating_cash_flow"])-money(q["cash_purchases"])!=money(q["operating_cash_less_purchases"]):
                raise ValueError("Original OCF minus purchases mismatch")
        q1_available=first_eligible(registry,[q1["source"]])
        q2_available=first_eligible(registry,b["sources"])
        if (q1_available.isoformat()!=expected["q1"]["available"]
            or q2_available.isoformat()!=expected["q2"]["available"]
            or q1["all_cited_checks_available"]!=q1_available.isoformat()):
            raise ValueError("Q1/Q2 first-available date mistyped")
        capex_gap_q2=money(q2["cash_purchases"])-money(q2["operating_cash_flow"])
        if capex_gap_q2!=money(b["cash_purchases_less_operating_cash"]):
            raise ValueError("Funding ledger must equal same-issuer Q2 deficit")
        if (money(b["cash_including_restricted"]["end"])
            -money(b["cash_including_restricted"]["start"])
            !=money(q2["operating_cash_flow"])+money(b["net_investing_cash"])
                 +money(b["net_financing_cash"])
                 +(money(b["separately_reported_exchange_effect"])
                   if b["separately_reported_exchange_effect"] is not None
                   else Decimal(0))):
            raise ValueError("Actual Q2 operating+investing+financing+FX cash identity failed")
        if as_of>=q1_available:
            visible.append({
                "issuer":issuer,"period":"2026-Q1",
                "source_eligible_at":q1_available.isoformat(),
                "ocf_usd_m":json_dec(money(q1["operating_cash_flow"])),
                "cash_purchases_usd_m":json_dec(money(q1["cash_purchases"])),
                "ocf_less_purchases_usd_m":json_dec(money(q1["operating_cash_less_purchases"])),
                "cash_purchase_scope":expected["scope"],
                "net_financing_cash_usd_m":None,
                "quarter_source_ids":[q1["source"]],
                "original_sec_source_urls":[registry[q1["source"]]["source_page"]],
                "funding_split_by_lender_usd_m":None,
            })
        if as_of>=q2_available:
            q1gap=money(q1["operating_cash_less_purchases"])
            q2gap=money(q2["operating_cash_less_purchases"])
            visible.append({
                "issuer":issuer,"period":"2026-Q2",
                "source_eligible_at":q2_available.isoformat(),
                "ocf_usd_m":json_dec(money(q2["operating_cash_flow"])),
                "cash_purchases_usd_m":json_dec(money(q2["cash_purchases"])),
                "ocf_less_purchases_usd_m":json_dec(q2gap),
                "qoq_change_ocf_minus_cash_purchases_usd_m":json_dec(q2gap-q1gap),
                "cash_purchase_scope":expected["scope"],
                "net_investing_cash_usd_m":json_dec(money(b["net_investing_cash"])),
                "net_financing_cash_usd_m":json_dec(money(b["net_financing_cash"])),
                "q2_financing_components_usd_m":b["financing_components_signed"],
                "q2_financing_type":expected["financing_type"],
                "net_change_cash_including_restricted_usd_m":
                    json_dec(money(b["cash_including_restricted"]["change"])),
                "q2_financing_is_not_all_new_loan_borrowing":True,
                "no_direct_evidence_of_same_quarter_bank_lender_loss":True,
                "quarter_source_ids":b["sources"],
                "original_sec_source_urls":[registry[z]["source_page"] for z in b["sources"]],
                "funding_split_by_lender_usd_m":None,
            })
    visible.sort(key=lambda r:(r["period"],r["issuer"]))
    at_q2=[x for x in visible if x["period"]=="2026-Q2"]
    if len(at_q2) not in (0,2):
        raise ValueError("Inconsistent Q2 source date between issuers")
    direct_financing=(
        {r["issuer"]:r["q2_financing_type"] for r in at_q2} if at_q2 else {}
    )
    return {
        "schema":"aics-v30-issuer-cashflow-financing-identity-source-gated-research-v1",
        "as_of":as_of.isoformat(),
        "issuer_quarter_observations":visible,
        "q2_same_date_comparable_two_issuer_count":len(at_q2),
        "q2_both_issuers_ocf_purchases_shortfall":len(at_q2)==2,
        "q2_observed_financing_type_per_issuer":direct_financing,
        "q2_independent_funding_source_reconciliation_complete":len(at_q2)==2,
        "source_first_pit_provider_delivery_attested":False,
        "cashflow_financing_identity_not_causal_allocation":True,
        "contemporaneous_2026Q2_loan_issuances_directly_attributed_to_ddtl4_5":False,
        "q2_cashflow_is_not_net_lender_debt_outstanding":True,
        "net_financing_not_equivalent_to_accessible_undrawn_bank_liquidity":True,
        "grouped_neocloud_loan_aggregate_current_outstanding_usd_m":None,
        "credit_spread_repricing_on_matched_instrument_bps":None,
        "historically_comparable_matched_borrower_pricing_event_count":0,
        "coreweave_ddtl4_vs_ddtl5_spread_difference_is_not_time_series_repricing":True,
        "actual_credit_default_or_covenant_breach":None,
        "predictive_lead_over_2000_or_2008":None,
        "2000_similarity_pct":None,"2008_similarity_pct":None,
        "crisis_probability":None,"full_aics":None,
        "original_weights_total_unchanged":1050,"weights_changed":False,
        "trades_created":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    args=p.parse_args()
    rep=build(read(FUNDING),read(CASH),read(SEC),as_of=args.as_of)
    rep["input_source_file_sha256"]={
        str(x):hashlib.sha256(x.read_bytes()).hexdigest()
        for x in (FUNDING,CASH,SEC)
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "issuer_quarters":len(rep["issuer_quarter_observations"]),
        "q2_cashflow_funding_bridges":rep["q2_same_date_comparable_two_issuer_count"],
        "contemporaneous_matched_loan_repricing_events":0,
        "bank_contagion_probability":None,"production_index":None,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
