#!/usr/bin/env python3
"""Derive an observed Repo rate-spread panel from original NY Fed and ALFRED bytes.

Research only: NY Fed current-capture history may include revisions, and ALFRED
as-of JSON was queried retrospectively on Nov 18, 2026. This cross-source
calculation is NOT point-in-time attestation or an AICS node stress score.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import statistics
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from scripts.aics_collect_alfred_iorb_power import month_ends, validate_vintage
from scripts.aics_collect_nyfed_repo_rates import validate_rows as validate_nyfed

ALFRED_RECEIPT = Path("aics_data/research/alfred_iorb_power_cross_run_independent_rehash_2026_11_18.json")
NYFED_RECEIPT = Path("aics_data/research/nyfed_repo_original_archive_independent_rehash_2026_11_18.json")
OUT = Path("docs/audit/aics_repo_market_spreads_research_2026-11-18.json")
TYPES = ("SOFR", "BGCR", "TGCR")


class SourceError(ValueError):
    pass


def dec(v: object) -> Decimal:
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise SourceError("invalid rate value type")
    try:
        x = Decimal(str(v))
    except InvalidOperation:
        raise SourceError("invalid market rate decimal") from None
    if not x.is_finite():
        raise SourceError("nonfinite market rate")
    return x


def _zip(path: Path, claimed_sha: str) -> zipfile.ZipFile:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != claimed_sha:
        raise SourceError("original ZIP changed")
    return zipfile.ZipFile(path)


def derive(alfred_zip: Path, nyfed_zip: Path,
           alfred_receipt: Path = ALFRED_RECEIPT,
           nyfed_receipt: Path = NYFED_RECEIPT) -> dict:
    alfred = json.loads(alfred_receipt.read_text(encoding="utf-8"))
    nyfed = json.loads(nyfed_receipt.read_text(encoding="utf-8"))
    if (alfred.get("unique_original_raw_json_files") != 48
            or alfred.get("independent_historical_publication_time_pit_verified") is not False
            or alfred.get("all_original_file_sha256_verified") is not True
            or alfred.get("aics_index") is not None
            or nyfed.get("total_raw_rows") != 2997
            or nyfed.get("independent_original_byte_rehash_passed") is not True
            or nyfed.get("rate_publication_pit_attested") is not False
            or nyfed.get("aics_index") is not None):
        raise SourceError("input receipt not research-only or not verified")
    prices: dict[str, dict[str, dict]] = {}
    with _zip(nyfed_zip, nyfed["source_archive_zip_sha256"]) as z:
        expected = {"manifest.json"} | {
            f"nyfed_{t.lower()}_last_999_as_captured.json" for t in TYPES
        }
        if set(z.namelist()) != expected:
            raise SourceError("unexpected NY Fed archive inventory")
        for entry in nyfed["archive_files"]:
            t = entry["rate_type"]
            if t not in TYPES:
                raise SourceError("NY Fed type unknown")
            raw = z.read(entry["source_file"])
            if hashlib.sha256(raw).hexdigest() != entry["raw_sha256"]:
                raise SourceError("NY Fed source SHA mismatch")
            info = validate_nyfed(raw, t.lower(), dt.date(2026, 11, 18))
            if info["row_count"] != 999:
                raise SourceError("NY Fed archive row mismatch")
            prices[t] = {r["effectiveDate"]: r for r in json.loads(raw)["refRates"]}
        if set(prices) != set(TYPES):
            raise SourceError("one or more NY Fed sources missing")
        if hashlib.sha256(z.read("manifest.json")).hexdigest() != nyfed["source_archive_manifest_sha256"]:
            raise SourceError("NY Fed original manifest SHA mismatch")

    result = []
    missing = []
    source_asof_records: dict[str, dict[str, str]] = {}
    with _zip(alfred_zip, alfred["merged_artifact_zip_sha256"]) as z:
        if hashlib.sha256(z.read("manifest.json")).hexdigest() != alfred["merged_manifest_sha256"]:
            raise SourceError("ALFRED merged manifest changed")
        manifest = json.loads(z.read("manifest.json"))
        if (manifest.get("unique_genuine_asof_snapshots") != 48
                or manifest.get("independent_provider_publication_timestamp_pit") is not False
                or manifest.get("index_aics") is not None
                or manifest.get("promotion") != "BLOCKED"):
            raise SourceError("ALFRED merged source claimed certification")
        originals = {(e["series_id"], e["as_of"]): e for e in manifest["original_files"]}
        if len(originals) != 48:
            raise SourceError("ALFRED 48 genuine originals unavailable")
        for asof in month_ends():
            key = ("IORB", asof.isoformat())
            entry = originals[key]
            raw = z.read(entry["source_file"])
            if hashlib.sha256(raw).hexdigest() != entry["raw_sha256"]:
                raise SourceError("IORB as-of source SHA mismatch")
            validate_vintage(raw, "IORB", asof)
            source_asof_records[asof.isoformat()] = {
                r["date"]: r["value"] for r in json.loads(raw)["observations"]
                if r.get("value") not in (".", "", None)
            }
    for asof in month_ends():
        cutoff = asof - dt.timedelta(days=1)  # NEVER same-day effective date; release timing unproved
        shared = set.intersection(*(set(prices[t]) for t in TYPES))
        shared = {day for day in shared if dt.date.fromisoformat(day) <= cutoff}
        if not shared:
            missing.append({"as_of": asof.isoformat(), "reason": "no matched NY Fed effective date"})
            continue
        date = max(shared)
        iorb = source_asof_records[asof.isoformat()].get(date)
        if iorb is None:
            missing.append({"as_of": asof.isoformat(), "reason": "no IORB value on matched effective date"})
            continue
        # A stale NY Fed trading session cannot be silently forward-filled.
        if (asof - dt.date.fromisoformat(date)).days > 7:
            missing.append({"as_of": asof.isoformat(), "reason": "effective-date age exceeds 7 days"})
            continue
        series = {t: dec(prices[t][date]["percentRate"]) for t in TYPES}
        ir = dec(iorb)
        result.append({
            "as_of_month_end": asof.isoformat(),
            "nyfed_effective_date": date,
            "effective_date_to_asof_days": (asof - dt.date.fromisoformat(date)).days,
            "ibor_source_vintage_as_of": asof.isoformat(),
            "iorb_pct": str(ir),
            "sofr_pct": str(series["SOFR"]),
            "bgcr_pct": str(series["BGCR"]),
            "tgcr_pct": str(series["TGCR"]),
            "sofr_minus_iorb_bps": str((series["SOFR"] - ir) * 100),
            "bgcr_minus_iorb_bps": str((series["BGCR"] - ir) * 100),
            "tgcr_minus_iorb_bps": str((series["TGCR"] - ir) * 100),
            "sofr_minus_bgcr_bps": str((series["SOFR"] - series["BGCR"]) * 100),
            "historical_release_pit_attested": False,
            "node_score_eligible": False,
        })

    if len(result) + len(missing) != 24 or len(set(x["as_of_month_end"] for x in result)) != len(result):
        raise SourceError("invalid monthly alignment")
    spreads = [dec(x["sofr_minus_iorb_bps"]) for x in result]
    summary = {
        "valid_source_matched_months": len(result),
        "missing_months": len(missing),
        "minimum_sofr_minus_iorb_bps": str(min(spreads)) if spreads else None,
        "maximum_sofr_minus_iorb_bps": str(max(spreads)) if spreads else None,
        "mean_sofr_minus_iorb_bps": str(sum(spreads) / len(spreads)) if spreads else None,
        "zero_or_negative_sofr_minus_iorb_months": sum(x <= 0 for x in spreads),
    }
    return {
        "schema_version": "aics-repo-24-month-real-source-research-spread-v1",
        "research_cutoff": "2026-11-18",
        "provider_archive_sha256": {
            "NYFED": nyfed["source_archive_zip_sha256"],
            "ALFRED": alfred["merged_artifact_zip_sha256"],
        },
        "source_archive_artifact_ids": {
            "NYFED": nyfed["github_actions_artifact_id"],
            "ALFRED": alfred["merged_artifact_id"],
        },
        "series": list(TYPES) + ["IORB"],
        "monthly_source_aligned_observations": result,
        "missing_coverage": missing,
        "summary": summary,
        "synthetic_rows_created": 0,
        "NYFED_historical_release_pit_attested": False,
        "ALFRED_original_contemporaneous_snapshots_attested": False,
        "untouched_24m_oos": False,
        "independent_source_to_score_methodology": False,
        "node_stress_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
        "limitations": [
            "NY Fed past effective-date rate history was fetched in a current 2026-11-18 capture; retrospective revisions are possible.",
            "ALFRED 2024-2026 as-of vintages were queried and archived together on 2026-11-18.",
            "A conservative previous-effective-date filter reduces same-day leakage but does not independently certify original release times.",
            "Repo sampled-rate volumes overlap. Do not add SOFR BGCR TGCR volumes.",
            "These are observed basis-point research spreads, NOT AICS 0-100 node scores or a 24-month untouched OOS.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--nyfed-zip", type=Path, required=True)
    p.add_argument("--alfred-zip", type=Path, required=True)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    try:
        data = derive(args.alfred_zip, args.nyfed_zip)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        print("AICS Repo spread research BLOCKED:", type(exc).__name__)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_matched_months": len(data["monthly_source_aligned_observations"]),
                      "summary": data["summary"], "index_aics": None, "promotion": "BLOCKED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
