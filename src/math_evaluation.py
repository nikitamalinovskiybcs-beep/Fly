"""Mathematical evaluation metrics for structured-product predictions."""

from __future__ import annotations

from math import log
from statistics import mean
from typing import Sequence


def brier_score(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    """Return mean squared probability error for binary outcomes."""
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probabilities and outcomes must have equal non-zero length")
    if any(probability < 0 or probability > 1 for probability in probabilities):
        raise ValueError("probabilities must be between 0 and 1")
    if any(outcome not in (0, 1) for outcome in outcomes):
        raise ValueError("outcomes must be binary")
    return mean((probability - outcome) ** 2 for probability, outcome in zip(probabilities, outcomes))


def log_loss(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    """Return clipped Bernoulli negative log likelihood."""
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probabilities and outcomes must have equal non-zero length")
    clipped = [min(max(probability, 1e-12), 1.0 - 1e-12) for probability in probabilities]
    return -mean(
        outcome * log(probability) + (1 - outcome) * log(1 - probability)
        for probability, outcome in zip(clipped, outcomes)
    )


def expected_calibration_error(
    probabilities: Sequence[float],
    outcomes: Sequence[int],
    bins: int = 10,
) -> float:
    """Return equally spaced expected calibration error."""
    if bins < 1:
        raise ValueError("bins must be positive")
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probabilities and outcomes must have equal non-zero length")
    total = len(probabilities)
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        members = [
            (probability, outcome)
            for probability, outcome in zip(probabilities, outcomes)
            if lower <= probability < upper or (
                index == bins - 1 and probability == upper
            )
        ]
        if members:
            confidence = mean(probability for probability, _ in members)
            accuracy = mean(outcome for _, outcome in members)
            error += len(members) / total * abs(confidence - accuracy)
    return error
