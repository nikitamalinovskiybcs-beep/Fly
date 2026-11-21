"""AICS V27: publication-gated, non-additive SPV recourse vs AI buildout.

CoreWeave June-2026 facility reported debt is a dated balance, not a parent's
loss or proof of an October funding run. Nscale's rent, credit ceilings,
historical draws and consolidated balance are DISTINCT accounting objects.
Never add them, backdate source receipts or promote a 2008-crisis prediction.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS

ROOT=Path("aics_data/research")
CORE=ROOT/"coreweave_two_spv_debt_original_independent_rehash_2026-11-19.json"
CLOUD=ROOT/"neocloud_cash_coverage_2026_h1.json"
NSCALE=ROOT/"nscale_s1_historical_draws_original_rehash_2026-11-19.json"
DFS=ROOT/"nscale_dfs_s1_source_replay_rehash_2026-11-19.json"
OUTPUT=ROOT/"aics_v27_spv_funding_transmission_research_2026-11-22.json"
SHA=re.compile(r"^[0-9a-f]{64}$")
TWO=Decimal("0.01")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dec(value):
    if isinstance(value,bool):
        raise ValueError("Boolean masquerading as financial number")
    x=Decimal(str(value))
    if not x.is_finite() or x<0:
        raise ValueError("Invalid original positive dollar amount")
    return x


def pct(a,b):
    return str((dec(a)*100/dec(b)).quantize(TWO,rounding=ROUND_HALF_UP))


def _sha(value):
    if not isinstance(value,str) or SHA.fullmatch(value) is None:
        raise ValueError("Missing verified source SHA-256")


def _dated_source(filed,available,asof):
    day=dt.date.fromisoformat(filed)
    if dt.date.fromisoformat(available)!=day+dt.timedelta(days=14):
        raise ValueError("Source violates legacy SEC filed_at + 14")
    return dt.date.fromisoformat(available)<=asof


def build(core,cloud,nscale,dfs,*,imbalance=None,as_of=None):
    if isinstance(as_of,str):
        as_of=dt.date.fromisoformat(as_of)
    if as_of is None:
        as_of=dt.datetime.now(dt.timezone.utc).date()
    if not isinstance(as_of,dt.date) or isinstance(as_of,dt.datetime):
        raise ValueError("Explicit as-of calendar date required")
    if sum(WEIGHTS.values())!=1050:
        raise ValueError("Immutable production weights altered")
    if (
        core.get("schema_version")!="aics-coreweave-ddtl4-ddtl5-original-sec-independent-rehash-v1"
        or core.get("original_issuer")!="CoreWeave"
        or core.get("economic_report_date")!="2026-06-30"
        or core.get("original_accession")!="0001769628-26-000366"
        or core.get("original_form")!="10-Q"
        or core.get("original_sec_url")!="https://www.sec.gov/Archives/edgar/data/1769628/000176962826000366/0001769628-26-000366.txt"
        or core.get("source_replay_second_pass_sha256")!=core.get("source_replay_report_sha256")
        or core.get("report_replayed_exactly") is not True
        or core.get("independent_raw_rehash_performed_outside_github_actions") is not True
        or core.get("historical_pit_source_delivery_verified") is not False
        or core.get("indexed_stress_score") is not None
        or core.get("index_aics") is not None
        or cloud.get("coreweave_facilities",{}).get("as_of")!="2026-06-30"
        or cloud.get("coreweave_facilities",{}).get("available_at")!="2026-08-26"
        or cloud.get("node_score") is not None
        or cloud.get("index_aics") is not None
        or nscale.get("schema_version")!="aics-nscale-s1-three-actual-debt-facts-external-artifact-rehash-v1"
        or nscale.get("source_filing_accession")!="0001193125-26-395475"
        or nscale.get("rehashed_outside_github_actions") is not True
        or nscale.get("cross_facility_amounts_additive") is not False
        or nscale.get("independent_live_time_pit_attested") is not False
        or nscale.get("aggregate_current_spv_exposure_usd") is not None
        or nscale.get("index_aics") is not None
        or dfs.get("schema_version")!="aics-nscale-dfs-s1-original-replay-external-rehash-v1"
        or dfs.get("source_filing_accession")!=nscale.get("source_filing_accession")
        or dfs.get("source_issuer_cik")!=nscale.get("source_issuer_cik")
        or dfs.get("independent_historical_provider_pit_attested") is not False
        or dfs.get("gpu_facility_and_dfs_rent_additive") is not False
        or dfs.get("drawn_gpu_principal_usd") is not None
        or dfs.get("combined_economic_exposure_usd") is not None
        or dfs.get("index_aics") is not None
    ):
        raise ValueError("Original SPV-recourse sources inconsistent or ineligible")
    for digest in ("original_full_submission_sha256","independently_recalculated_artifact_zip_sha256","source_replay_report_sha256"):
        _sha(core.get(digest))
    _sha(nscale.get("zip_original_sha256"));_sha(dfs.get("downloaded_zip_sha256"))
    a={r["source_id"]:r["sha256"] for r in nscale.get("original_documents",[])}
    b={r["source_id"]:r["sha256"] for r in dfs.get("original_source_files_independently_sha_rehashed_outside_actions",[])}
    if a!=b or sorted(a)!=["nscale_s1_narrative","ward_ex10_23"]:
        raise ValueError("Nscale independent source records contradict")
    for digest in a.values():
        _sha(digest)
    core_ok=_dated_source(core["sec_filed_at"],core["strict_aics_sec_available_at"],as_of)
    nscale_ok=_dated_source(nscale["source_sec_filed_at"],nscale["source_sec_available_at_plus_14_days"],as_of)
    dfs_ok=_dated_source(dfs["original_sec_filed_at"],dfs["sec_available_at"],as_of)
    if nscale_ok!=dfs_ok or dfs["sec_available_at"]!=nscale["source_sec_available_at_plus_14_days"]:
        raise ValueError("Nscale duplicate S-1 candidate availability inconsistent")
    if core["strict_aics_sec_available_at"]!="2026-08-26" or dfs["sec_available_at"]!="2026-10-02":
        raise ValueError("SPV historical source availability must not drift")

    observed_core=None
    core_dates=[]
    if core_ok:
        obs=core.get("observations",[])
        if len(obs)!=2 or len(cloud["coreweave_facilities"]["facilities"])!=2:
            raise ValueError("Missing 2 same-date SPV debt disclosures")
        names=("DDTL 4.0","DDTL 5.0")
        borrowers=("CoreWeave Compute Acquisition Co. VIII, LLC","CoreWeave Financing DDTL V, LLC")
        recourses=("Non-recourse except for customary limited guarantees","Unconditional parent guarantee")
        items=[]
        total_debt,total_ceiling=Decimal(0),Decimal(0)
        for i,(record,cross) in enumerate(zip(obs,cloud["coreweave_facilities"]["facilities"])):
            if (record.get("facility")!=names[i] or record.get("borrower")!=borrowers[i]
                or record.get("recourse")!=recourses[i]
                or record.get("parent_enforceable_guarantee_usd_m") is not None
                or any(record.get(k)!=cross.get(k) for k in ("facility","borrower","reported_debt_usd_m","facility_ceiling_usd_m","recourse"))
            ):
                raise ValueError("CoreWeave instrument, legal borrower or recourse misrepresented")
            debt,ceiling=dec(record["reported_debt_usd_m"]),dec(record["facility_ceiling_usd_m"])
            if debt>ceiling or pct(debt,ceiling)!=record["reported_balance_to_ceiling_pct"]:
                raise ValueError("Debt/facility utilization arithmetic broken")
            total_debt+=debt;total_ceiling+=ceiling
            items.append({"facility":names[i],"borrower":borrowers[i],
                          "reported_debt_usd_m":int(debt),"contractual_facility_ceiling_usd_m":int(ceiling),
                          "reported_balance_to_ceiling_pct":pct(debt,ceiling),
                          "recourse":recourses[i],"parent_enforceable_guarantee_usd_m":None,
                          "named_lender_or_participant_exposure_usd_m":None,
                          "economic_balance_asof":"2026-06-30",
                          "information_eligible_at":"2026-08-26"})
        if (total_debt!=dec(core["separate_same_date_facility_reported_debt_total_usd_m"])
            or total_ceiling!=dec(core["separate_same_date_facility_ceiling_total_usd_m"])
            or pct(total_debt,total_ceiling)!=core["reported_debt_to_ceiling_pct"]):
            raise ValueError("CoreWeave same-date sum does not reconcile")
        core_cash=[x for x in cloud.get("observations",[])
                   if x["issuer"]=="CoreWeave" and x["period"]=="2026-Q2"]
        if (len(core_cash)!=1 or core_cash[0]["all_cited_checks_available"]!="2026-08-26"
            or dec(core_cash[0]["cash_purchases"])-dec(core_cash[0]["operating_cash_flow"])!=Decimal(5743)
            or core_cash[0]["operating_cash_less_purchases"]!="-5743"):
            raise ValueError("CoreWeave Q2 cashflow cannot be tied to own issuer/date")
        observed_core={
            "facility_balance_date":"2026-06-30",
            "source_available_at":"2026-08-26",
            "facilities":items,
            "separate_facility_reported_debt_sum_usd_m":int(total_debt),
            "separate_facility_ceiling_sum_usd_m":int(total_ceiling),
            "reported_debt_to_ceiling_pct":pct(total_debt,total_ceiling),
            "same_issuer_coreweave_q2_ocf_minus_cash_ppe_usd_m":-5743,
            "cash_gap_is_not_debt_draw":True,
            "reported_facility_debt_is_not_parent_loss":True,
            "releasetime_pit_independently_attested":False,
        }
        core_dates=[{"issuer":"CoreWeave","borrower":x["borrower"],"facility":x["facility"],
                     "reported_debt_usd_m":x["reported_debt_usd_m"],"asof":"2026-06-30",
                     "first_research_eligible_at":"2026-08-26"}
                    for x in items]

    observed_nscale=None
    if nscale_ok:
        ns=nscale["original_sec_observed_financing_research"]
        uk=ns["gpu_services_uk_facility"]
        mac=ns["macquarie_senior_facility"]
        cons=ns["consolidated_nscale"]
        df=dfs["extracted_from_same_original_s1"]
        if (
            uk.get("named_borrower")!="Nscale Services UK Ltd"
            or uk.get("historical_observation_date")!="2026-03-31"
            or dec(uk.get("approx_drawn_and_outstanding_usd"))!=58900000
            or uk.get("current_outstanding_usd") is not None
            or mac.get("named_borrower")!="Nscale Global Holdings Limited"
            or mac.get("named_lender")!="Macquarie Bank Limited"
            or mac.get("current_outstanding_usd") is not None
            or mac.get("includes_letter_of_credit_facility") is not True
            or [r["date"] for r in mac["historical_utilizations"]]!=["2025-08-01","2026-01-30"]
            or [dec(r["amount_usd"]) for r in mac["historical_utilizations"]]!=[Decimal(70100000),Decimal(34900000)]
            or sum((dec(r["amount_usd"]) for r in mac["historical_utilizations"]),Decimal(0))!=dec(mac["historical_utilizations_sum_usd"])
            or cons.get("historical_observation_date")!="2026-06-30"
            or dec(cons.get("total_debt_carrying_value_usd"))!=137400000
            or cons.get("current_debt_carrying_value_usd") is not None
            or df.get("as_reported_at")!="2026-09-04"
            or df.get("guarantor")!="Nscale Global Holdings Ltd"
            or df.get("provider")!="Dell Financial Services L.L.C."
            or df.get("customer_spv_borrowers")!=["Nscale Ward County Borrower SPV, LLC","Nscale NC Borrower SPV, LLC"]
            or df.get("executed_payment_schedules")!=40
            or dec(df.get("approximate_initial_term_rent_usd"))!=2540000000
            or dec(df.get("approximate_included_financing_charges_usd"))!=34800000
            or dec(df.get("gpu_facility_ceiling_ward_county_usd"))!=1850000000
            or dec(df.get("gpu_facility_ceiling_north_carolina_usd"))!=1200000000
            or nscale.get("ward_county_spv_drawn_amount_usd") is not None
            or nscale.get("north_carolina_spv_drawn_amount_usd") is not None
            or dfs.get("legally_enforceable_parent_guarantee_amount_usd") is not None
            or dfs.get("outstanding_lease_liability_usd") is not None
        ):
            raise ValueError("Nscale instrument identity, value type or obligation term changed")
        observed_nscale={
            "source_available_at":"2026-10-02",
            "s1_observed_as_reported_at":"2026-09-04",
            "ward_gpu_contractual_ceiling_usd_m":1850,
            "north_carolina_gpu_contractual_ceiling_usd_m":1200,
            "combined_two_gpu_ceiling_usd_m":3050,
            "ward_drawn_balance_usd_m":None,
            "north_carolina_drawn_balance_usd_m":None,
            "dell_initial_term_rent_usd_m_includes_financing_charges":2540,
            "included_financing_charges_usd_m":34.8,
            "outstanding_lease_liability_usd_m":None,
            "dell_guarantor":"Nscale Global Holdings Ltd",
            "legally_enforceable_parent_guarantee_usd_m":None,
            "separate_uk_gpu_services_historical_2026_03_31_drawn_usd_m":58.9,
            "separate_macquarie_historical_utilizations_usd_m_not_current_outstanding":105,
            "macquarie_named_lender":"Macquarie Bank Limited",
            "separate_nscale_consolidated_2026_06_30_debt_carrying_usd_m":137.4,
            "sum_of_3050_2540_137_4_105_58_9_as_exposure":None,
            "historical_publication_receipt_independently_pit_attested":False,
        }
    macro=None
    if imbalance is not None:
        if (imbalance.get("schema")!="aics-precrisis-four-hyperscaler-source-gated-cash-imbalance-research-v1"
            or imbalance.get("as_of")!=as_of.isoformat()
            or imbalance.get("full_11_node_aics") is not None
            or imbalance.get("primary_source_document_bytes_independently_historical_pit_attested") is not False
            or imbalance.get("similarity_to_2000_pct") is not None
            or imbalance.get("similarity_to_2008_pct") is not None):
            raise ValueError("Invalid date-scoped buildout imbalance for juxtaposition")
        q={x["period"]:x for x in imbalance["complete_or_partial_quarters"]}
        if (q.get("2026-Q2") is not None and q["2026-Q2"].get("four_issuer_complete") and
            q["2026-Q2"]["four_issuer_cash_gap_usd_m"]!="6709"):
            raise ValueError("Hyperscaler June cash gap no longer matches original")
        if (q.get("2026-Q3") is not None and q["2026-Q3"].get("four_issuer_complete") and
            q["2026-Q3"]["four_issuer_cash_gap_usd_m"]!="-26425"):
            raise ValueError("Hyperscaler September cash gap no longer matches original")
        macro={
            "hyperscaler_four_issuer_q2_2026_gap_usd_m":
                int(q["2026-Q2"]["four_issuer_cash_gap_usd_m"]) if
                "2026-Q2" in q and q["2026-Q2"]["four_issuer_complete"] else None,
            "hyperscaler_four_issuer_q3_2026_gap_usd_m":
                int(q["2026-Q3"]["four_issuer_cash_gap_usd_m"]) if
                "2026-Q3" in q and q["2026-Q3"]["four_issuer_complete"] else None,
            "hyperscalers_are_not_coreweave_or_nscale":True,
            "same_counterparty_exposure_or_transmission_proven":False,
        }
    return {
        "schema":"aics-v27-spv-and-buildout-pit-gated-recourse-bridge-v1",
        "as_of":as_of.isoformat(),
        "underlying": {"coreweave":str(CORE),"nscale":str(NSCALE),"dfs":str(DFS),"neocloud_cash":str(CLOUD)},
        "coreweave":observed_core,"coreweave_facility_edges":core_dates,
        "nscale":observed_nscale,
        "hyperscaler_buildout_context":macro,
        "proven_same_date_coreweave_facility_balance_edges":len(core_dates),
        "named_lender_to_borrower_current_exposure_edges":0,
        "named_historical_nscale_lender_borrower_relationships":1 if nscale_ok else 0,
        "verified_2008_funding_contagion_matrix":None,
        "spv_parent_enforceable_guarantee_total_usd_m":None,
        "nscale_gpu_drawn_total_usd_m":None,
        "current_combined_spv_debt_usd_m":None,
        "debt_ceiling_plus_rent_aggregate_usd_m":None,
        "observations_additive_across_issuers_types_or_dates":False,
        "contractual_ceilings_as_available_liquidity":False,
        "issuer_only_spv_to_global_buildout_causality_proven":False,
        "sec_plus14_is_policy_proxy_not_historical_provider_receipt":True,
        "independent_historical_pit_attested":False,
        "historical_crisis_2000_similarity_pct":None,
        "historical_crisis_2008_similarity_pct":None,
        "forecast_crisis_probability":None,
        "new_aics_node_score":None,
        "full_11node_aics":None,
        "independent_24month_oos":False,
        "weights_total_unchanged":1050,"production_weights_changed":False,
        "trades_created":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=OUTPUT)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    args=p.parse_args()
    from scripts.aics_early_imbalance_cashflow_shadow import (
        build as build_imbalance, Y2025, Q42025, Q12026, Q22026, Q32026)
    macro=build_imbalance(read(Y2025),read(Q42025),read(Q22026),read(Q32026),
                          q1=read(Q12026),as_of=args.as_of)
    report=build(read(CORE),read(CLOUD),read(NSCALE),read(DFS),
                 imbalance=macro,as_of=args.as_of)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({
        "original_spv_facility_edges":report["proven_same_date_coreweave_facility_balance_edges"],
        "coreweave_reported_debt_usd_m":report["coreweave"]["separate_facility_reported_debt_sum_usd_m"] if report["coreweave"] else None,
        "nscale_outstanding_gpu_draws_usd_m":None,
        "historical_2008_pit_contagion_matrix":None,
        "model_reweighting":False,"trades":False,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
