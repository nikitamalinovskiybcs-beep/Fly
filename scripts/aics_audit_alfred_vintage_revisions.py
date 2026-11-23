#!/usr/bin/env python3
"""Independently reconcile REAL ALFRED IORB/WPU0543 monthly vintage revisions.

Consumes immutable original JSON bytes from Actions ZIP; never queries FRED
or imputes observations. "Retrospectively reconstructed as-of" is NOT proof
of contemporaneous release, PIT attestation, or AICS scoring eligibility.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import zipfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from scripts.aics_collect_alfred_iorb_power import SERIES, month_ends, validate_vintage

RECEIPT = Path("aics_data/research/alfred_iorb_power_cross_run_independent_rehash_2026_11_18.json")
OUTPUT = Path("docs/audit/aics_alfred_iorb_power_revision_audit_2026-11-18.json")
SCHEMA = "aics-alfred-iorb-power-adjacent-asof-revision-audit-v1"


class AuditError(ValueError):
    """One or more original sources have failed the evidence integrity gate."""


def _number(value: object) -> Decimal | None:
    if value in (None, "", "."):
        return None
    if isinstance(value, bool) or not isinstance(value, str):
        raise AuditError("unrecognized original numeric observation")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise AuditError("invalid source decimal observation") from None
    if not result.is_finite():
        raise AuditError("non-finite original observation")
    return result


def _file_sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def analyze(archive: Path, receipt_path: Path = RECEIPT) -> dict:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        receipt.get("schema_version") != "aics-alfred-iorb-power-independent-rehash-receipt-v1"
        or receipt.get("unique_original_raw_json_files") != 48
        or receipt.get("independent_historical_publication_time_pit_verified") is not False
        or receipt.get("all_original_file_sha256_verified") is not True
        or receipt.get("aics_index") is not None
        or receipt.get("aics_promotion") != "BLOCKED"
        or _file_sha256(archive) != receipt.get("merged_artifact_zip_sha256")
    ):
        raise AuditError("original ZIP or independent receipt mismatch")

    with zipfile.ZipFile(archive) as container:
        member_names = set(container.namelist())
        if len(member_names) != 49 or "manifest.json" not in member_names:
            raise AuditError("unexpected original ZIP file inventory")
        manifest_bytes = container.read("manifest.json")
        if hashlib.sha256(manifest_bytes).hexdigest() != receipt["merged_manifest_sha256"]:
            raise AuditError("merged original manifest bytes drifted")
        manifest = json.loads(manifest_bytes)
        records = manifest.get("original_files")
        if (
            not isinstance(records, list) or len(records) != 48
            or manifest.get("unique_genuine_asof_snapshots") != 48
            or manifest.get("replaced_or_synthetically_interpolated_snapshots") != 0
            or manifest.get("independent_provider_publication_timestamp_pit") is not False
            or manifest.get("index_aics") is not None
            or manifest.get("promotion") != "BLOCKED"
        ):
            raise AuditError("source claims score or missing genuine original snapshots")

        dated = {}
        row_total = 0
        for record in records:
            sid, source_day = record.get("series_id"), record.get("as_of")
            if sid not in SERIES:
                raise AuditError("unexpected ALFRED series")
            try:
                as_of = dt.date.fromisoformat(source_day)
            except (TypeError, ValueError):
                raise AuditError("invalid original as-of date") from None
            key = (sid, as_of)
            if key in dated:
                raise AuditError("duplicate vintage day")
            filename = f"{sid}_asof_{source_day}.json"
            if record.get("source_file") != filename or filename not in member_names:
                raise AuditError("original JSON filename mismatch")
            original = container.read(filename)
            if hashlib.sha256(original).hexdigest() != record.get("raw_sha256"):
                raise AuditError("original provider byte-level SHA mismatch")
            try:
                verification = validate_vintage(original, sid, as_of)
            except ValueError as exc:
                raise AuditError("ALFRED vintage chronology failed") from exc
            if (verification["rows"] != record.get("observation_rows")
                    or verification["non_missing_observations"] != record.get("non_missing_observations")
                    or len(original) != record.get("raw_bytes")):
                raise AuditError("source row-count, nonmissing count or bytes mismatch")
            data = json.loads(original)
            dates = {}
            for observation in data["observations"]:
                observation_date = observation["date"]
                if observation_date in dates:
                    raise AuditError("duplicate underlying economic observation")
                dates[observation_date] = _number(observation.get("value"))
            dated[key] = dates
            row_total += len(dates)
        if member_names != {"manifest.json"} | {
            f"{sid}_asof_{day.isoformat()}.json" for sid in SERIES for day in month_ends()
        }:
            raise AuditError("historical original ZIP has missing/untrusted files")

    expected_days = month_ends()
    if set(dated) != {(sid, d) for sid in SERIES for d in expected_days}:
        raise AuditError("one or more dated original snapshots missing")

    coverage = {}
    changes = []
    for series in SERIES:
        comparisons = 0
        changed = 0
        added = 0
        removed = 0
        missingness_changed = 0
        comparable_pairs = 0
        transitions = []
        for earlier, later in zip(expected_days, expected_days[1:]):
            before, after = dated[(series, earlier)], dated[(series, later)]
            a, b = set(before), set(after)
            common = sorted(a & b)
            changed_values = []
            delta_missing = []
            for obs in common:
                old, new = before[obs], after[obs]
                if old is None or new is None:
                    if (old is None) != (new is None):
                        delta_missing.append(obs)
                    continue
                comparable_pairs += 1
                if old != new:
                    changed_values.append({
                        "observation_date": obs, "old": str(old), "new": str(new),
                        "delta": str(new - old),
                        "from_as_of": earlier.isoformat(), "to_as_of": later.isoformat(),
                        "series_id": series,
                    })
            comparisons += 1
            changed += len(changed_values)
            added += len(b - a)
            removed += len(a - b)
            missingness_changed += len(delta_missing)
            changes.extend(changed_values)
            transitions.append({
                "from_as_of": earlier.isoformat(), "to_as_of": later.isoformat(),
                "revised_observation_values": len(changed_values),
                "new_observation_dates": len(b - a),
                "removed_observation_dates": len(a - b),
                "changed_missingness": len(delta_missing),
            })
        latest = dated[(series, expected_days[-1])]
        most_recent_valid = max(date for date, value in latest.items() if value is not None)
        coverage[series] = {
            "adjacent_snapshot_comparisons": comparisons,
            "comparable_nonmissing_observation_pairs": comparable_pairs,
            "changed_existing_nonmissing_observations": changed,
            "new_observation_date_memberships": added,
            "removed_observation_date_memberships": removed,
            "missingness_transitions": missingness_changed,
            "newest_observation_date_asof_2026_10_31": most_recent_valid,
            "latest_value_in_original_asof_2026_10_31": str(latest[most_recent_valid]),
            "transitions": transitions,
        }

    if row_total != receipt["original_provider_response_observation_rows"]:
        raise AuditError("independent total original economic-row recount mismatch")

    return {
        "schema_version": SCHEMA,
        "research_as_of": "2026-11-18",
        "vintage_snapshots_per_series": 24,
        "original_provider_files_rehashed": len(dated),
        "recounted_original_observation_rows": row_total,
        "source_zip_sha256": receipt["merged_artifact_zip_sha256"],
        "source_archive_run": receipt["merged_workflow_run_id"],
        "source_artifact_id": receipt["merged_artifact_id"],
        "series": coverage,
        "observed_cross_vintage_revisions": changes,
        "observed_revision_event_count": len(changes),
        "synthetically_filled_rows": 0,
        "retrospective_api_asof_replay_only": True,
        "independent_contemporaneous_publication_proof": False,
        "independent_24_month_oos": False,
        "certified_node_stress_scores": {"Repo": None, "Power/Data Centers": None},
        "index_aics": None,
        "promotion": "BLOCKED",
        "limitations": [
            "These original 48 ALFRED queries were executed on 2026-11-18, not at each past as-of.",
            "An observed change between two monthly snapshots is NOT a timestamped original release.",
            "69 revision events may involve repeated changes to one economic observation.",
            "IORB zero changed values in adjacent monthly as-of comparisons does not prove future no revisions.",
            "Never infer data-center contract electricity pricing from national industrial PPI.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        result = analyze(args.archive, args.receipt)
    except (AuditError, OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print("AICS ALFRED revisions integrity BLOCKED:", type(exc).__name__)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "original_files": result["original_provider_files_rehashed"],
        "provider_observation_rows": result["recounted_original_observation_rows"],
        "revision_events": {k: v["changed_existing_nonmissing_observations"]
                            for k, v in result["series"].items()},
        "certified_aics": None,
        "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
