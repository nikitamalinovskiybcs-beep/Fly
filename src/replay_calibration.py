"""Leakage-safe calibration helpers for historical replay research."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from src.math_evaluation import brier_score, expected_calibration_error, log_loss


def fit_histogram_calibrator(
    predictions: Sequence[float],
    outcomes: Sequence[int],
    bins: int = 5,
) -> list[float]:
    """Fit fixed-width probability-bin rates using train data only."""
    if bins < 2:
        raise ValueError("bins must be at least 2")
    prior = float(np.mean(outcomes)) if outcomes else 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    rates: list[float] = []
    for index in range(bins):
        values = [
            outcome
            for prediction, outcome in zip(predictions, outcomes)
            if edges[index] <= prediction
            and (prediction < edges[index + 1] or index == bins - 1)
        ]
        rates.append(float(np.mean(values)) if values else prior)
    return rates


def apply_histogram_calibrator(
    predictions: Sequence[float],
    rates: Sequence[float],
) -> list[float]:
    """Apply a train-fitted fixed-width histogram calibrator."""
    bins = len(rates)
    if bins < 2:
        raise ValueError("rates must contain at least two bins")
    return [
        float(rates[min(bins - 1, int(np.clip(prediction, 0.0, 1.0) * bins))])
        for prediction in predictions
    ]


def walk_forward_histogram_calibration(
    predictions: Sequence[float],
    outcomes: Sequence[int],
    *,
    initial_train: int = 20,
    bins: int = 5,
) -> dict[str, object]:
    """Evaluate train-only calibration on chronological observations.

    Each test observation is calibrated only with outcomes strictly before it.
    The result is a research candidate and never changes production parameters.
    """
    if len(predictions) != len(outcomes) or len(predictions) <= initial_train:
        raise ValueError("predictions must contain more than initial_train rows")
    if initial_train < bins:
        raise ValueError("initial_train must be at least bins")

    raw = [float(value) for value in predictions[initial_train:]]
    actual = [int(value) for value in outcomes[initial_train:]]
    calibrated: list[float] = []
    for index, prediction in enumerate(raw):
        train_end = initial_train + index
        rates = fit_histogram_calibrator(
            predictions[:train_end],
            outcomes[:train_end],
            bins=bins,
        )
        calibrated.extend(apply_histogram_calibrator([prediction], rates))

    return {
        "status": "research_only",
        "initial_train": initial_train,
        "bins": bins,
        "oos_observations": len(actual),
        "raw": {
            "brier": brier_score(raw, actual),
            "log_loss": log_loss(raw, actual),
            "ece": expected_calibration_error(raw, actual),
        },
        "calibrated": {
            "brier": brier_score(calibrated, actual),
            "log_loss": log_loss(calibrated, actual),
            "ece": expected_calibration_error(calibrated, actual),
        },
        "production_weights_changed": False,
        "verdict_mutated": False,
    }


def diagnose_calibration_bottleneck(result: dict[str, object]) -> dict[str, object]:
    """Rank the dominant calibration failure for the next research run."""
    raw = result.get("raw", {})
    calibrated = result.get("calibrated", {})
    ece = float(calibrated.get("ece", 1.0))
    log_loss_change = float(calibrated.get("log_loss", 1.0)) - float(
        raw.get("log_loss", 0.0),
    )
    if ece > 0.05:
        priority = "reduce_calibration_error"
    elif log_loss_change >= 0:
        priority = "improve_log_loss"
    else:
        priority = "expand_fixed_24m_sample"
    return {
        "priority": priority,
        "calibrated_ece": ece,
        "log_loss_change": round(log_loss_change, 8),
        "action": {
            "reduce_calibration_error": "add leakage-safe labels and regime features",
            "improve_log_loss": "test regularized calibration candidates",
            "expand_fixed_24m_sample": "collect more settled 24m outcomes",
        }[priority],
        "research_only": True,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
