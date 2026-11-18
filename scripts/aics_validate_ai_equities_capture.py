#!/usr/bin/env python3
"""Rehash an observed Nasdaq capture without asserting historical market PIT.

This validates downloaded bytes and the time of the *capture*. A historical
quote response is mutable, so the original economic date is NOT proof the
price, constituent universe, or corporate-action adjustment existed then.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from scripts.aics_collect_ai_equities_prices import (
    RESEARCH_SYMBOLS,
    quote_url,
    validate_price_response,
)


def audit_capture(output_dir: Path) -> dict:
    root = output_dir.resolve()
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    capture = dt.datetime.fromisoformat(manifest["retrieved_at_utc"])
    if capture.tzinfo is None or capture.utcoffset() is None:
        raise ValueError("Capture clock must be timezone-aware")
    capture_day = capture.astimezone(dt.timezone.utc).date()
    if manifest.get("schema_version") != "aics-ai-equities-price-capture-v1":
        raise ValueError("Unexpected Nasdaq archive schema")
    # Current-capture receipts cannot be relabeled as older observation dates.
    if manifest.get("requested_as_of") != capture_day.isoformat():
        raise ValueError("Backdated or future-labeled capture")
    if (manifest.get("candidate_node") != "AI Equities"
            or manifest.get("research_only_universe") != list(RESEARCH_SYMBOLS)
            or manifest.get("attempted") != len(RESEARCH_SYMBOLS)
            or manifest.get("archive_candidates") != len(RESEARCH_SYMBOLS)):
        raise ValueError("Incomplete prospective candidate universe")
    if (manifest.get("independently_verified_pit") is not False
            or manifest.get("historical_membership_attested") is not False
            or manifest.get("price_adjustments_as_of_historical_date_attested") is not False
            or manifest.get("node_stress_score") is not None
            or manifest.get("index_aics") is not None
            or manifest.get("predictive_skill_score") is not None
            or manifest.get("promotion") != "BLOCKED"
            or manifest.get("trades_created") is not False):
        raise ValueError("Unsupported market PIT / score promotion")
    rows = manifest.get("sources")
    if not isinstance(rows, list) or len(rows) != len(RESEARCH_SYMBOLS):
        raise ValueError("Missing Nasdaq source records")
    receipt_rows = []
    seen = set()
    for row in rows:
        symbol = row.get("symbol")
        if symbol not in RESEARCH_SYMBOLS or symbol in seen:
            raise ValueError("Duplicate or unapproved Nasdaq symbol")
        seen.add(symbol)
        if (row.get("status") != "raw_candidate_archived_not_pit"
                or row.get("requested_as_of") != capture_day.isoformat()
                or row.get("retrieved_at_utc") != manifest["retrieved_at_utc"]
                or row.get("independently_attested_pit") is not False
                or row.get("score_eligible") is not False):
            raise ValueError("Untrusted source or capture metadata")
        original_url = row.get("requested_url", "")
        query = parse_qs(urlsplit(original_url).query, strict_parsing=True)
        if len(query.get("fromdate", [])) != 1 or len(query.get("todate", [])) != 1:
            raise ValueError("Missing price request boundaries")
        start = dt.date.fromisoformat(query["fromdate"][0])
        end = dt.date.fromisoformat(query["todate"][0])
        if (end != capture_day or start > end
                or (end - start).days > 90
                or original_url != quote_url(symbol, start, end)):
            raise ValueError("Unapproved price request or historical relabeling")
        sha = row.get("sha256")
        if not isinstance(sha, str) or len(sha) != 64:
            raise ValueError("Invalid source fingerprint")
        original_path = Path(row.get("raw_path", ""))
        if not original_path.is_absolute():
            original_path = Path.cwd() / original_path
        if (original_path.resolve().parent != root / "raw"
                or original_path.name != f"{symbol}_{sha}.json"
                or not original_path.is_file()):
            raise ValueError("Original source path missing or outside archive")
        original = original_path.read_bytes()
        if hashlib.sha256(original).hexdigest() != sha or row.get("bytes") != len(original):
            raise ValueError("Original Nasdaq source tampered with")
        checked = validate_price_response(original, start, end)
        if any(row.get(field) != checked[field] for field in (
                "rows_validated", "first_observation_date", "last_observation_date",
                "provider_data_are_historically_pit_attested",
                "split_dividend_adjustment_verified", "score_eligible")):
            raise ValueError("Archived Nasdaq rows disagree with original bytes")
        provider_data = json.loads(original).get("data", {})
        observed_symbol = provider_data.get("symbol") if isinstance(provider_data, dict) else None
        if observed_symbol is not None and observed_symbol != symbol:
            raise ValueError("Provider response symbol disagrees with requested instrument")
        receipt_rows.append({
            "symbol": symbol,
            "source_sha256_rechecked": sha,
            "source_bytes": len(original),
            "original_rows_rechecked": checked["rows_validated"],
            "first_observation_date": checked["first_observation_date"],
            "last_observation_date": checked["last_observation_date"],
            "historical_pit_verified": False,
        })
    if seen != set(RESEARCH_SYMBOLS):
        raise ValueError("Unaccounted research instrument")
    result = {
        "schema_version": "aics-ai-equities-prospective-raw-rehash-v1",
        "scope": "CURRENT_CAPTURE_NOT_HISTORIC_PRICE_VINTAGE",
        "capture_day_utc": capture_day.isoformat(),
        "capture_started_at_utc": manifest["retrieved_at_utc"],
        "local_original_rehashes": len(receipt_rows),
        "original_candidate_rows": sum(x["original_rows_rechecked"] for x in receipt_rows),
        "source_receipts": receipt_rows,
        "provider_publication_time_attested": False,
        "point_in_time_membership_attested": False,
        "corporate_action_adjustment_pit_attested": False,
        "source_license_cleared": False,
        "historical_price_pit_attested": False,
        "independently_certified_nodes": 0,
        "node_stress_score": None,
        "index_aics": None,
        "predictive_skill_score": None,
        "promotion": "BLOCKED",
        "trades_created": False,
        "limitations": [
            "Rehash validates local raw bytes, not historical Nasdaq vintage availability.",
            "Contemporaneous provider publishing times and surviving historical index membership remain unproven.",
            "Retain original bytes only where provider rights permit; do not promote to model inputs.",
        ],
    }
    (root / "prospective_rehash_receipt.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("aics_data/source_evidence/ai_equities_live"))
    args = parser.parse_args()
    try:
        result = audit_capture(args.out)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("AI Equities prospective raw receipt BLOCKED:", type(exc).__name__)
        return 1
    print(json.dumps({
        "locally_rehashed_originals": result["local_original_rehashes"],
        "real_candidate_rows": result["original_candidate_rows"],
        "historical_pit_attested": False,
        "index_aics": None,
        "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
