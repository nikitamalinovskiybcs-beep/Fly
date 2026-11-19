#!/usr/bin/env python3
"""Reproduce *historical* Nscale debt draw and carrying facts from genuine SEC S-1.

A single retrospectively captured September 18 2026 original is rehashed from
the prior Ward evidence archive. Reporting dates (2025/2026) are NOT AICS
availability: the original SEC filing only passes the +14 day gate 2026-10-02.
Three economically different figures must never be summed into a SPV stress
score or contemporaneous 2026-11 outstanding balance.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from scripts.aics_audit_nscale_dfs_s1 import (
    EXHIBIT_BYTES, EXHIBIT_SHA, S1_SOURCE_ID,
    audit as verify_original_sec_s1,
)
from scripts.aics_collect_nscale_ward_sec import AVAILABLE, SourceError, html_text

SOURCE_DIR = Path("aics_data/source_evidence/nscale_ward_primary")
OUTPUT = Path("aics_data/source_evidence/nscale_drawn_debt_s1_research.json")
GPU_START = "GPU Credit Agreement On February 11, 2026, Nscale Services UK Ltd"
MACQUARIE_START = (
    "Macquarie Senior Facility In June 2025, "
    "Nscale Global Holdings Limited as Borrower"
)
GPU_CURRENT_DISCLOSURE = (
    "As of March 31, 2026, approximately $58.9 million of term loans "
    "have been drawn and are outstanding and approximately $1.4 billion "
    "of delayed draw term commitments available for borrowing"
)
MACQUARIE_LIMIT_DISCLOSURE = (
    "entered into a senior facility agreement with Macquarie, providing "
    "for an aggregate $105.0 million facility comprised of a term loan "
    "facility and a letter of credit facility"
)
MACQUARIE_FIRST_DRAW = (
    "The first utilization against the facility of $70.1 million "
    "was drawn on August 1, 2025."
)
MACQUARIE_SECOND_DRAW = (
    "The remaining $34.9 million was drawn on January 30, 2026."
)
GROUP_CARRYING_DISCLOSURE = (
    "As of June 30, 2026, the carrying value of our total debt "
    "was $137.4 million."
)

def parse_reporting_facts(original_html: bytes) -> dict:
    """Reject unrelated, duplicate, relabeled or altered disclosure text."""
    text = html_text(original_html)
    if text.count(GPU_START) != 1 or text.count(MACQUARIE_START) != 1:
        raise SourceError("Missing or duplicated exact borrower credit-section identity")
    gpu_at = text.index(GPU_START)
    mac_at = text.index(MACQUARIE_START)
    if not (gpu_at < mac_at <= gpu_at + 5_000):
        raise SourceError("GPU credit and Macquarie facilities conflated")
    gpu = text[gpu_at:mac_at]
    macquarie = text[mac_at:mac_at + 1900]
    if gpu.count(GPU_CURRENT_DISCLOSURE) != 1:
        raise SourceError("GPU initial-borrower reported drawn-and-outstanding fact changed")
    if (macquarie.count(MACQUARIE_LIMIT_DISCLOSURE) != 1
            or macquarie.count(MACQUARIE_FIRST_DRAW) != 1
            or macquarie.count(MACQUARIE_SECOND_DRAW) != 1):
        raise SourceError("Macquarie original separate funding and utilization facts changed")
    if text.count(GROUP_CARRYING_DISCLOSURE) != 1:
        raise SourceError("Consolidated debt carrying amount changed or duplicated")
    first_draw, second_draw = 70_100_000, 34_900_000
    if first_draw + second_draw != 105_000_000:
        raise SourceError("Macquarie historical utilization arithmetic mismatch")
    return {
        "gpu_financing_facility": {
            "borrower": "Nscale Services UK Ltd",
            "loan_class": "GPU Financing Facility; distinct from Ward and NC borrower agreements",
            "observation_as_of": "2026-03-31",
            "drawn_and_outstanding_term_loans_usd_approx": 58_900_000,
            "delayed_draw_commitments_available_usd_approx": 1_400_000_000,
            "outstanding_on_review_date_usd": None,
        },
        "macquarie_senior_facility": {
            "borrower": "Nscale Global Holdings Limited",
            "lender": "Macquarie Bank Limited",
            "facility_total_usd": 105_000_000,
            "comprised_of_term_loan_and_letter_of_credit": True,
            "first_utilization": {"date": "2025-08-01", "usd": first_draw},
            "second_utilization": {"date": "2026-01-30", "usd": second_draw},
            "historical_utilizations_sum_usd": first_draw + second_draw,
            "outstanding_on_review_date_usd": None,
        },
        "consolidated_nscale_debt": {
            "observation_as_of": "2026-06-30",
            "gaap_total_debt_carrying_value_usd": 137_400_000,
            "current_2026_11_balance_usd": None,
        },
    }


def audit(directory: Path, as_of: dt.date = dt.date(2026, 11, 19)) -> dict:
    if as_of < AVAILABLE:
        raise SourceError("SEC +14 day embargo has not elapsed")
    verified = verify_original_sec_s1(directory, as_of=as_of)
    if (verified.get("source_sec_original_sha256") != EXHIBIT_SHA
            or verified.get("source_sec_original_bytes") != EXHIBIT_BYTES
            or verified.get("source_sec_filed_at") != "2026-09-18"
            or verified.get("source_sec_available_at") != "2026-10-02"
            or verified.get("independent_historical_pit_attested") is not False
            or verified.get("promotion") != "BLOCKED"
            or verified.get("index_aics") is not None):
        raise SourceError("Original Nscale S-1 identity, PIT or promotion changed")
    manifest = json.loads((directory / "manifest.json").read_bytes())
    sources = [row for row in manifest["source_receipts"]
               if row["source_id"] == S1_SOURCE_ID]
    if len(sources) != 1:
        raise SourceError("Nscale S-1 archived primary original missing or duplicated")
    raw = Path(sources[0]["raw_path"]).read_bytes()
    if len(raw) != EXHIBIT_BYTES or hashlib.sha256(raw).hexdigest() != EXHIBIT_SHA:
        raise SourceError("Nscale S-1 original bytes changed")
    facts = parse_reporting_facts(raw)
    return {
        "schema_version": "aics-nscale-original-s1-three-debt-reporting-facts-v1",
        "research_as_of": as_of.isoformat(),
        "issuer_cik": "2110365",
        "sec_accession": "0001193125-26-395475",
        "sec_filed_at": "2026-09-18",
        "sec_available_at": "2026-10-02",
        "original_s1_html_sha256": EXHIBIT_SHA,
        "original_s1_html_bytes": EXHIBIT_BYTES,
        "independent_current_rehash_of_original_s1": True,
        "disclosure_facts": facts,
        "ward_county_gpu_facility_drawn_principal_usd": None,
        "north_carolina_gpu_facility_drawn_principal_usd": None,
        "total_2026_11_spv_outstanding_usd": None,
        "cross_facility_additive_amount_usd": None,
        "three_facts_are_independent_current_borrower_balances": False,
        "reporting_dates_are_not_sec_available_at": True,
        "independent_historical_pit_attested": False,
        "untouched_24_month_oos": False,
        "synthetic_historical_observations": 0,
        "spv_node_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
        "trades_created": False,
        "limitations": [
            "March 31 2026 GPU draw pertains to Nscale Services UK Ltd, not the two Ward/NC SPVs.",
            "Macquarie $70.1m and $34.9m are two historical utilizations, not a current debt balance; outstanding principal may amortize.",
            "June 30 2026 $137.4m is consolidated debt carrying value, not an additive facility cash flow.",
            "All observed figures are visible to AICS no earlier than October 2 2026, 14 days after the original S-1 filing.",
            "No independent archive of September release-time delivery, current drawn balances, verified SPV scoring, or untouched 24m OOS.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--directory", type=Path, default=SOURCE_DIR)
    p.add_argument("--as-of", type=dt.date.fromisoformat,
                   default=dt.date(2026, 11, 19))
    p.add_argument("--out", type=Path, default=OUTPUT)
    a = p.parse_args()
    try:
        x = audit(a.directory, a.as_of)
    except (OSError, TypeError, ValueError, KeyError) as exc:
        print(json.dumps({"promotion": "BLOCKED", "reason": type(exc).__name__}))
        return 2
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(x, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    print(json.dumps({
        "gpu_march_2026_drawn_usd_approx": 58_900_000,
        "macquarie_historical_utilizations_usd": 105_000_000,
        "group_june_2026_debt_carrying_value_usd": 137_400_000,
        "ward_nc_current_drawn_principal_usd": None,
        "index_aics": None,
        "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
