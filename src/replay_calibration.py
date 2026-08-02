"""Leakage-safe calibration helpers for historical replay research."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


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
