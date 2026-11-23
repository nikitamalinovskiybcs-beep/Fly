#!/usr/bin/env python3
"""Fail-closed archive-stage receipt for original Nasdaq price JSON.

All seven raw bytes and their SHA256s were independently checked against GitHub
Actions artifact 14466941540. This never attests historical PIT or scores.
"""
import json
from pathlib import Path

RECEIPT_PATH = "aics_data/progress/ai_equities_nasdaq_raw_archive_receipt_2026-11-18.json"
RUN_URL = "https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44387147503"
ZIP_SHA = "0354dea8f0507a770afc4dcfcbb7ce9d4ddf33539d774664b62fa1b04464e9b8"
MANIFEST_SHA = "9bccc1d37085816c13be3f709ae5a4cfc81eb939b8edaf0fc7a8a4636c869120"
SOURCE_SHA = {
    "NVDA": "f6640ca7e5e806c74e077bd6ffc42178fced0a03ec1cda341cd210ffecd01092",
    "MSFT": "3a43904adcd0b4e9f77d9d3717e644affa0f53127cd9008a2a6a5af9d56acd8e",
    "GOOGL": "906b51190955fc7148500e3b7cd61cc9bb1cf70aa9b157f8e60b2bdf1b8613ef",
    "AMZN": "bd280aea245107ba3a1498e0a593957cbd3f012c4be0fa647dc5248e58aac67a",
    "META": "ba54c37df4e7b9c7c4b19333f9e5c9c21e5dd43ff6f8306bc5d2379d08723b34",
    "ORCL": "151ac422b532e2239b932143afca4bb06c1c93fa444a3a99f7f3d9bb87b71e09",
    "MU": "b5b914e41482630d6c0044c169d1f439e5aa398698bff08f03fb8174d9a66196",
}
SOURCE_BYTES = {
    "NVDA": 7403,
    "MSFT": 7366,
    "GOOGL": 7374,
    "AMZN": 7376,
    "META": 7380,
    "ORCL": 7355,
    "MU": 7516,
}
EVIDENCE_STATUS = "NASDAQ_DATED_RAW_PRICE_BYTES_SHA256_RECHECKED_NOT_PIT"


def verified_ai_equities_archive(root: Path, manifest: dict) -> set[str]:
    entries = manifest.get("independently_recalculated_raw_archive_receipts", [])
    if not isinstance(entries, list):
        raise ValueError("invalid source receipt collection")
    selected = [row for row in entries if isinstance(row, dict)
                and row.get("node") == "AI Equities"]
    if len(selected) > 1:
        raise ValueError("duplicate AI Equities source receipt")
    if not selected:
        return set()
    if (selected[0].get("receipt_path") != RECEIPT_PATH
            or selected[0].get("evidence_status") != EVIDENCE_STATUS):
        raise ValueError("unapproved Nasdaq source receipt")
    path = (root / RECEIPT_PATH).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("original source receipt missing")
    x = json.loads(path.read_text(encoding="utf-8"))
    if (x.get("schema_version") != "aics-ai-equities-raw-archive-receipt-v1"
            or x.get("node") != "AI Equities"
            or x.get("as_of") != manifest.get("report_as_of")
            or x.get("scope") != "RAW_PRICE_CANDIDATE_NOT_HISTORICAL_PIT"
            or x.get("artifact_run_url") != RUN_URL
            or x.get("artifact_id") != 14466941540
            or x.get("artifact_zip_sha256") != ZIP_SHA
            or x.get("internal_manifest_sha256") != MANIFEST_SHA
            or x.get("archive_expires_at") != "2026-12-18T20:04:45Z"
            or x.get("raw_archive_candidate_milestone_complete") is not True
            or x.get("node_stress_score") is not None
            or x.get("index_aics") is not None
            or x.get("predictive_skill_score") is not None
            or x.get("promotion") != "BLOCKED"
            or x.get("trades_created") is not False):
        raise ValueError("Nasdaq source archive cannot promote AICS")
    checks = x.get("independent_recalculation", {})
    if (checks.get("checked_files") != 7
            or checks.get("matching_source_hashes") != 7
            or checks.get("matching_response_symbols") != 7
            or checks.get("validated_original_rows") != 441
            or checks.get("historical_pit_verified") is not False
            or checks.get("split_dividend_adjustment_pit_verified") is not False
            or checks.get("historical_constituents_verified") is not False
            or checks.get("source_license_cleared") is not False):
        raise ValueError("Nasdaq original source rehash or PIT caveat missing")
    sources = x.get("original_files")
    if not isinstance(sources, list) or len(sources) != 7:
        raise ValueError("incomplete original Nasdaq market bytes")
    seen = set()
    for src in sources:
        if not isinstance(src, dict):
            raise ValueError("invalid source row")
        symbol = src.get("symbol")
        if symbol not in SOURCE_SHA or symbol in seen:
            raise ValueError("unexpected or duplicate Nasdaq symbol")
        if (src.get("raw_json_sha256") != SOURCE_SHA[symbol]
                or src.get("bytes") != SOURCE_BYTES[symbol]
                or src.get("rows") != 63
                or src.get("first_date") != "2026-08-20"
                or src.get("last_date") != "2026-11-17"
                or src.get("url") != (
                    "https://api.nasdaq.com/api/quote/" + symbol
                    + "/historical?assetclass=stocks&fromdate=2026-08-20"
                    + "&todate=2026-11-18&limit=100")
                or src.get("score_eligible") is not False):
            raise ValueError("Nasdaq source hashes or lineage mismatch")
        seen.add(symbol)
    if seen != set(SOURCE_SHA):
        raise ValueError("incomplete AI Equities source group")
    return {"AI Equities"}
