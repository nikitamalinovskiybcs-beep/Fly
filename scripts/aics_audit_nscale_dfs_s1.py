#!/usr/bin/env python3
"""Evidence-only Dell Financial Services rent/guaranty review from original Nscale S-1.

The 40 executed payment schedules and initial-term rent are not funded GPU
credit-facility principal. The two borrower legal entities appear in both
instruments; adding the numbers would falsely double-count economic exposure.
This original HTML replay does NOT establish historic independent PIT or AICS.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from scripts.aics_collect_nscale_ward_sec import (
    AVAILABLE, SourceError, html_text, verify_archive,
)

FROZEN_RECEIPT = Path(
    "aics_data/research/nscale_ward_original_sec_independent_rehash_2026-11-19.json"
)
SOURCE_DIR = Path("aics_data/source_evidence/nscale_ward_primary")
OUTPUT = Path("aics_data/source_evidence/nscale_dfs_research.json")
S1_SOURCE_ID = "nscale_s1_narrative"
EXHIBIT_SHA = "82ca06374fb97f55f66e334679103e8153b9686a44a86dae425ab0bfc1074020"
EXHIBIT_BYTES = 7_958_866
SECTION_START = (
    "Dell Vendor Financing In April 2026, "
    "Nscale Ward County Borrower SPV, LLC and Nscale NC Borrower SPV, LLC"
)
SECTION_END = " GPU Credit Agreement On February 11, 2026"
REQUIRED_PHRASES = (
    "entered into two DFS Framework Agreements with DFS, as the funder",
    "On April 18, 2026, Nscale Global Holdings Ltd as guarantor entered into "
    "a corporate guaranty in favor of DFS, guaranteeing all obligations of "
    "the Customers under the DFS Framework Agreements.",
    "As of September 4, 2026, we have entered into 40 payment schedules, "
    "of which 40 have been fully executed, incurring an aggregate initial-term "
    "rent of approximately $2.54 billion, including combined financing "
    "charges of approximately $34.8 million.",
    "Each Customer has granted DFS a security interest in the Products "
    "and all related proceeds.",
)


def extract_terms(original_html: bytes) -> dict:
    """Parse exact narrative disclosures; no estimation of outstanding debt."""
    plain = html_text(original_html)
    if plain.count(SECTION_START) != 1:
        raise SourceError("Missing or ambiguous signed DFS financing section")
    start = plain.index(SECTION_START)
    end = plain.find(SECTION_END, start)
    if end < 0 or end - start > 3_500:
        raise SourceError("DFS section not securely bounded")
    section = plain[start:end]
    if any(phrase not in section for phrase in REQUIRED_PHRASES):
        raise SourceError("DFS original guarantee, schedules or financing terms changed")
    return {
        "borrower_legal_entities": [
            "Nscale Ward County Borrower SPV, LLC",
            "Nscale NC Borrower SPV, LLC",
        ],
        "funder": "Dell Financial Services L.L.C.",
        "guarantor": "Nscale Global Holdings Ltd",
        "guaranty_scope": "all obligations under DFS Framework Agreements",
        "as_reported_at": "2026-09-04",
        "framework_agreements": 2,
        "payment_schedules_executed": 40,
        "aggregate_initial_term_rent_usd_approx": 2_540_000_000,
        "included_financing_charges_usd_approx": 34_800_000,
        "lender_security_interest_in_equipment_described": True,
    }


def audit(directory: Path, as_of: dt.date = dt.date(2026, 11, 19),
          frozen_receipt: Path = FROZEN_RECEIPT) -> dict:
    if as_of < AVAILABLE:
        raise SourceError("SEC +14 days not yet elapsed")
    manifest = json.loads((directory / "manifest.json").read_bytes())
    verify_archive(directory, manifest)
    pin = json.loads(frozen_receipt.read_bytes())
    expected = {
        "schema_version": "aics-nscale-ward-original-sec-zip-independent-rehash-v1",
        "sec_accession": "0001193125-26-395475",
        "sec_filed_at": "2026-09-18",
        "sec_available_at": "2026-10-02",
        "source_artifact_id": 14505066061,
        "raw_original_html_independently_rehashed_outside_actions": 2,
        "promotion": "BLOCKED",
        "index_aics": None,
        "independent_historical_provider_pit_attestation": False,
    }
    if any(pin.get(k) != v for k, v in expected.items()):
        raise SourceError("Frozen original SEC source receipt changed")
    pinned = [r for r in pin.get("source_originals", ())
              if r.get("source_id") == S1_SOURCE_ID]
    rows = [r for r in manifest.get("source_receipts", ())
            if r.get("source_id") == S1_SOURCE_ID]
    if len(pinned) != 1 or len(rows) != 1:
        raise SourceError("Unique archived Nscale S-1 original required")
    source, row = pinned[0], rows[0]
    if (source.get("sha256") != EXHIBIT_SHA
            or source.get("bytes") != EXHIBIT_BYTES
            or row.get("sha256") != EXHIBIT_SHA
            or row.get("bytes") != EXHIBIT_BYTES
            or source.get("url") != row.get("source_url")
            or row.get("available_at") != "2026-10-02"):
        raise SourceError("Pinned SEC original does not match downloaded HTML receipt")
    raw = Path(row["raw_path"]).read_bytes()
    if (len(raw) != EXHIBIT_BYTES
            or hashlib.sha256(raw).hexdigest() != EXHIBIT_SHA):
        raise SourceError("Original Nscale S-1 bytes have changed")
    terms = extract_terms(raw)
    return {
        "schema_version": "aics-nscale-dfs-original-s1-legal-observations-v1",
        "research_as_of": as_of.isoformat(),
        "source_sec_accession": expected["sec_accession"],
        "source_sec_original_sha256": EXHIBIT_SHA,
        "source_sec_original_bytes": EXHIBIT_BYTES,
        "source_sec_filed_at": expected["sec_filed_at"],
        "source_sec_available_at": expected["sec_available_at"],
        "original_html_rehashed_in_this_audit": True,
        **terms,
        "financing_instrument": "equipment lease financing / DFS payment schedules",
        "gpu_loan_commitment_ceilings_usd": {
            "north_carolina": 1_200_000_000,
            "ward_county": 1_850_000_000,
        },
        "parent_guaranty_enforceable_amount_usd": None,
        "dfs_actual_paid_rent_usd": None,
        "dfs_current_lease_liability_usd": None,
        "gpu_facility_actual_drawn_principal_usd": None,
        "gpu_and_dfs_exposures_safe_to_add": False,
        "cross_instrument_total_exposure_usd": None,
        "independent_historical_pit_attested": False,
        "independent_24month_oos": False,
        "synthetic_rows": 0,
        "spv_node_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
        "trades_created": False,
        "limitations": [
            "Forty payment schedules and the approximate rent are original reported "
            "contract facts, not a cash-paid balance or current outstanding lease liability.",
            "The same borrower entities also signed GPU loan facilities. Lease rent and "
            "GPU commitments cannot be added as independent debt exposures.",
            "The DFS guarantor Nscale Global Holdings Ltd is not interchangeable with "
            "Nscale Limited's limited support for the Ward GPU credit facility.",
            "Retrospectively rehashed SEC original cannot certify historical market-data PIT.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=SOURCE_DIR)
    parser.add_argument("--receipt", type=Path, default=FROZEN_RECEIPT)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    a = parser.parse_args()
    try:
        data = audit(a.directory, frozen_receipt=a.receipt)
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        print(json.dumps({"promotion": "BLOCKED", "error": type(exc).__name__}))
        return 2
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    print(json.dumps({
        "fully_executed_schedules": data["payment_schedules_executed"],
        "approx_initial_term_rent_usd": data["aggregate_initial_term_rent_usd_approx"],
        "actual_drawn_principal_usd": None, "index_aics": None,
        "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
