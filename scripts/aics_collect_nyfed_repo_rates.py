#!/usr/bin/env python3
"""Archive exact New York Fed secured-rate JSON bytes, research-only.

This is a CURRENT capture of retrospective SOFR/BGCR/TGCR data, NOT an
archived sequence of real-time publication vintages. No historical PIT
attestation, rate spread to IORB, stress score or trading inference.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

BASE_URL = "https://markets.newyorkfed.org/api/rates/secured"
TYPES = ("sofr", "bgcr", "tgcr")
ROW_LIMIT = 1500
MAX_BYTES = 8_000_000
FIELDS = ("effectiveDate", "type", "percentRate", "volumeInBillions")
RAW_DIR = Path("aics_data/nyfed_repo")
MANIFEST = Path("aics_data/nyfed_repo/manifest.json")


class SourceValidationError(ValueError):
    pass


def validate_rows(raw: bytes, rate_type: str, captured_on: dt.date) -> dict:
    if rate_type not in TYPES or len(raw) < 3 or len(raw) > MAX_BYTES:
        raise SourceValidationError("invalid rate type or response size")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise SourceValidationError("unparseable official response") from None
    if not isinstance(data, dict) or "refRates" not in data or not isinstance(data["refRates"], list):
        raise SourceValidationError("missing official refRates array")
    rows = data["refRates"]
    if not rows or len(rows) > ROW_LIMIT:
        raise SourceValidationError("unexpected official series length")
    observed_dates: list[dt.date] = []
    for record in rows:
        if not isinstance(record, dict) or any(field not in record for field in FIELDS):
            raise SourceValidationError("missing official observation fields")
        if record["type"] != rate_type.upper():
            raise SourceValidationError("official rate type mismatch")
        try:
            day = dt.date.fromisoformat(record["effectiveDate"])
        except (ValueError, TypeError):
            raise SourceValidationError("invalid effective date") from None
        if day > captured_on:
            raise SourceValidationError("future effective date")
        observed_dates.append(day)
        for field in ("percentRate", "volumeInBillions"):
            value = record[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise SourceValidationError("invalid numeric observation")
        if not -20 <= record["percentRate"] <= 100 or record["volumeInBillions"] < 0:
            raise SourceValidationError("implausible official rate or volume")
    if len(set(observed_dates)) != len(observed_dates):
        raise SourceValidationError("duplicate effective date")
    if observed_dates != sorted(observed_dates, reverse=True):
        raise SourceValidationError("non-descending official history")
    return {
        "rate_type": rate_type.upper(),
        "source_url": f"{BASE_URL}/{rate_type}/last/{ROW_LIMIT}.json",
        "row_count": len(rows),
        "oldest_effective_date": min(observed_dates).isoformat(),
        "newest_effective_date": max(observed_dates).isoformat(),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_bytes": len(raw),
        "independently_attested_historical_pit": False,
        "original_publication_timestamps_verified": False,
        "aics_score_eligible": False,
    }


def collect(
    dest: Path = RAW_DIR,
    *,
    fetched_at: dt.datetime | None = None,
    transport: Callable = urllib.request.urlopen,
) -> dict:
    now = fetched_at or dt.datetime.now(dt.timezone.utc)
    if not now.tzinfo:
        raise ValueError("fetched_at must have a timezone")
    now = now.astimezone(dt.timezone.utc)
    capture_day = now.date()
    checked: list[tuple[str, bytes, dict]] = []
    for rate_type in TYPES:
        url = f"{BASE_URL}/{rate_type}/last/{ROW_LIMIT}.json"
        request = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "AICS-Research-Source-Archive/1.0",
        })
        with transport(request, timeout=40) as response:
            data = response.read(MAX_BYTES + 1)
        metadata = validate_rows(data, rate_type, capture_day)
        checked.append((rate_type, data, metadata))

    # Only persist once *all three* official endpoints have been validated.
    dest.mkdir(parents=True, exist_ok=True)
    saved = []
    for rate_type, raw, metadata in checked:
        filename = f"nyfed_{rate_type}_last_{ROW_LIMIT}_as_captured.json"
        (dest / filename).write_bytes(raw)
        saved.append({**metadata, "file": filename})
    manifest = {
        "schema_version": "aics-nyfed-secured-rates-current-capture-v1",
        "captured_at_utc": now.isoformat().replace("+00:00", "Z"),
        "primary_source": "Federal Reserve Bank of New York Markets Data API",
        "series": saved,
        "candidate_node": "Repo",
        "rate_spread_to_iorb_bps": None,
        "historical_pit_attested": False,
        "raw_provider_publication_vintage": False,
        "independent_24m_oos": False,
        "node_stress_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
        "trading_signal": None,
        "notes": (
            "These current snapshots can contain revised retrospective effective-date observations. "
            "Do not assume effectiveDate is the release timestamp. Verify historical publication "
            "times/revisions and ALFRED IORB vintages before any walk-forward calculation. "
            "Check New York Fed Terms of Use before redistributing raw bytes."
        ),
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    try:
        result = collect(dest=args.dest)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError,
            TimeoutError, SourceValidationError) as exc:
        # Fail closed; never print a partial success or synthesize records.
        print("NY Fed official source archival BLOCKED:", type(exc).__name__)
        return 1
    print(json.dumps({
        "status": "ARCHIVED_CURRENT_RESEARCH_ONLY",
        "source_rows": {x["rate_type"]: x["row_count"] for x in result["series"]},
        "raw_sha256": {x["rate_type"]: x["raw_sha256"] for x in result["series"]},
        "historical_pit_attested": False,
        "index_aics": None,
        "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
