"""Small, deterministic quality gates for Phoenix research artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
import hashlib
import json

import numpy as np


SAFETY_FLAGS = {
    "production_weights_changed": False,
    "verdict_mutated": False,
    "trades_created": False,
}


def immutable_safety_flags() -> dict[str, bool]:
    return dict(SAFETY_FLAGS)


def snapshot_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_market_observations(
    observations: Sequence[Mapping[str, object]],
    *,
    as_of: date,
    max_age_days: int = 5,
) -> dict[str, object]:
    errors: list[str] = []
    for index, observation in enumerate(observations):
        source = observation.get("source")
        observed_at = observation.get("as_of")
        if not source:
            errors.append(f"{index}:missing_source")
        if not observed_at:
            errors.append(f"{index}:missing_as_of")
            continue
        try:
            observed_date = date.fromisoformat(str(observed_at)[:10])
        except ValueError:
            errors.append(f"{index}:invalid_as_of")
            continue
        if observed_date > as_of:
            errors.append(f"{index}:future_dated")
        elif (as_of - observed_date).days > max_age_days:
            errors.append(f"{index}:stale")
    return {
        "passed": not errors,
        "checked": len(observations),
        "errors": errors,
        **immutable_safety_flags(),
    }


def validate_payoff_bounds(
    *,
    notional: float,
    cashflows: Sequence[float],
    terminal_redemption: float,
) -> dict[str, object]:
    errors: list[str] = []
    if notional <= 0:
        errors.append("notional_not_positive")
    if any(value < 0 for value in cashflows):
        errors.append("negative_cashflow")
    if terminal_redemption < 0:
        errors.append("negative_redemption")
    if any(value != value for value in cashflows):
        errors.append("nan_cashflow")
    if terminal_redemption != terminal_redemption:
        errors.append("nan_redemption")
    return {
        "passed": not errors,
        "errors": errors,
        "total_cashflows": round(float(sum(cashflows)), 8),
        "terminal_redemption": round(float(terminal_redemption), 8),
        **immutable_safety_flags(),
    }


def autocall_metrics(outcomes: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Summarize realized or explicitly labelled research outcomes."""
    if not outcomes:
        return {
            "status": "insufficient_evidence",
            "sample_size": 0,
            **immutable_safety_flags(),
        }
    autocalls = [
        row for row in outcomes if row.get("outcome_type") == "autocall"
    ]
    first_observations = [
        int(row["autocall_observation"])
        for row in autocalls
        if row.get("autocall_observation") is not None
    ]
    return {
        "status": "research_summary",
        "sample_size": len(outcomes),
        "autocall_count": len(autocalls),
        "autocall_rate": round(len(autocalls) / len(outcomes), 6),
        "mean_first_autocall_observation": (
            round(sum(first_observations) / len(first_observations), 6)
            if first_observations
            else None
        ),
        **immutable_safety_flags(),
    }


def evidence_partition(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    counts = {
        "realized": 0,
        "verified_quote": 0,
        "historical_replay": 0,
        "simulation": 0,
        "unverified": 0,
    }
    for row in rows:
        status = str(row.get("evidence_status", "unverified"))
        if status in counts:
            counts[status] += 1
        else:
            counts["unverified"] += 1
    return counts


def require_fixed_24m_anchors(anchors: Mapping[str, object]) -> dict[str, object]:
    required = {"6", "12", "18", "24"}
    present = {str(anchor) for anchor in anchors}
    missing = sorted(required - present, key=int)
    return {
        "passed": not missing,
        "required_anchors": sorted(required, key=int),
        "missing_anchors": missing,
        **immutable_safety_flags(),
    }


def validate_correlation_matrix(matrix: Sequence[Sequence[float]]) -> dict[str, object]:
    values = np.asarray(matrix, dtype=float)
    errors: list[str] = []
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        errors.append("not_square")
    elif not np.allclose(values, values.T, atol=1e-8):
        errors.append("not_symmetric")
    elif not np.allclose(np.diag(values), 1.0, atol=1e-8):
        errors.append("diagonal_not_one")
    elif np.min(np.linalg.eigvalsh(values)) < -1e-8:
        errors.append("not_positive_semidefinite")
    return {
        "passed": not errors,
        "dimension": int(values.shape[0]) if values.ndim == 2 else 0,
        "errors": errors,
        **immutable_safety_flags(),
    }


def worst_of_driver(levels: Mapping[str, float]) -> dict[str, object]:
    if not levels:
        return {"status": "insufficient_data", **immutable_safety_flags()}
    ticker, level = min(levels.items(), key=lambda item: item[1])
    return {
        "status": "research_summary",
        "ticker": ticker,
        "normalized_level": round(float(level), 8),
        **immutable_safety_flags(),
    }


def quote_fit_gate(
    *,
    model_coupon_pa: float,
    dealer_coupon_pa: float,
    tolerance_pa: float,
) -> dict[str, object]:
    error = abs(float(model_coupon_pa) - float(dealer_coupon_pa))
    return {
        "passed": error <= tolerance_pa,
        "absolute_error_pa": round(error, 8),
        "tolerance_pa": tolerance_pa,
        "evidence_status": "quote_fit_research",
        **immutable_safety_flags(),
    }


def confidence_interval(
    values: Sequence[float],
    *,
    z_score: float = 1.96,
) -> dict[str, object]:
    if not values:
        return {"status": "insufficient_evidence", **immutable_safety_flags()}
    array = np.asarray(values, dtype=float)
    mean = float(np.mean(array))
    standard_error = (
        float(np.std(array, ddof=1) / np.sqrt(len(array)))
        if len(array) > 1
        else 0.0
    )
    return {
        "status": "research_summary",
        "n": len(array),
        "mean": round(mean, 8),
        "lower": round(mean - z_score * standard_error, 8),
        "upper": round(mean + z_score * standard_error, 8),
        **immutable_safety_flags(),
    }


def monte_carlo_convergence(
    path_counts: Sequence[int],
    estimates: Sequence[float],
    standard_errors: Sequence[float],
) -> dict[str, object]:
    if not (len(path_counts) == len(estimates) == len(standard_errors)):
        raise ValueError("convergence inputs must have equal length")
    if not path_counts:
        return {"status": "insufficient_evidence", **immutable_safety_flags()}
    return {
        "status": "research_summary",
        "points": [
            {
                "paths": int(paths),
                "estimate": round(float(estimate), 8),
                "standard_error": round(float(error), 8),
            }
            for paths, estimate, error in zip(
                path_counts, estimates, standard_errors
            )
        ],
        "non_increasing_standard_error": all(
            later <= earlier + 1e-12
            for earlier, later in zip(standard_errors, standard_errors[1:])
        ),
        **immutable_safety_flags(),
    }


def validate_basket_symbols(
    basket: Sequence[str],
    available_symbols: Sequence[str],
) -> dict[str, object]:
    normalized = [str(symbol).upper() for symbol in basket]
    available = {str(symbol).upper() for symbol in available_symbols}
    missing = sorted(set(normalized) - available)
    duplicates = sorted(
        {symbol for symbol in normalized if normalized.count(symbol) > 1}
    )
    return {
        "passed": bool(normalized) and not missing and not duplicates,
        "size": len(normalized),
        "missing_symbols": missing,
        "duplicate_symbols": duplicates,
        **immutable_safety_flags(),
    }


def validate_observation_schedule(
    observations: Sequence[str],
) -> dict[str, object]:
    errors: list[str] = []
    parsed: list[date] = []
    for value in observations:
        try:
            parsed.append(date.fromisoformat(str(value)[:10]))
        except ValueError:
            errors.append("invalid_observation_date")
    if any(later <= earlier for earlier, later in zip(parsed, parsed[1:])):
        errors.append("not_strictly_increasing")
    return {
        "passed": bool(parsed) and not errors,
        "count": len(parsed),
        "errors": errors,
        **immutable_safety_flags(),
    }


def feature_lineage(
    *,
    model_id: str,
    model_version: str,
    data_snapshot: Mapping[str, object],
    feature_names: Sequence[str],
) -> dict[str, object]:
    return {
        "model_id": model_id,
        "model_version": model_version,
        "data_snapshot_hash": snapshot_hash(data_snapshot),
        "feature_names": sorted(set(feature_names)),
        "lineage_status": "recorded",
        **immutable_safety_flags(),
    }


def seed_sensitivity(
    estimates: Mapping[int, float],
    *,
    tolerance: float,
) -> dict[str, object]:
    values = list(estimates.values())
    spread = max(values) - min(values) if values else None
    return {
        "status": "research_summary" if values else "insufficient_evidence",
        "seed_count": len(values),
        "spread": round(float(spread), 8) if spread is not None else None,
        "passed": spread is not None and spread <= tolerance,
        "tolerance": tolerance,
        **immutable_safety_flags(),
    }


def sensitivity_grid(
    *,
    parameter: str,
    values: Sequence[float],
    estimates: Sequence[float],
) -> dict[str, object]:
    if len(values) != len(estimates):
        raise ValueError("sensitivity inputs must have equal length")
    return {
        "status": "research_summary" if values else "insufficient_evidence",
        "parameter": parameter,
        "points": [
            {"value": float(value), "estimate": float(estimate)}
            for value, estimate in zip(values, estimates)
        ],
        **immutable_safety_flags(),
    }


def agent_evidence_gate(
    *,
    provider: str,
    status: str,
    evidence_ids: Sequence[str],
    confidence: float | None,
) -> dict[str, object]:
    errors: list[str] = []
    if not provider:
        errors.append("missing_provider")
    if status not in {"completed", "timeout", "error", "skipped"}:
        errors.append("invalid_status")
    if status == "completed" and not evidence_ids:
        errors.append("completed_without_evidence_ids")
    if confidence is not None and not 0.0 <= confidence <= 1.0:
        errors.append("confidence_out_of_bounds")
    return {
        "passed": not errors,
        "provider": provider,
        "status": status,
        "errors": errors,
        **immutable_safety_flags(),
    }


def monotonicity_check(
    lower_value: float,
    higher_value: float,
    *,
    expected: str,
) -> dict[str, object]:
    if expected == "increasing":
        passed = higher_value >= lower_value
    elif expected == "decreasing":
        passed = higher_value <= lower_value
    else:
        raise ValueError("expected must be increasing or decreasing")
    return {
        "passed": passed,
        "expected": expected,
        "lower_value": lower_value,
        "higher_value": higher_value,
        **immutable_safety_flags(),
    }
