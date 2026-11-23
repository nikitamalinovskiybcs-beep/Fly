#!/usr/bin/env python3
"""Research-only UST 30Y/SOFR panel and licensed-credit coverage from original ALFRED ZIP.

Four raw CSVs are independently SHA-256 rechecked against the previously
rehashed source receipt. ICE BofA values are NEVER republished; only the
non-numeric series inventory/coverage is reported. A retrospective ALFRED
as-of replay does NOT independently prove contemporaneous data availability.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import zipfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from scripts.aics_collect_alfred_iorb_power import month_ends

DEFAULT_RECEIPT = Path("aics_data/research/alfred_macro_archive_rehash_2026_11_18.json")
DEFAULT_OUT = Path("docs/audit/aics_ust30_private_credit_24_month_source_panel_2026-11-18.json")
PUBLIC_SERIES = {"DGS30", "SOFR"}
LICENSED_SERIES = {"BAMLH0A0HYM2", "BAMLH0A3HYC"}
EXPECTED_SERIES = PUBLIC_SERIES | LICENSED_SERIES
EXPECTED_HEADERS = (
    "series_id", "observation_date", "as_of", "realtime_start", "realtime_end",
    "value", "source", "verified_pit",
)


class SourceIntegrityError(ValueError):
    pass


def _date(raw: str) -> dt.date:
    try:
        return dt.date.fromisoformat(raw)
    except (ValueError, TypeError):
        raise SourceIntegrityError("invalid original source date") from None


def _decimal(raw: str) -> Decimal:
    try:
        value = Decimal(raw)
    except (TypeError, InvalidOperation):
        raise SourceIntegrityError("invalid provider value") from None
    if not value.is_finite():
        raise SourceIntegrityError("non-finite provider value")
    return value


def _zip_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive(archive: Path, receipt_path: Path = DEFAULT_RECEIPT) -> dict:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        receipt.get("schema_version") != "aics-alfred-macro-research-recheck-v1"
        or receipt.get("scope") != "REHASHED_ARCHIVED_ALFRED_SNAPSHOTS_NOT_PROVIDER_VINTAGE_ATTESTATION"
        or receipt.get("historical_pit_certified") is not False
        or receipt.get("independent_provider_vintage_attestation") is not False
        or receipt.get("score_eligible") is not False
        or receipt.get("index_aics") is not None
        or receipt.get("series_count") != 4
        or receipt.get("monthly_vintages_per_series") != 24
        or receipt.get("source_rows_total") != 165913
        or _zip_digest(archive) != receipt.get("artifact_zip_sha256")
    ):
        raise SourceIntegrityError("source ZIP or independent receipt mismatch")
    expected = month_ends()
    months = {x.isoformat() for x in expected}
    incoming = {x["series_id"]: x for x in receipt["series"]}
    if set(incoming) != EXPECTED_SERIES:
        raise SourceIntegrityError("missing or unknown macro source series")
    last_values = {}
    coverage = {}
    with zipfile.ZipFile(archive) as bundle:
        if not {"manifest.json", "quality_report.json", "coverage_report.json"} <= set(bundle.namelist()):
            raise SourceIntegrityError("missing original provider manifest")
        expected_files = {f"alfred_asof_{sid}.csv" for sid in EXPECTED_SERIES}
        if set(bundle.namelist()) != expected_files | {"manifest.json", "quality_report.json", "coverage_report.json"}:
            raise SourceIntegrityError("unexpected original ZIP inventory")
        for sid in sorted(EXPECTED_SERIES):
            raw = bundle.read(f"alfred_asof_{sid}.csv")
            if hashlib.sha256(raw).hexdigest() != incoming[sid]["csv_sha256"]:
                raise SourceIntegrityError("CSV SHA-256 mismatch")
            grouped: dict[str, tuple[dt.date, Decimal] | None] = {d: None for d in months}
            seen = set()
            counts = defaultdict(int)
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
            if tuple(reader.fieldnames or ()) != EXPECTED_HEADERS:
                raise SourceIntegrityError("unexpected ALFRED CSV columns")
            for row in reader:
                if not isinstance(row, dict) or None in row:
                    raise SourceIntegrityError("malformed original row")
                asof = row["as_of"]
                if (
                    row["series_id"] != sid or asof not in months
                    or row["source"] != "ALFRED_AS_OF" or row["verified_pit"] != "False"
                    or row["realtime_start"] != asof or row["realtime_end"] != asof
                ):
                    raise SourceIntegrityError("provider vintage or series boundary violated")
                day = _date(row["observation_date"])
                if day > _date(asof) or day < dt.date(2010, 1, 1):
                    raise SourceIntegrityError("look-ahead or unsupported observation date")
                key = (asof, row["observation_date"])
                if key in seen:
                    raise SourceIntegrityError("duplicate original source observation")
                seen.add(key)
                counts[asof] += 1
                if sid in PUBLIC_SERIES:
                    value = _decimal(row["value"])
                    prior = grouped[asof]
                    if prior is None or day > prior[0]:
                        grouped[asof] = (day, value)
                else:
                    # Restrict ICE source-derived numeric values from outputs.
                    if row["value"] in ("", "."):
                        raise SourceIntegrityError("unexpected empty licensed source observation")
            if len(seen) != incoming[sid]["source_rows"] or set(counts) != months:
                raise SourceIntegrityError("row count or 24 actual as-of snapshots mismatch")
            if sum(counts.values()) != incoming[sid]["source_rows"]:
                raise SourceIntegrityError("source duplicate / count discrepancy")
            coverage[sid] = {
                "source_rows": incoming[sid]["source_rows"],
                "historical_asof_queries": len(counts),
                "csv_sha256": incoming[sid]["csv_sha256"],
                "original_contemporaneous_release_attested": False,
                "licensed_credit_proxy_not_direct_private_credit": sid in LICENSED_SERIES,
                "numeric_values_redistributed": False if sid in LICENSED_SERIES else True,
                "source_license_public_redistribution_cleared": False if sid in LICENSED_SERIES else None,
            }
            if sid in PUBLIC_SERIES:
                if any(value is None for value in grouped.values()):
                    raise SourceIntegrityError("missing public source monthly month-end observation")
                last_values[sid] = grouped

    rows = []
    for index, asof in enumerate(expected):
        d = asof.isoformat()
        dgsday, dgsval = last_values["DGS30"][d]
        sofrday, sofrval = last_values["SOFR"][d]
        age_dgs = (asof - dgsday).days
        age_sofr = (asof - sofrday).days
        if not (0 < age_dgs <= 7 and 0 < age_sofr <= 7):
            raise SourceIntegrityError("same-day, future, or stale provider observation")
        prev = rows[-1] if rows else None
        rows.append({
            "as_of_month_end": d,
            "dgs30_observation_date": dgsday.isoformat(),
            "sofr_observation_date": sofrday.isoformat(),
            "dgs30_pct": str(dgsval),
            "sofr_pct": str(sofrval),
            "dgs30_minus_sofr_bps": str((dgsval - sofrval) * 100),
            "dgs30_month_over_month_bps": (
                str((dgsval - Decimal(prev["dgs30_pct"])) * 100) if prev else None
            ),
            "dgs30_twelve_month_change_bps": (
                str((dgsval - Decimal(rows[index - 12]["dgs30_pct"])) * 100)
                if index >= 12 else None
            ),
            "source_release_pit_certified": False,
            "node_stress_score_eligible": False,
        })
    if len(rows) != 24:
        raise SourceIntegrityError("incomplete public series observed panel")
    oct_change = Decimal(rows[-1]["dgs30_pct"]) - Decimal(rows[-2]["dgs30_pct"])
    return {
        "schema_version": "aics-ust30-public-real-asof-panel-with-privatecredit-coverage-v1",
        "research_as_of": "2026-11-18",
        "original_provider_artifact_id": receipt["artifact_id"],
        "original_provider_zip_sha256": receipt["artifact_zip_sha256"],
        "source_csv_sha256_rechecked": True,
        "source_snapshot_asof_start": rows[0]["as_of_month_end"],
        "source_snapshot_asof_end": rows[-1]["as_of_month_end"],
        "source_series": coverage,
        "monthly_public_observations": rows,
        "observed_public_months": len(rows),
        "dgs30_last_observed_rate_percent": rows[-1]["dgs30_pct"],
        "dgs30_last_month_change_bps": str(oct_change * 100),
        "licensed_ice_series": sorted(LICENSED_SERIES),
        "private_credit_direct_exposure_measured": False,
        "ice_numeric_values_in_output": False,
        "synthetic_market_observations_created": 0,
        "original_2024_2026_release_timestamps_independently_attested": False,
        "source_provider_historical_pit_certified": False,
        "untouched_24_month_oos": False,
        "node_scores": {"UST 30Y": None, "Private Credit": None, "Repo": None},
        "aics_index": None,
        "promotion": "BLOCKED",
        "notes": [
            "Original 24 ALFRED month-end as-of requests were archived on 2026-11-18, not at each historical date.",
            "DGS30 less SOFR is descriptive yield-rate differential, NOT a Treasury term premium.",
            "ICE BofA indices are licensed high-yield proxies, NOT direct private credit exposure observations.",
            "The current provider's historical API responses alone do not prove actual initial release date.",
            "No algorithmic stress score is assigned or published from 24 retrospective monthly observations.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        result = derive(args.archive, args.receipt)
    except (SourceIntegrityError, OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        print("AICS UST30/credit source-panel BLOCKED:", type(exc).__name__)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "original_public_months": result["observed_public_months"],
        "dgs30_october_pct": result["dgs30_last_observed_rate_percent"],
        "dgs30_month_change_bps": result["dgs30_last_month_change_bps"],
        "private_credit_licensed_values_republished": False,
        "index_aics": None,
        "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
