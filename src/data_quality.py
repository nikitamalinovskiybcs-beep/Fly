"""Deterministic quality checks for free market and macro data sources."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime


def compare_price_sources(
    primary: Mapping[str, Sequence[float]],
    secondary: Mapping[str, Sequence[float]],
    max_relative_gap: float = 0.02,
) -> dict:
    """Compare overlapping price observations without selecting a winner."""
    tickers = sorted(set(primary) & set(secondary))
    checks: dict[str, dict] = {}
    for ticker in tickers:
        left = list(primary[ticker])
        right = list(secondary[ticker])
        overlap = min(len(left), len(right))
        if overlap == 0:
            checks[ticker] = {"passed": False, "reason": "no_overlap"}
            continue
        gaps = [
            abs(float(left[index]) - float(right[index]))
            / max(abs(float(right[index])), 1e-12)
            for index in range(overlap)
        ]
        max_gap = max(gaps)
        checks[ticker] = {
            "passed": max_gap <= max_relative_gap,
            "overlap": overlap,
            "max_relative_gap": round(max_gap, 6),
        }
    return {
        "source": "observed_quality_check",
        "tickers": len(tickers),
        "passed": bool(tickers) and all(item["passed"] for item in checks.values()),
        "checks": checks,
        "max_relative_gap": max_relative_gap,
    }


def validate_macro_snapshot(snapshot: Mapping) -> dict:
    """Reject impossible or stale macro observations before model use."""
    issues: list[str] = []
    vix = snapshot.get("vix")
    if vix is not None and not 0 < float(vix) < 200:
        issues.append("vix_out_of_range")
    for field in ("rate_10y", "rate_2y", "fed_rate"):
        value = snapshot.get(field)
        if value is not None and not -5 < float(value) < 30:
            issues.append(f"{field}_out_of_range")
    as_of = snapshot.get("as_of")
    if as_of:
        try:
            age_days = (datetime.utcnow() - datetime.fromisoformat(str(as_of))).days
            if age_days > 14:
                issues.append("macro_snapshot_stale")
        except ValueError:
            issues.append("invalid_as_of")
    return {
        "source": "observed_quality_check",
        "passed": not issues,
        "issues": issues,
    }
