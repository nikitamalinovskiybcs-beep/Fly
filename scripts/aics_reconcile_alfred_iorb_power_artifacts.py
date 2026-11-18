#!/usr/bin/env python3
"""Losslessly reconcile two genuine, partly rate-limited ALFRED artifact runs.

Never synthesize a missing vintage, interpolate, relabel as-of dates or
resample. Require exactly 48 original provider responses, SHA-256 per file,
consistent overlapping bytes and explicit run/source provenance.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from scripts.aics_collect_alfred_iorb_power import (
    FREEZE_AS_OF, SERIES, month_ends, validate_vintage,
)

PROVENANCE = (
    (44396812187, 14470887017),
    (44397399928, 14471996734),
)
EXPECTED_KEYS = {(series, day.isoformat()) for series in SERIES for day in month_ends()}
OUT = Path("aics_data/pit/free_gaps_2026_11_18_reconciled")


def _read_source(base: Path, run_id: int, artifact_id: int) -> tuple[dict, dict]:
    m = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    if (m.get("schema_version") != "aics-alfred-iorb-power-asof-research-v1"
            or m.get("research_as_of") != FREEZE_AS_OF.isoformat()
            or m.get("expected_snapshots") != 48
            or m.get("aics_index") is not None
            or m.get("promotion") != "BLOCKED"
            or m.get("provider_publication_lag_pit_attested") is not False
            or not isinstance(m.get("series_results"), list)
            or len(m["series_results"]) != 48):
        raise ValueError("untrusted or incomplete provenance report")
    from_run = {}
    blocked = 0
    for row in m["series_results"]:
        key = (row.get("series_id"), row.get("as_of"))
        if key not in EXPECTED_KEYS or key in from_run:
            raise ValueError("unexpected or duplicate historical snapshot")
        if row.get("status") != "downloaded_unverified":
            if row.get("status") != "BLOCKED":
                raise ValueError("unknown ALFRED source status")
            blocked += 1
            from_run[key] = None
            continue
        source_file = row.get("raw_file")
        if source_file != f"{key[0]}_asof_{key[1]}.json":
            raise ValueError("unexpected source path")
        raw = (base / source_file).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row.get("raw_sha256"):
            raise ValueError("original ALFRED response hash mismatch")
        original = validate_vintage(raw, key[0], dt.date.fromisoformat(key[1]))
        if (original["rows"] != row.get("rows")
                or original["non_missing_observations"] != row.get("non_missing_observations")
                or original["raw_sha256"] != row["raw_sha256"]):
            raise ValueError("source row recount or vintage validation failed")
        from_run[key] = (raw, {
            "source_run_id": run_id, "source_artifact_id": artifact_id,
            "captured_at_utc": m["captured_at_utc"],
            "as_of": key[1], "series_id": key[0],
            "source_file": source_file,
            "raw_sha256": row["raw_sha256"],
            "raw_bytes": len(raw),
            "observation_rows": original["rows"],
            "non_missing_observations": original["non_missing_observations"],
            "historical_release_pit_attested": False,
        })
    if len(from_run) != 48:
        raise ValueError("source did not attempt all 48 scheduled snapshots")
    if sum(val is not None for val in from_run.values()) != m.get("successful_snapshots"):
        raise ValueError("source counts mismatched")
    if blocked != len(m.get("blocked", [])):
        raise ValueError("blocked-source metadata mismatched")
    return m, from_run


def reconcile(first: Path, second: Path, dest: Path = OUT) -> dict:
    sources = [_read_source(path, run_id, artifact_id)
               for path, (run_id, artifact_id) in zip(
                   (first, second), PROVENANCE, strict=True)]
    selected = []
    archived = []
    overlap = 0
    for key in sorted(EXPECTED_KEYS):
        choices = [source[1][key] for source in sources if source[1][key] is not None]
        if not choices:
            raise ValueError("unavailable original vintage: no fabrication permitted")
        if len(choices) == 2:
            overlap += 1
            if choices[0][1]["raw_sha256"] != choices[1][1]["raw_sha256"]:
                raise ValueError("ALFRED historical response drift in overlapping runs")
        raw, receipt = choices[0]
        if key[0] not in SERIES or len(raw) == 0:
            raise ValueError("invalid selected original")
        archived.append((receipt["source_file"], raw))
        selected.append(receipt)
    if len(selected) != 48 or overlap != 42:
        raise ValueError("unexpected cross-run reconciliation coverage")

    # No output until every original, date and SHA has been checked.
    dest.mkdir(parents=True, exist_ok=True)
    for filename, raw in archived:
        (dest / filename).write_bytes(raw)
    manifest = {
        "schema_version": "aics-alfred-iorb-power-cross-run-raw-reconciliation-v1",
        "research_as_of": FREEZE_AS_OF.isoformat(),
        "original_captures_utc": [
            {"source_run_id": run_id, "source_artifact_id": artifact_id,
             "captured_at_utc": src["captured_at_utc"],
             "successful_originals": src["successful_snapshots"],
             "source_run_success": src["all_sources_downloaded"]}
            for (run_id, artifact_id), (src, _) in zip(PROVENANCE, sources, strict=True)
        ],
        "original_files": selected,
        "unique_genuine_asof_snapshots": 48,
        "iorb_snapshots": 24, "industrial_power_ppi_snapshots": 24,
        "identical_overlap_files": overlap,
        "replaced_or_synthetically_interpolated_snapshots": 0,
        "source_observation_start": "2018-01-01",
        "original_2018_release_vintages_verified": False,
        "independent_provider_publication_timestamp_pit": False,
        "source_file_sha256_rehashed_outside_initial_collection": True,
        "source_api_key_persisted": False,
        "independent_oos_24m": False,
        "node_stress_scores": {"Repo": None, "Power/Data Centers": None},
        "index_aics": None, "promotion": "BLOCKED", "trades_created": False,
        "limitations": (
            "Two real, different Nov 18 2026 provider captures were combined using "
            "unmodified original JSON files. 24 historical ALFRED as-of queries "
            "for each series are not independently attested contemporaneous releases. "
            "No evidence of true 2018-era publication, node scoring or untouched OOS."
        ),
    }
    (dest / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--dest", type=Path, default=OUT)
    args = parser.parse_args()
    report = reconcile(args.first, args.second, args.dest)
    print(json.dumps({
        "real_original_snapshots": report["unique_genuine_asof_snapshots"],
        "identical_cross_run_overlaps": report["identical_overlap_files"],
        "synthetic_snapshots": 0, "historical_release_pit_verified": False,
        "aics_index": None, "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
