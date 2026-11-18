#!/usr/bin/env python3
"""Capture dated ALFRED as-of snapshots for IORB and industrial power PPI.

Research-only: 24 actual monthly as-of queries (ending 2026-10-31) and
observations from 2018 onward. A 2018 observation retrieved today is NOT
evidence we archived its 2018 release; no historical backfill/promotion.
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Mapping

API = "https://api.stlouisfed.org/fred/series/observations"
SERIES = {"IORB": "Repo", "WPU0543": "Power/Data Centers"}
FREEZE_AS_OF = dt.date(2026, 11, 18)
OBSERVATION_START = "2018-01-01"
DATA_DIR = Path("aics_data/pit/free_gaps_2026_11_18")
MAX_RESPONSE_BYTES = 8_000_000


class VintageValidationError(ValueError):
    pass


def month_ends(count: int = 24, end: dt.date = dt.date(2026, 10, 31)) -> tuple[dt.date, ...]:
    if end.day != calendar.monthrange(end.year, end.month)[1]:
        raise ValueError("end must be month-end")
    months = []
    for i in range(count - 1, -1, -1):
        total = end.year * 12 + end.month - 1 - i
        year, month = divmod(total, 12)
        month += 1
        months.append(dt.date(year, month, calendar.monthrange(year, month)[1]))
    return tuple(months)


def validate_vintage(raw: bytes, series_id: str, as_of: dt.date) -> dict:
    if series_id not in SERIES or len(raw) == 0 or len(raw) > MAX_RESPONSE_BYTES:
        raise VintageValidationError("invalid source type or length")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise VintageValidationError("non-JSON ALFRED response") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("observations"), list):
        raise VintageValidationError("missing ALFRED observations")
    observations = payload["observations"]
    if (not observations or len(observations) != payload.get("count")
            or len(observations) > 10000):
        raise VintageValidationError("ALFRED snapshot incomplete or unexpectedly large")
    if (payload.get("realtime_start") != as_of.isoformat()
            or payload.get("realtime_end") != as_of.isoformat()):
        raise VintageValidationError("ALFRED top-level as-of mismatch")
    dates = []
    valid_count = 0
    for observation in observations:
        try:
            day = dt.date.fromisoformat(observation["date"])
            start = dt.date.fromisoformat(observation["realtime_start"])
            end = dt.date.fromisoformat(observation["realtime_end"])
        except (TypeError, KeyError, ValueError):
            raise VintageValidationError("invalid observation or vintage date") from None
        if (day > as_of or day < dt.date.fromisoformat(OBSERVATION_START)
                or not start <= as_of <= end):
            raise VintageValidationError("ALFRED observation or historical vintage look-ahead")
        dates.append(day)
        if observation.get("value") not in ("", ".", None):
            try:
                value = float(observation["value"])
            except (ValueError, TypeError):
                raise VintageValidationError("non-numeric official observation") from None
            if not -1000 < value < 100000:
                raise VintageValidationError("out-of-range official observation")
            valid_count += 1
    if dates != sorted(set(dates)):
        raise VintageValidationError("duplicate or out-of-order observation dates")
    return {
        "series_id": series_id,
        "candidate_node": SERIES[series_id],
        "as_of": as_of.isoformat(),
        "observation_start": OBSERVATION_START,
        "rows": len(observations),
        "non_missing_observations": valid_count,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_bytes": len(raw),
        "alfrED_as_of_request": True,
        "independent_provider_release_pit_attested": False,
        "stress_score_eligible": False,
    }


def collect(
    key: str,
    *,
    dest: Path = DATA_DIR,
    snapshots: tuple[dt.date, ...] | None = None,
    transport: Callable = urllib.request.urlopen,
    captured_at: dt.datetime | None = None,
    pace_seconds: float = 0.3,
) -> dict:
    if not key or not key.strip():
        raise ValueError("FRED_API_KEY is absent")
    snapshots = snapshots if snapshots is not None else month_ends()
    if not snapshots or len(snapshots) > 24 or snapshots != tuple(sorted(set(snapshots))):
        raise ValueError("invalid snapshot schedule")
    if max(snapshots) > FREEZE_AS_OF:
        raise ValueError("future ALFRED snapshot forbidden")
    now = captured_at or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("capture time must carry timezone")

    rows = []
    errors = []
    staged = []
    for series in SERIES:
        for as_of in snapshots:
            query = urllib.parse.urlencode({
                "series_id": series, "api_key": key.strip(),
                "file_type": "json",
                "observation_start": OBSERVATION_START,
                "observation_end": as_of.isoformat(),
                "realtime_start": as_of.isoformat(),
                "realtime_end": as_of.isoformat(),
                "limit": 10000, "offset": 0,
                "sort_order": "asc",
            })
            request = urllib.request.Request(API + "?" + query, headers={
                "Accept": "application/json", "User-Agent": "AICS PIT Source Archive/1.0",
            })
            try:
                for attempt in range(3):
                    try:
                        with transport(request, timeout=40) as response:
                            raw = response.read(MAX_RESPONSE_BYTES + 1)
                        break
                    except urllib.error.HTTPError as exc:
                        # Retry only temporary upstream errors, never replace or backfill.
                        if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                            raise
                        time.sleep(attempt + 1)
                if key.encode("utf-8") in raw:
                    raise VintageValidationError("provider response reflects credential")
                entry = validate_vintage(raw, series, as_of)
                filename = f"{series}_asof_{as_of.isoformat()}.json"
                staged.append((filename, raw))
                rows.append({**entry, "raw_file": filename, "status": "downloaded_unverified"})
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                    OSError, VintageValidationError) as exc:
                # Key, request query, and response body MUST NOT appear in logs.
                status = f"HTTP_{exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
                errors.append({"series_id": series, "as_of": as_of.isoformat(), "status": status})
                rows.append({"series_id": series, "as_of": as_of.isoformat(),
                             "status": "BLOCKED", "failure_code": status,
                             "stress_score_eligible": False})
            if pace_seconds:
                time.sleep(pace_seconds)
    dest.mkdir(parents=True, exist_ok=True)
    for name, raw in staged:
        (dest / name).write_bytes(raw)
    report = {
        "schema_version": "aics-alfred-iorb-power-asof-research-v1",
        "research_as_of": FREEZE_AS_OF.isoformat(),
        "captured_at_utc": now.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "provider": "FRED/ALFRED",
        "snapshot_dates": [x.isoformat() for x in snapshots],
        "historical_observation_start": OBSERVATION_START,
        "series_results": rows, "blocked": errors,
        "successful_snapshots": len(staged),
        "expected_snapshots": len(snapshots) * len(SERIES),
        "all_sources_downloaded": not errors and len(staged) == len(snapshots) * len(SERIES),
        "provider_publication_lag_pit_attested": False,
        "independent_24m_oos": False,
        "node_stress_scores": {"Repo": None, "Power/Data Centers": None},
        "aics_index": None, "promotion": "BLOCKED",
        "notes": (
            "Each monthly as-of response is raw retroactive ALFRED API research evidence. "
            "Its date gate is not independent contemporaneous release attestation. "
            "A 2018 observation timestamp must not be relabeled as a 2018 vintage. "
            "Historical revision dates, IORB market-hours release timing, PPI release dates, "
            "methodology and OOS remain unverified."
        ),
    }
    (dest / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        print("ALFRED gap-collection BLOCKED: FRED_API_KEY missing")
        return 1
    result = collect(key, dest=args.dest)
    print(json.dumps({
        "source_series": list(SERIES), "captured": result["successful_snapshots"],
        "expected": result["expected_snapshots"], "blocked": len(result["blocked"]),
        "as_of_pit_independently_attested": False, "aics_index": None,
        "promotion": "BLOCKED",
    }))
    return 0 if result["all_sources_downloaded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
