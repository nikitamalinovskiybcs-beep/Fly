#!/usr/bin/env python3
"""Reproduce two CoreWeave SPV facility debt balances and distinct recourse terms.

The original 2026-06-30 SEC 10-Q is rehashed and matched to its accession and
specific SEC <DOCUMENT> bytes before extracting the debt table and legal text.
All outputs are date-scoped research only, NOT live drawn principal, quantified
parent-loss exposure, historical PIT attestation, a stress score or AICS.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path

from scripts.aics_neocloud_cash_coverage import facility_rows, source_documents
from scripts.aics_observed_source_review import words

REGISTRY = Path("aics_data/source_registry/neocloud_cash_h1_sec.json")
CROSS_CHECK = Path("aics_data/research/neocloud_cash_coverage_2026_h1.json")
OUT = Path("aics_data/source_evidence/coreweave_two_spv_facility_debt.json")
SOURCE = "crwv_26_h1"
CUTOFF = date(2026, 11, 18)
EXPECTED_FACILITIES = {
    "DDTL 4.0": ("CoreWeave Compute Acquisition Co. VIII, LLC",
                 "Non-recourse except for customary limited guarantees"),
    "DDTL 5.0": ("CoreWeave Financing DDTL V, LLC",
                 "Unconditional parent guarantee"),
}

def _rate(balance: int, ceiling: int) -> str:
    if type(balance) is not int or type(ceiling) is not int or not 0 <= balance <= ceiling:
        raise ValueError("Debt balance or facility amount invalid")
    return str((Decimal(balance) * 100 / Decimal(ceiling))
               .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def reconcile(facilities: list[dict], checked: dict, source: dict) -> dict:
    """One row per entity; identify amounts without implying unconditional recourse."""
    if (not isinstance(facilities, list) or len(facilities) != 2
            or not isinstance(checked, dict) or not isinstance(source, dict)):
        raise ValueError("Missing original facility and independent research cross-check")
    issued = source.get("filed_at")
    available = source.get("available_at")
    if (issued != "2026-08-12" or available != "2026-08-26"
            or date.fromisoformat(available) != date.fromisoformat(issued) + timedelta(days=14)
            or source.get("cik") != "1769628"
            or source.get("accession") != "0001769628-26-000366"
            or source.get("form") != "10-Q"
            or source.get("document_type") != "10-Q"):
        raise ValueError("Original SEC chronology/issuer accession changed")
    if (checked.get("source_cutoff") != CUTOFF.isoformat()
            or checked.get("coreweave_facilities", {}).get("as_of") != "2026-06-30"
            or checked["coreweave_facilities"].get("available_at") != available
            or checked["coreweave_facilities"].get("source") != SOURCE
            or checked.get("node_score") is not None
            or checked.get("index_aics") is not None
            or checked.get("production_weights_changed") is not False
            or checked.get("trades_created") is not False):
        raise ValueError("Research cross-check date or model status changed")
    entries = checked["coreweave_facilities"].get("facilities")
    if not isinstance(entries, list) or entries != facilities:
        raise ValueError("Original SEC 10-Q debt and committed research differ")
    if {e.get("facility") for e in facilities} != set(EXPECTED_FACILITIES):
        raise ValueError("Missing, duplicate or substituted DDTL agreement")
    verified = []
    for entry in facilities:
        name = entry["facility"]
        borrower, recourse = EXPECTED_FACILITIES[name]
        if (entry.get("borrower") != borrower or entry.get("recourse") != recourse
                or type(entry.get("reported_debt_usd_m")) is not int
                or type(entry.get("facility_ceiling_usd_m")) is not int
                or not 0 < entry["reported_debt_usd_m"] <= entry["facility_ceiling_usd_m"]):
            raise ValueError("SEC facility borrower, recourse or reported balance changed")
        verified.append({
            **entry,
            "balance_to_ceiling_pct": _rate(
                entry["reported_debt_usd_m"], entry["facility_ceiling_usd_m"]),
            "is_outstanding_balance_as_of_2026_06_30": True,
            "exact_cash_drawn_usd_m": None,
            "enforceable_parent_guarantee_exposure_usd_m": None,
        })
    verified.sort(key=lambda r: r["facility"])
    total_balance = sum(r["reported_debt_usd_m"] for r in verified)
    total_ceiling = sum(r["facility_ceiling_usd_m"] for r in verified)
    if (total_balance != 3938 or total_ceiling != 11600
            or verified[0]["reported_debt_usd_m"] != 2837
            or verified[1]["reported_debt_usd_m"] != 1101
            or verified[0]["facility_ceiling_usd_m"] != 8500
            or verified[1]["facility_ceiling_usd_m"] != 3100):
        raise ValueError("Actual SEC 10-Q facility balances differ from reviewed record")
    return {
        "schema_version": "aics-coreweave-spv-dated-two-facility-recourse-review-v1",
        "node_candidates": ["SPV", "Neoclouds"],
        "issuer": "CoreWeave",
        "issuer_cik": source["cik"],
        "sec_form": source["form"],
        "sec_accession": source["accession"],
        "sec_original_submission_url": source["original"]["url"],
        "sec_original_sha256": source["original"]["sha256"],
        "sec_original_bytes": source["original"]["bytes"],
        "sec_embedded_document_sha256": source["document_text_sha256"],
        "filed_at": issued,
        "sec_available_at": available,
        "economic_balance_as_of": "2026-06-30",
        "amount_unit": "USD million",
        "facilities": verified,
        "two_distinct_contract_reported_debt_usd_m": total_balance,
        "two_distinct_contract_ceiling_usd_m": total_ceiling,
        "two_contract_balance_to_ceiling_pct": _rate(total_balance, total_ceiling),
        "nonrecourse_with_limited_exceptions_reported_debt_usd_m": verified[0]["reported_debt_usd_m"],
        "unconditional_parent_guaranteed_facility_reported_debt_usd_m": verified[1]["reported_debt_usd_m"],
        "consolidated_gaap_debt_usd_m": None,
        "effective_economic_parent_recourse_usd_m": None,
        "cash_drawn_2026_11_usd_m": None,
        "remaining_undrawn_borrowing_capacity_usd_m": None,
        "separately_reported_nscale_group_fundings_are_additive": False,
        "independent_historical_pit_attested": False,
        "heldout_24_month_oos": False,
        "source_original_bytes_rehashed_in_pipeline": True,
        "historical_period_backdated_as_source_available": False,
        "synthetic_market_observations": 0,
        "spv_node_score": None,
        "neoclouds_node_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
        "trades_created": False,
        "limitations": [
            "These are two reported contract debt balances as of June 30, 2026, not exact lifetime disbursements or debt on November 19.",
            "A sum of two distinct balances within CoreWeave's same-date debt table does not equal a parent recourse or loss amount.",
            "DDTL 4.0 includes customary non-recourse carve-out guarantees; DDTL 5.0 is unconditionally guaranteed by CoreWeave.",
            "Debt balance divided by contractual ceiling is a research ratio, not verified undrawn availability.",
            "SEC original re-download plus SEC+14 conservative availability does not prove contemporaneous provider delivery or independent PIT/OOS.",
        ],
    }

def audit(originals: Path, *, fetch: bool = False) -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    docs = source_documents(registry, (SOURCE,), originals, fetch)
    debt = facility_rows(docs[SOURCE])
    comparison = json.loads(CROSS_CHECK.read_text(encoding="utf-8"))
    return reconcile(debt, comparison, registry[SOURCE])

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--originals", type=Path, required=True)
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    try:
        result = audit(args.originals, fetch=args.fetch)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": type(exc).__name__}))
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(json.dumps({
        "two_facility_reported_debt_usd_m": result["two_distinct_contract_reported_debt_usd_m"],
        "unconditional_parent_guaranteed_facility_reported_debt_usd_m":
            result["unconditional_parent_guaranteed_facility_reported_debt_usd_m"],
        "spv_node_score": None, "index_aics": None, "promotion": "BLOCKED",
    }))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
