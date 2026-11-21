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


def validate_learning_provenance(rows: Sequence[Mapping]) -> dict:
    """Validate that learning rows have auditable, non-replay provenance."""
    issues: list[str] = []
    eligible = 0
    for index, row in enumerate(rows):
        source = str(row.get("source", ""))
        status = str(row.get("status", ""))
        if not source:
            issues.append(f"row_{index}_missing_source")
        if not row.get("as_of") and not row.get("generated_at"):
            issues.append(f"row_{index}_missing_timestamp")
        if source in {"simulated", "historical_replay", "replay"}:
            issues.append(f"row_{index}_non_independent_source")
        if status == "realized" and row.get("learning_eligible") is True:
            eligible += 1
    return {
        "source": "provenance_gate",
        "passed": not issues,
        "issues": issues,
        "learning_eligible_rows": eligible,
        "rows": len(rows),
    }


def validate_market_snapshot(
    snapshot: Mapping,
    *,
    max_age_hours: int = 48,
) -> dict:
    """Reject incomplete, impossible or stale market snapshots."""
    issues: list[str] = []
    prices = snapshot.get("prices", {})
    if not isinstance(prices, Mapping) or not prices:
        issues.append("missing_prices")
    else:
        for ticker, value in prices.items():
            try:
                if float(value) <= 0:
                    issues.append(f"{ticker}_non_positive_price")
            except (TypeError, ValueError):
                issues.append(f"{ticker}_invalid_price")
    as_of = snapshot.get("as_of")
    if not as_of:
        issues.append("missing_as_of")
    else:
        try:
            age_hours = (
                datetime.utcnow() - datetime.fromisoformat(str(as_of))
            ).total_seconds() / 3600
            if age_hours < -1:
                issues.append("as_of_in_future")
            elif age_hours > max_age_hours:
                issues.append("market_snapshot_stale")
        except ValueError:
            issues.append("invalid_as_of")
    return {
        "source": "market_snapshot_gate",
        "passed": not issues,
        "issues": issues,
        "max_age_hours": max_age_hours,
    }
