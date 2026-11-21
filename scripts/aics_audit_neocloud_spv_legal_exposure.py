#!/usr/bin/env python3
"""AICS audit of 37 research entities and Neocloud/SPV primary-source date gates.

No balances, 0-100 scores, PIT attestation, or OOS are inferred from name
mentions, current IR archives, Telegram images, or signed-contract leads.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from scripts.aics_collect_spv_neocloud_sec import load_registry

UNIVERSE = Path("aics_data/research/aics_extended_company_universe_omi_telegram_2026-11-18.json")
SEC_REGISTRY = Path("aics_data/source_registry/sec_spv_neoclouds_filings_2026-11-18.json")
OUTPUT = Path("aics_data/progress/neocloud_spv_contract_gap_audit_2026-11-18.json")
PRIVATE_LEADS = frozenset({"Crusoe Energy", "Lambda", "Firmus", "SharonAI", "GMI", "Nscale"})
NODES = {
    "Private Credit": 150, "Insurers": 125, "UST 30Y": 125,
    "Neoclouds": 100, "AI Equities": 100, "Hyperscalers": 100,
    "SPV": 100, "Repo": 100, "Power/Data Centers": 50,
    "Semiconductors Supply": 50, "AI Demand": 50,
}
ORIGINS = {"OMI_PDF", "TELEGRAM_SCREENSHOTS_NOT_IN_OMI_PDF"}
assert len(NODES) == 11 and sum(NODES.values()) == 1050


def audit(universe_path: Path = UNIVERSE, sec_path: Path = SEC_REGISTRY,
          as_of: dt.date | None = None) -> dict:
    universe_bytes = universe_path.read_bytes()
    sec_bytes = sec_path.read_bytes()
    universe = json.loads(universe_bytes)
    source_day = dt.date.fromisoformat(universe["source_as_of"])
    if universe.get("schema_version") != "aics-company-universe-research-v1":
        raise ValueError("unexpected company evidence schema")
    as_of = as_of or source_day
    if as_of != source_day:
        raise ValueError("cannot relabel a frozen historical snapshot")
    if as_of > dt.datetime.now(dt.timezone.utc).date():
        raise ValueError("future research snapshot forbidden")
    policy = universe.get("model_policy")
    if not isinstance(policy, dict) or (
        policy.get("fixed_node_count") != 11
        or policy.get("fixed_weights") != NODES
        or policy.get("expanding_entity_universe_does_not_expand_index_weights") is not True
        or policy.get("entity_mention_does_not_prove_contractual_exposure") is not True
        or policy.get("one_economic_exposure_must_not_double_count_across_nodes") is not True
        or policy.get("sec_mandatory_available_at") != "filed_at_plus_14_calendar_days"
        or policy.get("certified_aics") is not None
    ):
        raise ValueError("research universe breaches AICS invariant")

    companies = universe.get("companies")
    if not isinstance(companies, list) or len(companies) != 37:
        raise ValueError("unexpected research universe size")
    seen, origin_counts, node_counts, private_leads = set(), {}, dict.fromkeys(NODES, 0), set()
    for company in companies:
        if not isinstance(company, dict):
            raise ValueError("invalid issuer record")
        name, origin, nodes = company.get("name"), company.get("origin"), company.get("candidate_nodes")
        if (
            not isinstance(name, str) or not name or name in seen
            or origin not in ORIGINS
            or not isinstance(nodes, list) or not nodes
            or len(nodes) != len(set(nodes)) or not set(nodes) <= set(NODES)
            or company.get("confirmed_financial_exposure_usd") is not None
            or company.get("stress_score") is not None
            or company.get("model_eligible") is not False
        ):
            raise ValueError("unverified exposure, duplicate, or invalid company")
        pages = company.get("original_pdf_pages")
        if not isinstance(pages, list) or bool(pages) != (origin == "OMI_PDF"):
            raise ValueError("OMI/Telegram provenance mixing")
        seen.add(name)
        origin_counts[origin] = origin_counts.get(origin, 0) + 1
        for node in nodes:
            node_counts[node] += 1
        if name in PRIVATE_LEADS:
            if ("Neoclouds" not in nodes
                    or company.get("raw_source_status") not in
                    {"secondary_only", "secondary_social_lead_only"}):
                raise ValueError("private company research lead falsely promoted")
            private_leads.add(name)
    if (origin_counts != {"OMI_PDF": 26, "TELEGRAM_SCREENSHOTS_NOT_IN_OMI_PDF": 11}
            or private_leads != PRIVATE_LEADS
            or node_counts["Neoclouds"] != 9 or node_counts["SPV"] != 13):
        raise ValueError("reconciled research company inventory changed")
    relationships = universe.get("reported_relationships")
    if not isinstance(relationships, list) or len(relationships) != 3:
        raise ValueError("unexpected reported project relationships")
    for relationship in relationships:
        if (not isinstance(relationship, dict)
                or relationship.get("score_eligible") is not False
                or relationship.get("legal_entity_ciks_verified") is not False
                or not set(relationship.get("entities", ())) <= seen):
            raise ValueError("secondary project relationship promoted or unknown")

    sec = load_registry(sec_path)
    if sec.get("as_of") != as_of.isoformat():
        raise ValueError("SEC date-registry mismatch")
    eligible, embargoed, sec_rows = 0, 0, []
    for doc in sec["documents"]:
        available = dt.date.fromisoformat(doc["available_at"])
        date_gate = "DATE_ELIGIBLE_NOT_RETRIEVAL_OR_PIT_PROOF" if available <= as_of else "EMBARGOED_SEC_PLUS_14_DAYS"
        eligible += available <= as_of
        embargoed += available > as_of
        sec_rows.append({
            "source_id": doc["source_id"], "issuer": doc["issuer"],
            "form": doc["form"], "filed_at": doc["filed_at"],
            "available_at": doc["available_at"], "date_gate": date_gate,
            "candidate_nodes": doc["candidate_nodes"],
            "original_bytes_verified_in_this_audit": False,
            "drawn_debt_usd": None, "recourse_proven": False, "score_eligible": False,
        })
    if (len(sec_rows) != 5 or eligible != 4 or embargoed != 1
            or not any(r["source_id"] == "CRWV_10Q_20261112"
                       and r["available_at"] == "2026-11-26"
                       and r["date_gate"] == "EMBARGOED_SEC_PLUS_14_DAYS"
                       for r in sec_rows)):
        raise ValueError("SEC coverage or embargo changed")
    return {
        "schema_version": "aics-neocloud-spv-contract-gap-audit-v1",
        "as_of": as_of.isoformat(),
        "source_universe_sha256": hashlib.sha256(universe_bytes).hexdigest(),
        "sec_registry_sha256": hashlib.sha256(sec_bytes).hexdigest(),
        "research_company_count": 37,
        "omi_named_count": 26, "telegram_only_count": 11,
        "candidate_memberships_by_node": node_counts,
        "neocloud_company_candidates": 9, "spv_company_candidates": 13,
        "private_neocloud_contract_leads": sorted(private_leads),
        "original_private_contracts_confirmed": 0,
        "sec_registry_docs": len(sec_rows), "sec_date_eligible_docs": eligible,
        "sec_embargoed_docs": embargoed, "sec_documents": sec_rows,
        "independently_verified_spv_legal_recourse_contracts": 0,
        "numeric_contractual_exposure_usd": None,
        "node_stress_scores": dict.fromkeys(NODES),
        "index_aics": None, "predictive_skill_score": None,
        "independently_attested_pit": False, "untouched_24m_oos": False,
        "promotion": "BLOCKED", "trades_created": False,
        "limitations": [
            "Date eligibility is not original filing download or independently verified PIT.",
            "Node memberships overlap: 9 Neocloud and 13 SPV are NOT 22 additive claims.",
            "Current IR, OMI and Telegram cannot establish signed contracts, drawn debt or recourse.",
            "Unconfirmed facility principal, guarantees, lease and equity commitments must not be added.",
            "No 0-100 score, independent OOS, or investment signal is produced."
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    data = audit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "companies": data["research_company_count"],
        "neocloud_candidates": data["neocloud_company_candidates"],
        "spv_candidates": data["spv_company_candidates"],
        "sec_date_eligible": data["sec_date_eligible_docs"],
        "sec_embargoed": data["sec_embargoed_docs"],
        "index_aics": None, "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
