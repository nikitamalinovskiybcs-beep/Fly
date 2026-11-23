#!/usr/bin/env python3
"""Fail-closed source-to-candidate audit for pinned real SEC research receipts.

Validates the *recorded* ZIP/source hashes, filing chronology and actual
arithmetic. This script does not redownload the underlying ZIP archives.
Source-byte rehash attestation requires the original archived bytes and is
separate from this metadata check. Neither passes historical SEC PIT.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

DEFAULT_RECEIPT = Path(
    "aics_data/research/sec_primary_archive_independent_rehash_2026_11_18.json"
)
SHA = re.compile(r"[a-f0-9]{64}\Z")
ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}\Z")
RUN = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/\d+\Z")
ISSUERS = {"MET": "0001099219", "PRU": "0001137774"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def checked_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def digest(value: str) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def verify(data: dict) -> dict:
    require(isinstance(data, dict) and
            data.get("schema_version") == "aics-sec-primary-byte-audit-v1",
            "unrecognized SEC source receipt")
    as_of = checked_date(data["as_of"])
    require(data.get("scope") ==
            "CURRENT_ARCHIVED_SEC_BYTES_AND_RESEARCH_BALANCE_SHEET_RATIOS_NOT_HISTORICAL_PIT",
            "research SEC source reclassified as historical PIT")
    require(data.get("fixed_node_count") == 11 and data.get("total_weight") == 1050
            and data.get("additional_project_milestones") == 0
            and data.get("independently_certified_nodes") == 0
            and data.get("new_node_score") is None
            and data.get("index_aics") is None
            and data.get("predictive_skill_score") is None
            and data.get("promotion") == "BLOCKED"
            and data.get("trades_created") is False,
            "SEC receipts must never promote unvalidated AICS")

    insurers = data["insurers"]
    spv = data["neocloud_spv"]
    for item in (insurers, spv):
        require(isinstance(item, dict)
                and isinstance(item.get("github_run_url"), str)
                and RUN.fullmatch(item["github_run_url"]) is not None
                and type(item.get("artifact_id")) is int
                and item["artifact_id"] > 0
                and digest(item.get("artifact_zip_sha256")),
                "missing original archived ZIP identity")
        require(checked_date(item["archive_expires_at_utc"][:10]) > as_of,
                "archive expired at the reporting date")
    require(insurers.get("independent_historical_pit_verified") is False
            and insurers.get("records_primary_provider_current_companyfacts_not_historical_vintage") is True
            and spv.get("independent_historical_pit_verified") is False,
            "modern source collection is not a historic provider vintage")
    require(insurers.get("all_candidates_checked_for_sec_filed_plus_14_days") is True
            and insurers.get("candidate_observation_count") == 521
            and insurers.get("issuer_counts") == {"MET": 257, "PRU": 264}
            and digest(insurers.get("candidate_csv_sha256")),
            "source candidate count or chronology claim changed")

    sources = insurers.get("original_sec_json_files")
    require(isinstance(sources, list) and len(sources) == 6,
            "expected 6 source insurer JSON originals")
    source_shas = {}
    for src in sources:
        require(isinstance(src, dict), "bad SEC JSON source")
        key = (src.get("issuer"), src.get("kind"))
        require(key[0] in ISSUERS and key[1] in
                ("submissions", "companyfacts", "filings.files")
                and key not in source_shas and digest(src.get("sha256"))
                and type(src.get("bytes")) is int and src["bytes"] > 0,
                "missing or duplicate insurer original")
        source_shas[key] = src["sha256"]
    require(len(source_shas) == 6, "missing original SEC JSON")

    ratios = insurers.get("research_asset_mix")
    require(isinstance(ratios, list) and len(ratios) == 2
            and {r["issuer"] for r in ratios} == set(ISSUERS),
            "expected two specific issuer candidate ratios")
    observed = []
    for row in ratios:
        name = row["issuer"]
        filed = checked_date(row["filed_at"])
        period = checked_date(row["period_end"])
        available = checked_date(row["available_at"])
        require(row["cik"] == ISSUERS[name] and row["form"] == "10-Q"
                and isinstance(row["accession"], str)
                and ACCESSION.fullmatch(row["accession"]) is not None
                and period <= filed and available == filed + dt.timedelta(days=14)
                and available <= as_of,
                "SEC original filing availability is not PIT eligible")
        require(row.get("source_companyfacts_sha256") ==
                source_shas[(name, "companyfacts")],
                "candidate value detached from original companyfacts")
        assets, afs = row["assets_usd"], row["afs_debt_securities_usd"]
        require(type(assets) is int and type(afs) is int
                and 0 < afs <= assets,
                "non-financial or non-subset security amount")
        calculated = (Decimal(afs) * 100 / Decimal(assets)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP)
        require(Decimal(str(row["afs_to_assets_pct"])) == calculated,
                "research-only AFS/assets ratio not reproducible")
        require(row.get("ai_specific_exposure_verified") is False
                and row.get("stress_score") is None,
                "balance-sheet composition is not AI stress")
        observed.append({"issuer": name, "period_end": period.isoformat(),
                         "filed_at": filed.isoformat(),
                         "available_at": available.isoformat(),
                         "afs_to_assets_pct": str(calculated)})
    require(spv.get("available_count") == 4
            and spv.get("raw_html_sha256_rechecked_count") == 4
            and spv.get("embargo_excluded_count") == 1
            and spv.get("independently_verified_spv_contracts") == 0
            and spv.get("drawn_debt_verified_usd") is None
            and digest(spv.get("source_registry_sha256")),
            "missing or falsely certified SPV evidence")
    original = spv.get("original_sec_html_files")
    require(isinstance(original, list) and len(original) == 4,
            "missing real SEC HTML candidates")
    ids = set()
    for doc in original:
        require(isinstance(doc, dict)
                and isinstance(doc.get("source_id"), str)
                and doc["source_id"] not in ids and digest(doc.get("sha256"))
                and type(doc.get("bytes")) is int and doc["bytes"] > 0
                and checked_date(doc["available_at"]) ==
                checked_date(doc["filed_at"]) + dt.timedelta(days=14)
                and checked_date(doc["available_at"]) <= as_of,
                "SPV source is duplicated, future or unhashable")
        ids.add(doc["source_id"])
    require(ids == {"NBIS_CITI_6K_20261022", "NBIS_CITI_EX99_20261022",
                    "EQIX_10Q_20261028", "APLD_10Q_20261007"},
            "different SEC source registry")
    blocked = spv["date_excluded"]
    require(blocked.get("source_id") == "CRWV_10Q_20261112"
            and blocked.get("issuer") == "CoreWeave"
            and blocked.get("status") == "excluded_14_day_sec_lag"
            and checked_date(blocked["available_at"]) ==
            checked_date(blocked["filed_at"]) + dt.timedelta(days=14)
            and checked_date(blocked["available_at"]) > as_of,
            "CoreWeave embargo bypassed")
    return {
        "receipt_integrity": "PASS_METADATA_AND_ARITHMETIC_ONLY",
        "raw_zip_rehash_performed_by_this_script": False,
        "archived_sec_json": 6,
        "archived_sec_html": 4,
        "sec_candidate_observations": 521,
        "asset_mix_research_only": observed,
        "independently_verified_historical_pit": False,
        "node_score": None, "index_aics": None,
        "promotion": "BLOCKED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    result = verify(json.loads(args.receipt.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
