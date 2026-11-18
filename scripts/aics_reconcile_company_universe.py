#!/usr/bin/env python3
"""Reconcile the 37-company OMI/Telegram research universe without score leakage.

All entities and relationships remain research leads. A mention, IR archive,
social-media screenshot, or reported contract amount is not a verified exposure.
This program intentionally performs NO dollar aggregation or AICS calculation.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from scripts.aics_progress_dashboard import WEIGHTS

REGISTRY = Path("aics_data/research/aics_extended_company_universe_omi_telegram_2026-11-18.json")
STATUS = Path("aics_data/progress/status.json")
OMI = "OMI_PDF"
TELEGRAM = "TELEGRAM_SCREENSHOTS_NOT_IN_OMI_PDF"
PDF_SHA256 = "466b8a875752c85e23a41d5e33ad985c44f437ddc5cf801e132310c4e28bff60"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def audit(data: dict, status: dict) -> dict:
    """Fail closed if research-only provenance or the no-promotion gate changes."""
    require(isinstance(data, dict) and isinstance(status, dict), "invalid input")
    require(data.get("schema_version") == "aics-company-universe-research-v1",
            "unexpected universe schema")
    require(data.get("source_as_of") == status.get("as_of"), "as-of mismatch")
    pdf = data.get("source_pdf", {})
    require(isinstance(pdf, dict) and pdf.get("sha256") == PDF_SHA256
            and pdf.get("source_type") == "SECONDARY_POLICY_RESEARCH",
            "OMI secondary PDF provenance changed")
    policy = data.get("model_policy", {})
    require(isinstance(policy, dict) and policy.get("fixed_weights") == WEIGHTS
            and policy.get("fixed_node_count") == 11
            and sum(WEIGHTS.values()) == 1050, "model constants changed")
    for flag in ("expanding_entity_universe_does_not_expand_index_weights",
                 "entity_mention_does_not_prove_contractual_exposure",
                 "one_economic_exposure_must_not_double_count_across_nodes",
                 "unverified_issuer_lagged_inputs_excluded"):
        require(policy.get(flag) is True, "risk research protection removed: " + flag)
    require(policy.get("sec_mandatory_available_at") == "filed_at_plus_14_calendar_days",
            "SEC PIT embargo changed")
    require(policy.get("progress_milestone_from_name_discovery") == 0
            and policy.get("independently_validated_model_scores") == 0
            and policy.get("all_new_company_scores") is None
            and policy.get("certified_aics") is None,
            "company mention incorrectly promoted")
    require(data.get("status") == "CANDIDATE_UNIVERSE_NOT_MODEL_PROMOTION",
            "universe status must remain research only")

    companies = data.get("companies")
    require(isinstance(companies, list) and len(companies) == 37,
            "expected exactly 37 recorded candidates")
    by_name = {}
    names_casefold = set()
    by_node = {node: {"omi_pdf_mentions": [], "telegram_only_leads": [],
                      "issuer_ir_archived_not_pit": []} for node in WEIGHTS}
    for c in companies:
        require(isinstance(c, dict), "invalid company")
        name, origin, nodes = c.get("name"), c.get("origin"), c.get("candidate_nodes")
        require(isinstance(name, str) and name.strip()
                and name.casefold() not in names_casefold, "duplicate/invalid company")
        require(origin in (OMI, TELEGRAM), "unsupported company provenance")
        require(isinstance(nodes, list) and bool(nodes)
                and len(nodes) == len(set(nodes))
                and set(nodes) <= set(WEIGHTS), "invalid node mapping")
        require(c.get("stress_score") is None
                and c.get("confirmed_financial_exposure_usd") is None
                and c.get("model_eligible") is False,
                "unverified company exposure promoted")
        pages = c.get("original_pdf_pages")
        require(isinstance(pages, list), "missing PDF page lineage")
        if origin == OMI:
            require(bool(pages) and all(type(p) is int and 1 <= p <= 88 for p in pages),
                    "OMI mention missing valid physical PDF page")
            require(c.get("raw_source_status") in ("secondary_only", "issuer_ir_archived"),
                    "OMI company has unapproved evidence label")
        else:
            require(pages == [] and c.get("raw_source_status") == "secondary_social_lead_only"
                    and isinstance(c.get("telegram_image_ids"), list)
                    and bool(c["telegram_image_ids"])
                    and all(isinstance(i, str) and i.endswith(".jpg")
                            for i in c["telegram_image_ids"]),
                    "Telegram-only lead disguised as PDF or primary record")
        names_casefold.add(name.casefold())
        by_name[name] = c
        for node in nodes:
            key = "omi_pdf_mentions" if origin == OMI else "telegram_only_leads"
            by_node[node][key].append(name)
            if c.get("raw_source_status") == "issuer_ir_archived":
                by_node[node]["issuer_ir_archived_not_pit"].append(name)

    counts = Counter(c["origin"] for c in companies)
    require(counts == {OMI: 26, TELEGRAM: 11}, "26/11 source split changed")
    recorded = data.get("collections", {})
    require(isinstance(recorded, dict)
            and recorded.get("company_count") == 37
            and recorded.get("pdf_named_count") == 26
            and recorded.get("telegram_only_count") == 11, "source totals inconsistent")

    relationships = data.get("reported_relationships")
    require(isinstance(relationships, list) and len(relationships) == 3,
            "expected three separate reported project groups")
    seen_projects = set()
    projects = []
    for rel in relationships:
        require(isinstance(rel, dict), "invalid project relationship")
        project = rel.get("project")
        entities = rel.get("entities")
        require(isinstance(project, str) and project
                and project not in seen_projects, "duplicate/invalid project")
        require(isinstance(entities, list) and entities
                and len(set(entities)) == len(entities)
                and set(entities) <= set(by_name), "relationship has unknown entities")
        require(rel.get("score_eligible") is False
                and rel.get("legal_entity_ciks_verified") is False,
                "unverified project relationship promoted")
        src = rel.get("source_status")
        require(src in ("OMI_PDF_SECONDARY_NOT_CONTRACT_ATTESTED", TELEGRAM),
                "project source status not approved")
        pages = rel.get("paper_pages")
        require(isinstance(pages, list)
                and ((bool(pages) and all(type(p) is int and 1 <= p <= 88 for p in pages))
                     if src != TELEGRAM else pages == []),
                "invalid relationship PDF provenance")
        terms = rel.get("reported_terms")
        require(isinstance(terms, list), "reported terms missing")
        for term in terms:
            require(isinstance(term, dict)
                    and "secondary_report" in str(term.get("kind", ""))
                    and term.get("unit") == "USD billion", "primary amount falsely inferred")
        seen_projects.add(project)
        projects.append({"project": project, "source_status": src,
                         "named_counterparties": sorted(entities),
                         "original_contract_attested": False,
                         "verified_drawn_exposure_usd": None,
                         "score_eligible": False})

    require(status.get("total_nodes") == 11 and status.get("total_weight") == 1050,
            "status/model weights inconsistent")
    require(status.get("independently_certified_nodes") == 0
            and status.get("source_pit_attested_nodes") == 0
            and status.get("index_aics") is None
            and status.get("promotion") == "BLOCKED", "status cannot certify this research")
    rows = status.get("node_progress")
    require(isinstance(rows, list) and len(rows) == 11
            and {r["node"]: r["weight"] for r in rows} == WEIGHTS,
            "status node mapping changed")
    require(all(r.get("node_stress_score") is None
                and r.get("independently_certified") is False for r in rows),
            "a research-only node was promoted")
    for node in by_node:
        for field in by_node[node]:
            by_node[node][field].sort()
    return {
        "schema_version": "aics-company-source-reconciliation-v1",
        "as_of": status["as_of"],
        "scope": "SECONDARY_SOURCE_CANDIDATE_MAPPING_NOT_HISTORICAL_PIT",
        "nodes": by_node,
        "counts": {"all_candidates": 37, "omi_pdf_named": 26,
                   "telegram_only": 11, "separate_project_groups": len(projects)},
        "projects": projects,
        "milestones_added": 0,
        "independently_certified_nodes": 0,
        "node_stress_scores": None,
        "index_aics": None,
        "aggregated_exposure_usd": None,
        "promotion": "BLOCKED",
        "required_next_evidence": [
            "Original dated contracts with identified borrower, lender, guarantor and recourse",
            "Drawn balances and reporting dates separate from undrawn facility limits",
            "Independent filed-at plus 14-day SEC PIT and ALFRED vintage checks",
            "Untouched historical constituents, corporate actions and 24-month OOS",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", type=Path, default=REGISTRY)
    p.add_argument("--status", type=Path, default=STATUS)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    result = audit(json.loads(args.registry.read_text(encoding="utf-8")),
                   json.loads(args.status.read_text(encoding="utf-8")))
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
        print(json.dumps({"candidates": 37, "projects": 3,
                          "milestones_added": 0, "index_aics": None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
