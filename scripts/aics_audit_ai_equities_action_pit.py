#!/usr/bin/env python3
"""Fail-closed original-source and chronology audit for AI Equities action/membership history.

This is a gap audit, not historical PIT certification. A document downloaded
today does not prove what exchange participants knew on an old observation day.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from scripts.aics_collect_ai_equities_prices import RESEARCH_SYMBOLS

FACETS = ("corporate_action_history", "security_identity_history",
          "historical_constituency")
SCHEMA = "aics-ai-equities-historical-action-evidence-v1"
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MAX_DOCUMENT_BYTES = 8_000_000
PRIMARY_HOSTS = ("www.nasdaq.com", "www.nasdaqtrader.com", "nasdaqtrader.com",
                 "data.nasdaq.com", "www.sec.gov", "sec.gov", "www.nyse.com")
REGISTRY_PATH = Path("aics_data/source_registry/ai_equities_action_pit_registry_2026-11-19.json")
OUT_PATH = Path("aics_data/research/ai_equities_action_pit_gap_report.json")


def _timestamp(value: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError("Missing source timestamp")
    result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Source timestamp must include an offset")
    return result.astimezone(dt.timezone.utc)


def audit_action_registry(registry_path: Path, *, out_path: Path | None = None) -> dict:
    document = json.loads(registry_path.read_text(encoding="utf-8"))
    if (document.get("schema_version") != SCHEMA
            or document.get("node") != "AI Equities"
            or document.get("research_symbols") != list(RESEARCH_SYMBOLS)
            or document.get("mandatory_facets") != list(FACETS)):
        raise ValueError("Unexpected immutable AI Equities roster or facet registry")
    # No original record may smuggle model promotion through the gap document.
    if (document.get("index_aics") is not None
            or document.get("node_stress_score") is not None
            or document.get("predictive_skill_score") is not None
            or document.get("promotion") != "BLOCKED"
            or document.get("trades_created") is not False
            or document.get("all_absence_of_actions_assertions") is not False
            or document.get("historical_membership_verified") is not False
            or document.get("split_dividend_adjustment_pit_verified") is not False
            or document.get("corporate_action_history_pit_verified") is not False
            or document.get("independently_certified_pit") is not False):
        raise ValueError("Unsupported AICS corporate-action or price PIT promotion")
    records = document.get("original_evidence_records")
    if not isinstance(records, list):
        raise ValueError("Original source evidence must be a list")
    root = Path.cwd().resolve()
    original_root = (root / "aics_data/source_evidence/ai_equities_action_originals").resolve()
    read_pairs: set[tuple[str, str]] = set()
    source_fingerprints: set[tuple[str, str, str]] = set()
    local_rehashes = []
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("Malformed corporate-action source record")
        symbol, facet = row.get("symbol"), row.get("facet")
        if symbol not in RESEARCH_SYMBOLS or facet not in FACETS:
            raise ValueError("Unknown security or evidence facet")
        if row.get("historical_pit_attested") is not False:
            raise ValueError("Source receipt must not certify historical PIT")
        if row.get("independent_publication_release_attested") is not False:
            raise ValueError("Provider release attestation is not independent")
        if row.get("licensed_for_model_use") is not False:
            raise ValueError("Uncleared provider rights cannot be auto-approved")
        source = row.get("source")
        if source not in ("NASDAQ_DAILY_LIST", "NASDAQ_DAILY_LIST_SPEC",
                          "SEC_EDGAR", "EXCHANGE_BULLETIN"):
            raise ValueError("Unsupported primary source class")
        url = urlparse(row.get("url", ""))
        if url.scheme != "https" or url.hostname not in PRIMARY_HOSTS:
            raise ValueError("Untrusted or non-HTTPS original source")
        release = _timestamp(row.get("published_at_utc"))
        capture = _timestamp(row.get("retrieved_at_utc"))
        if release > capture or capture > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
            raise ValueError("Impossible source publication/capture chronology")
        start = dt.date.fromisoformat(row["coverage_start"])
        end = dt.date.fromisoformat(row["coverage_end"])
        if not start <= end <= capture.date():
            raise ValueError("Source coverage after capture or inverted date range")
        if source == "SEC_EDGAR":
            filed = dt.date.fromisoformat(row["filed_at"])
            available = dt.date.fromisoformat(row["available_at"])
            if (available != filed + dt.timedelta(days=14)
                    or capture.date() < available or start > filed):
                raise ValueError("SEC original violates the 14-day embargo")
        elif row.get("filed_at") is not None or row.get("available_at") is not None:
            raise ValueError("SEC embargo fields attached to non-SEC document")
        sha = row.get("sha256")
        if not isinstance(sha, str) or not HASH_PATTERN.fullmatch(sha):
            raise ValueError("Invalid original document hash")
        relative = Path(row.get("original_path", ""))
        if relative.is_absolute():
            raise ValueError("Absolute source path forbidden")
        original = (root / relative).resolve()
        if (not original.is_relative_to(original_root)
                or original.suffix not in (".json", ".txt", ".html", ".csv", ".pdf")
                or not original.is_file()):
            raise ValueError("Missing document or path escapes archive")
        body = original.read_bytes()
        if (not body or len(body) > MAX_DOCUMENT_BYTES
                or len(body) != row.get("bytes")
                or hashlib.sha256(body).hexdigest() != sha):
            raise ValueError("Tampered or oversized original corporate action source")
        key = (symbol, facet, sha)
        if key in source_fingerprints:
            raise ValueError("Duplicate source evidence record")
        source_fingerprints.add(key)
        read_pairs.add((symbol, facet))
        local_rehashes.append({"symbol":symbol, "facet":facet, "sha256":sha,
                              "bytes":len(body), "status":"ORIGINAL_BYTES_CHECKED_NOT_PIT"})
    matrix = [{
        "symbol": symbol,
        "facets": {facet: ("LOCAL_SOURCE_ONLY_NOT_PIT" if (symbol, facet) in read_pairs
                          else "MISSING_HISTORICAL_SOURCE") for facet in FACETS},
        "all_historical_facets_pit_verified": False,
    } for symbol in RESEARCH_SYMBOLS]
    result = {
        "schema_version": "aics-ai-equities-action-pit-gap-report-v1",
        "node": "AI Equities",
        "requested_original_facets": len(RESEARCH_SYMBOLS) * len(FACETS),
        "source_facets_with_local_originals": len(read_pairs),
        "facets_missing_original_sources": sum(
            (symbol, facet) not in read_pairs for symbol in RESEARCH_SYMBOLS for facet in FACETS),
        "local_original_rehashes": len(local_rehashes),
        "original_source_receipts": local_rehashes,
        "matrix": matrix,
        "historical_pit_verified": False,
        "corporate_actions_pit_verified": False,
        "membership_pit_verified": False,
        "absence_of_event_proven": False,
        "split_dividend_adjustment_approved": False,
        "score_eligible": False,
        "independently_certified_nodes": 0,
        "node_stress_score": None,
        "index_aics": None,
        "predictive_skill_score": None,
        "promotion": "BLOCKED",
        "trades_created": False,
        "blockers": [
            "No historical exchange action feed with independent release-time attestation",
            "No dated coverage proving historical security membership and ticker identity",
            "No independently verified split/dividend factors as known at each observation date",
            "Provider data use rights and 24-month untouched out-of-sample validation absent",
        ],
    }
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    options = parser.parse_args()
    try:
        report = audit_action_registry(options.registry, out_path=options.out)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print("AICS action evidence integrity FAILED:", type(exc).__name__)
        return 1
    print(json.dumps({
        "local_originals_rehashed": report["local_original_rehashes"],
        "missing_facets": report["facets_missing_original_sources"],
        "historical_pit_verified": False,
        "index_aics": None, "promotion": "BLOCKED"
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
