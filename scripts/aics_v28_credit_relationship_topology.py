"""AICS V28: source-dated legal lender→borrower→guarantor edge ledger.

A relationship is NOT an additive credit exposure. Historical draw events,
facility ceilings, consolidated balance, rental payment schedules and
guarantee recourse have different units/meaning even when all are USD.
No original 2026 provider receipts independently PIT-attested, current
lender risk exposures, model score, probability or trading authorization.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_spv_funding_transmission_bridge import (
    build as build_spv, read, CORE, CLOUD, NSCALE, DFS,
)
from scripts.aics_spv_nscale_contract_gate import (
    audit as nc_audit, ContractEvidenceError, REGISTRY, OBSERVED,
)
from scripts.aics_early_imbalance_cashflow_shadow import (
    build as build_imbalance, Y2025, Q42025, Q12026, Q22026, Q32026,
)

ROOT = Path("aics_data/research")
WARD = ROOT / "nscale_ward_original_sec_independent_rehash_2026-11-19.json"
KVANDAL = ROOT / "nscale_kvandal_south_2026-09-18.json"
NEBIUS = ROOT / "nebius_sec_6k_credit_facility_2026_10_22.json"
OUT = ROOT / "aics_v28_named_lender_borrower_guarantor_network_2026-11-22.json"


def money(x):
    if isinstance(x,bool):
        raise ValueError("Boolean financial amount")
    d = Decimal(str(x))
    if not d.is_finite() or d<0:
        raise ValueError("Nonpositive/or invalid amount")
    return d


def eligible(filed, available, asof):
    f=dt.date.fromisoformat(filed)
    a=dt.date.fromisoformat(available)
    if a!=f+dt.timedelta(days=14):
        raise ValueError("SEC +14 filing date rule violated")
    return a<=asof


def edge(*, id, from_entity, to_entity, relation, amount_usd_m,
         amount_kind, source, eligible_at, observation_asof,
         current_credit_exposure_verified=False, group=False):
    if not all(isinstance(v,str) and v for v in (id,from_entity,to_entity,relation,
                                                  amount_kind,source,eligible_at,observation_asof)):
        raise ValueError("Source or exact legal entity missing")
    if amount_usd_m is not None:
        money(amount_usd_m)
    return {
        "id":id,"from":from_entity,"to":to_entity,
        "relationship":relation,"amount_usd_m":amount_usd_m,
        "amount_semantics":amount_kind,"source":source,
        "source_eligible_at":eligible_at,"economic_observation_date":observation_asof,
        "borrower_group_not_per_borrower_split":group,
        "current_credit_exposure_verified":current_credit_exposure_verified,
        "historical_first_delivery_pit_attested":False,
        "combined_effective_exposure_usd_m":None,
    }


def build(*, bridge, ward, nc_contract, kvandal, nebius, as_of):
    if isinstance(as_of,str):as_of=dt.date.fromisoformat(as_of)
    if not isinstance(as_of,dt.date) or isinstance(as_of,dt.datetime):
        raise ValueError("Calendar date as-of required")
    if (sum(WEIGHTS.values())!=1050
        or bridge.get("schema")!="aics-v27-spv-and-buildout-pit-gated-recourse-bridge-v1"
        or bridge.get("as_of")!=as_of.isoformat()
        or bridge.get("independent_historical_pit_attested") is not False
        or bridge.get("named_lender_to_borrower_current_exposure_edges")!=0
        or bridge.get("full_11node_aics") is not None
        or bridge.get("trades_created") is not False):
        raise ValueError("Illegal V27 source or model promotion")
    if (ward.get("schema_version")!="aics-nscale-ward-original-sec-zip-independent-rehash-v1"
        or ward.get("sec_accession")!="0001193125-26-395475"
        or ward.get("borrower")!="Nscale Ward County Borrower SPV, LLC"
        or ward.get("affiliate_guarantor")!="Nscale Ward County, LLC"
        or ward.get("fixed_delayed_draw_commitment_usd")!=630000000
        or ward.get("floating_delayed_draw_commitment_usd")!=1220000000
        or ward.get("facility_commitment_ceiling_usd")!=1850000000
        or ward.get("drawn_principal_for_either_facility_usd") is not None
        or ward.get("parent_guarantee_amount_usd") is not None
        or ward.get("independent_historical_provider_pit_attestation") is not False
        or nc_contract.get("schema_version")!="aics-spv-nscale-contract-original-lineage-gate-v1"
        or nc_contract.get("sec_accession")!=ward.get("sec_accession")
        or nc_contract.get("named_borrower")!="Nscale NC Borrower SPV, LLC"
        or nc_contract.get("named_affiliate_guarantor")!="Nscale Services US Inc."
        or nc_contract.get("fixed_commitment_usd")!=370000000
        or nc_contract.get("floating_commitment_usd")!=830000000
        or nc_contract.get("contractual_ceiling_usd")!=1200000000
        or nc_contract.get("drawn_principal_usd") is not None
        or nc_contract.get("effective_recourse_usd") is not None
        or nc_contract.get("independently_attested_historical_pit") is not False):
        raise ValueError("Nscale original two SPV legal agreements not independently reconciled")
    if (ward.get("sec_available_at")!=nc_contract.get("sec_available_at")
        or ward.get("sec_available_at")!="2026-10-02"
        or ward.get("sec_filed_at")!="2026-09-18"
        or nc_contract.get("sec_filed_at")!=ward.get("sec_filed_at")
        or not eligible(ward["sec_filed_at"],ward["sec_available_at"],dt.date(2026,11,22))):
        raise ValueError("Nscale S-1 availability inconsistent")
    originals=ward.get("source_originals",[])
    if (len(originals)!=2 or
        sorted(x["source_id"] for x in originals)!=["nscale_s1_narrative","ward_ex10_23"] or
        not all(len(x.get("sha256",""))==64 and x["url"].startswith("https://www.sec.gov/Archives/edgar/data/2110365/")
                for x in originals) or
        len(ward.get("zip_sha256",""))!=64 or
        ward.get("raw_original_html_independently_rehashed_outside_actions")!=2):
        raise ValueError("Original 2-file source rehash lineage missing")
    if (kvandal.get("project")!="Kvandal South DC"
        or kvandal.get("original_borrower")!="Nscale Norway DC DA"
        or kvandal.get("agreement_date")!="2026-07-07"
        or kvandal.get("source")!=originals[1]["url"]
        or kvandal.get("draw_period")!="2026-08"
        or kvandal.get("parent_guarantee_reported") is not True
        or kvandal.get("guarantor_legal_name_verified") is not None
        or kvandal.get("closing_balance") is not None
        or len(kvandal.get("facilities",[]))!=2
        or [(r["type"],r["base_limit"],r["draws_in_period"]) for r in kvandal["facilities"]]
           !=[("senior term",725,88.1),("revolving VAT",65,19.1)]
        or kvandal.get("base_limits_total")!=790
        or kvandal.get("draws_in_period_total")!=107.2):
        raise ValueError("Kvandal historical draws mistaken for balances")
    if (nebius.get("record_id")!="NBIS_TERM_LOAN_20261022"
        or nebius.get("schema_version")!="aics-research-source-terms-v1"
        or nebius.get("source_accession")!="0001104659-26-117978"
        or nebius.get("source_url")!="https://www.sec.gov/Archives/edgar/data/1513845/000110465926117978/tm2628078d1_6k.htm"
        or nebius.get("terms",{}).get("aggregate_principal_capacity_usd")!=3500000000
        or nebius["terms"].get("amount_currently_drawn_usd") is not None
        or nebius.get("spv_legal_structure_proven") is not False
        or nebius.get("score_eligible") is not False
        or nebius.get("independently_verified_pit") is not False
        or nebius.get("raw_source_sha256") is not None
        or nebius.get("index_aics") is not None):
        raise ValueError("Nebius bridge capacity is not a drawn SPV balance")
    if nebius["terms"]["borrower_entities"]!=["Nebius Group N.V.","Nebius Inc.","Nebius B.V."]:
        raise ValueError("Nebius borrower roster altered")
    if not eligible(nebius["source_filing_date"],nebius["available_at"],dt.date(2026,11,22)):
        raise ValueError("Nebius SEC source dates inconsistent")
    date=as_of.isoformat()
    edges=[]
    core=bridge["coreweave"]
    if core is not None:
        for item in core["facilities"]:
            edges.append(edge(
                id="COREWEAVE_"+item["facility"].replace(" ","_"),
                from_entity="UNDISCLOSED_LENDER_POOL",
                to_entity=item["borrower"],
                relation="historical_borrower_facility_debt",
                amount_usd_m=item["reported_debt_usd_m"],
                amount_kind="reported_debt_principal_asof_2026_06_30_not_current_lender_exposure",
                source=str(CORE),eligible_at="2026-08-26",
                observation_asof="2026-06-30"))
        if [x["amount_usd_m"] for x in edges]!=[2837,1101]:
            raise ValueError("CoreWeave historical balances corrupted")
    if eligible(ward["sec_filed_at"],ward["sec_available_at"],as_of):
        edges.extend([
            edge(id="WARD_LIMIT",from_entity="UNDISCLOSED_GPU_LENDER_POOL",
                 to_entity=ward["borrower"],relation="contractual_credit_capacity",
                 amount_usd_m=1850,amount_kind="facility_commitment_ceiling_not_drawn",
                 source=str(WARD),eligible_at="2026-10-02",observation_asof="2026-09-18"),
            edge(id="NC_LIMIT",from_entity="UNDISCLOSED_GPU_LENDER_POOL",
                 to_entity=nc_contract["named_borrower"],relation="contractual_credit_capacity",
                 amount_usd_m=1200,amount_kind="facility_commitment_ceiling_not_drawn",
                 source=str(REGISTRY),eligible_at="2026-10-02",observation_asof="2026-09-18"),
            edge(id="DELL_GROUP_RENT",from_entity="Dell Financial Services L.L.C.",
                 to_entity="Nscale Ward County Borrower SPV, LLC + Nscale NC Borrower SPV, LLC",
                 relation="combined_initial_rental_obligation",
                 amount_usd_m=2540,amount_kind="initial_term_rent_including_financing_charges_not_drawn_debt",
                 source=str(DFS),eligible_at="2026-10-02",observation_asof="2026-09-04",group=True),
            edge(id="MACQUARIE_HISTORY",from_entity="Macquarie Bank Limited",
                 to_entity="Nscale Global Holdings Limited",relation="historical_utilization_events",
                 amount_usd_m=105,amount_kind="sum_two_historical_utilization_events_not_current_outstanding",
                 source=str(NSCALE),eligible_at="2026-10-02",observation_asof="2026-01-30"),
            edge(id="KVANDAL_TERM_DRAW",from_entity="UNDISCLOSED_LENDER_POOL",
                 to_entity="Nscale Norway DC DA",relation="historical_draw_event",
                 amount_usd_m=88.1,amount_kind="august_2026_period_draw_senior_term_not_closing_balance",
                 source=str(KVANDAL),eligible_at="2026-10-02",observation_asof="2026-08-31"),
            edge(id="KVANDAL_VAT_DRAW",from_entity="UNDISCLOSED_LENDER_POOL",
                 to_entity="Nscale Norway DC DA",relation="historical_draw_event",
                 amount_usd_m=19.1,amount_kind="august_2026_period_draw_revolving_vat_not_closing_balance",
                 source=str(KVANDAL),eligible_at="2026-10-02",observation_asof="2026-08-31"),
        ])
    if eligible(nebius["source_filing_date"],nebius["available_at"],as_of):
        edges.append(edge(id="NEBIUS_6K_CAPACITY",from_entity="UNDISCLOSED_FINANCING_PROVIDER",
                          to_entity="Nebius Group N.V. + Nebius Inc. + Nebius B.V.",
                          relation="secured_term_loan_contractual_capacity",
                          amount_usd_m=3500,amount_kind="three_coborrowers_one_facility_not_3x_and_not_drawn",
                          source=str(NEBIUS),eligible_at="2026-11-05",observation_asof="2026-10-17",group=True))
    guarantee=[]
    if eligible(ward["sec_filed_at"],ward["sec_available_at"],as_of):
        guarantee=[
            {"guarantor":ward["affiliate_guarantor"],"for_borrower":ward["borrower"],
             "extent_usd_m":None,"kind":"affiliate_guarantee_amount_unverified",
             "first_eligible_at":"2026-10-02","source":str(WARD)},
            {"guarantor":nc_contract["named_affiliate_guarantor"],"for_borrower":nc_contract["named_borrower"],
             "extent_usd_m":None,"kind":"affiliate_guarantee_amount_unverified",
             "first_eligible_at":"2026-10-02","source":str(REGISTRY)},
        ]
    ids=[x["id"] for x in edges]
    if len(ids)!=len(set(ids)) or any(x["source_eligible_at"]>date for x in edges):
        raise ValueError("Duplicate or future source relationship")
    current_lender_exposures=[x for x in edges if x["current_credit_exposure_verified"]]
    if current_lender_exposures:
        raise ValueError("Cannot claim present lender counterparty exposures")
    named_financing_edges=[
        x for x in edges if x["id"] in ("DELL_GROUP_RENT","MACQUARIE_HISTORY")]
    return {
        "schema":"aics-v28-source-gated-credit-relationship-topology-research-v1",
        "as_of":date,"source_v27_bridge":str(ROOT/"aics_v27_spv_funding_transmission_research_2026-11-22.json"),
        "relationships":edges,"guarantor_relationships":guarantee,
        "historical_coreweave_two_facility_debt_count":sum(x["relationship"]=="historical_borrower_facility_debt" for x in edges),
        "named_financing_provider_relationship_count":len(named_financing_edges),
        "named_provider_types":["lease_rent_provider_not_lender_exposure","historical_facility_lender_not_current_exposure"] if named_financing_edges else [],
        "named_guarantor_legal_links":len(guarantee),
        "historical_kvandal_period_draws_total_usd_m_not_outstanding":
            "107.2" if "KVANDAL_TERM_DRAW" in ids else None,
        "same_date_present_value_of_all_relationships_usd_m":None,
        "contractual_capacity_additive_to_rents_and_balances":False,
        "current_named_lender_to_borrower_dollar_exposure_edges":0,
        "current_lender_borrower_dollar_exposure_matrix":None,
        "network_2008_contagion_calibrated":False,
        "liquidity_run_and_repo_haircuts_original_verified":False,
        "historical_2000_similarity_pct":None,
        "historical_2008_similarity_pct":None,
        "crisis_forecast_probability":None,
        "historical_provider_pit_certified":False,
        "independently_validated_24m_oos":False,
        "index_aics":None,"spv_node_score":None,"fixed_weights_total":1050,
        "production_weights_changed":False,"verdict_mutated":False,"trades_created":False,
        "next_missing":
            ["Current exact lender names and funded amount per CoreWeave facility",
             "Nscale Ward/NC actual drawn principal and legal guarantee caps",
             "DFS liability current outstanding rather than gross rent",
             "Macquarie current lender exposure",
             "Kvandal month-end outstanding and exact lending syndicate",
             "Nebius lender identities and funded outstanding",
             "Datestamped maturity/repo haircut transmission to insurers/BDCs"],
    }


def from_originals(bridge, *, as_of):
    """Reconcile pinned original source receipts without new network requests."""
    registry_bytes=REGISTRY.read_bytes()
    gate=nc_audit(json.loads(registry_bytes),read(OBSERVED),registry_bytes)
    return build(bridge=bridge,ward=read(WARD),nc_contract=gate,
                 kvandal=read(KVANDAL),nebius=read(NEBIUS),as_of=as_of)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    a=p.parse_args()
    asof=dt.date.fromisoformat(a.as_of)
    cash=build_imbalance(read(Y2025),read(Q42025),read(Q22026),read(Q32026),
                         q1=read(Q12026),as_of=asof)
    spv=build_spv(read(CORE),read(CLOUD),read(NSCALE),read(DFS),
                  imbalance=cash,as_of=asof)
    report=from_originals(spv,as_of=asof)
    report["input_file_sha256"]={
        str(path):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (WARD,KVANDAL,NEBIUS,REGISTRY,OBSERVED,CORE,CLOUD,NSCALE,DFS)
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({
        "as_of":report["as_of"],
        "typed_credit_relationships":len(report["relationships"]),
        "named_historical_financing_provider_links":report["named_financing_provider_relationship_count"],
        "known_named_guarantor_links":report["named_guarantor_legal_links"],
        "current_named_lender_dollar_exposure_edges":0,
        "crisis_forecast_probability":None,"index_aics":None,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
