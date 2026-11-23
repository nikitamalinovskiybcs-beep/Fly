"""Transparent classical baselines for fixed-24m Phoenix validation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

import numpy as np

from src.math_evaluation import expected_calibration_error, log_loss


def empirical_probability(outcomes: Sequence[float]) -> float:
    """Return the leakage-safe constant probability for one evaluation set."""
    if not outcomes:
        raise ValueError("outcomes must not be empty")
    values = np.asarray(outcomes, dtype=float)
    if np.any((values < 0) | (values > 1)):
        raise ValueError("outcomes must be between 0 and 1")
    return float(np.mean(values))


def evaluate_against_empirical_baseline(
    predictions: Sequence[float],
    outcomes: Sequence[float],
) -> dict[str, float | None]:
    """Evaluate a candidate and its empirical constant baseline."""
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    if not outcomes:
        return {
            "brier": None,
            "log_loss": None,
            "ece": None,
            "empirical_baseline_brier": None,
            "empirical_baseline_log_loss": None,
            "empirical_baseline_ece": None,
            "brier_vs_baseline_pct": None,
        }
    predicted = np.clip(np.asarray(predictions, dtype=float), 0.0, 1.0)
    observed = np.asarray(outcomes, dtype=float)
    baseline_probability = empirical_probability(outcomes)
    baseline = [baseline_probability] * len(outcomes)
    brier = float(np.mean((predicted - observed) ** 2))
    baseline_brier = float(np.mean((baseline_probability - observed) ** 2))
    return {
        "brier": round(brier, 6),
        "log_loss": round(log_loss(predicted.tolist(), outcomes), 6),
        "ece": round(expected_calibration_error(predicted.tolist(), outcomes), 6),
        "empirical_baseline_brier": round(baseline_brier, 6),
        "empirical_baseline_log_loss": round(log_loss(baseline, outcomes), 6),
        "empirical_baseline_ece": round(
            expected_calibration_error(baseline, outcomes), 6
        ),
        "brier_vs_baseline_pct": round(
            (baseline_brier - brier) / baseline_brier * 100, 2
        ) if baseline_brier else None,
        "mean_predicted_loss": round(float(np.mean(predicted)), 6),
        "mean_observed_loss": round(float(np.mean(observed)), 6),
    }


def fixed_24m_gate(
    anchor_metrics: Iterable[Mapping[str, object]],
    *,
    max_ece: float = 0.05,
) -> dict[str, object]:
    """Require a candidate to beat the baseline at every fixed-24m anchor."""
    anchors = list(anchor_metrics)
    checks = [
        (
            float(anchor.get("brier_vs_baseline_pct", -float("inf"))) > 0
            and float(anchor.get("log_loss", float("inf")))
            <= float(anchor.get("empirical_baseline_log_loss", -float("inf")))
            and float(anchor.get("ece", float("inf"))) <= max_ece
        )
        for anchor in anchors
    ]
    return {
        "passed": bool(checks) and all(checks),
        "anchors_checked": len(checks),
        "passed_anchors": sum(checks),
        "max_ece": max_ece,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
