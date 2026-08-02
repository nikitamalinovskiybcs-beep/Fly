"""Transparent analytical benchmarks for worst-of barrier risk."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

import numpy as np
from scipy.stats import multivariate_normal, norm


def _terminal_probability(volatility: float, barrier: float, years: float) -> float:
    if volatility <= 0 or years <= 0:
        return 0.0
    threshold = (
        math.log(barrier) + 0.5 * volatility * volatility * years
    ) / (volatility * math.sqrt(years))
    return float(norm.cdf(threshold))


def analytical_worst_of_probability(
    prices: Mapping[str, Sequence[float]],
    basket: Sequence[str],
    barrier: float = 0.65,
    term_months: int = 6,
) -> dict:
    """Estimate terminal worst-of breach with a Gaussian copula.

    This is an analytical research benchmark, not a barrier Monte Carlo
    valuation. The robust interval perturbs annualized volatility by 20%.
    """
    returns = []
    for ticker in basket:
        values = np.asarray(prices[ticker], dtype=float)
        if len(values) < 30:
            continue
        returns.append(np.diff(np.log(values)))
    if len(returns) != len(basket):
        return {"status": "insufficient_data", "source": "analytical_quant"}
    matrix = np.asarray(returns, dtype=float)
    vols = np.std(matrix, axis=1, ddof=1) * math.sqrt(252)
    correlation = np.corrcoef(matrix)
    correlation = np.nan_to_num(correlation, nan=0.0)
    correlation = (correlation + correlation.T) / 2
    np.fill_diagonal(correlation, 1.0)
    years = term_months / 12
    probabilities = np.array(
        [_terminal_probability(vol, barrier, years) for vol in vols],
    )
    thresholds = np.array(
        [
            norm.ppf(np.clip(probability, 1e-8, 1 - 1e-8))
            for probability in probabilities
        ],
    )
    joint_survival = float(
        multivariate_normal.cdf(-thresholds, mean=np.zeros(len(basket)), cov=correlation),
    )
    probability = float(np.clip(1.0 - joint_survival, 0.0, 1.0))
    lower_vols = vols * 0.8
    upper_vols = vols * 1.2
    lower = 1.0 - float(
        multivariate_normal.cdf(
            -np.array(
                [
                    norm.ppf(
                        np.clip(_terminal_probability(vol, barrier, years), 1e-8, 1 - 1e-8),
                    )
                    for vol in lower_vols
                ],
            ),
            mean=np.zeros(len(basket)),
            cov=correlation,
        ),
    )
    upper = 1.0 - float(
        multivariate_normal.cdf(
            -np.array(
                [
                    norm.ppf(
                        np.clip(_terminal_probability(vol, barrier, years), 1e-8, 1 - 1e-8),
                    )
                    for vol in upper_vols
                ],
            ),
            mean=np.zeros(len(basket)),
            cov=correlation,
        ),
    )
    return {
        "status": "research_estimate",
        "source": "analytical_quant",
        "method": "gaussian_copula_terminal_worst_of",
        "p_loss": round(probability, 6),
        "robust_lower": round(float(np.clip(lower, 0.0, 1.0)), 6),
        "robust_upper": round(float(np.clip(upper, 0.0, 1.0)), 6),
        "annualized_vol_mean": round(float(np.mean(vols)), 6),
        "correlation_mean": round(float(np.mean(correlation[np.triu_indices(len(basket), 1)])), 6),
    }


def historical_barrier_probability(
    prices: Mapping[str, Sequence[float]],
    basket: Sequence[str],
    window_days: int,
    barrier: float = 0.65,
) -> dict:
    """Estimate path-dependent barrier risk from rolling observed windows."""
    if any(len(prices[ticker]) < window_days for ticker in basket):
        return {"status": "insufficient_data", "source": "historical_path_quant"}
    frame = np.column_stack(
        [np.asarray(prices[ticker], dtype=float) for ticker in basket],
    )
    outcomes: list[int] = []
    step = max(1, window_days // 12)
    for start in range(0, len(frame) - window_days + 1, step):
        window = frame[start:start + window_days]
        relative = window / window[0]
        outcomes.append(int(np.min(relative) < barrier))
    probability = float(np.mean(outcomes)) if outcomes else 0.0
    return {
        "status": "research_estimate",
        "source": "historical_path_quant",
        "method": "rolling_worst_of_barrier_frequency",
        "p_loss": round(probability, 6),
        "windows": len(outcomes),
    }


def regime_adjusted_probability(
    prices: Mapping[str, Sequence[float]],
    basket: Sequence[str],
    base_probability: float,
) -> dict:
    """Adjust a probability using recent-versus-long-run volatility regime."""
    returns = []
    for ticker in basket:
        values = np.asarray(prices[ticker], dtype=float)
        if len(values) < 64:
            return {"status": "insufficient_data", "source": "regime_quant"}
        returns.append(np.diff(np.log(values)))
    matrix = np.asarray(returns, dtype=float)
    recent = float(np.mean(np.std(matrix[:, -63:], axis=1)))
    long_run = float(np.mean(np.std(matrix, axis=1)))
    ratio = recent / long_run if long_run > 0 else 1.0
    adjusted = float(np.clip(base_probability * np.clip(ratio, 0.75, 1.5), 0.0, 1.0))
    return {
        "status": "research_estimate",
        "source": "regime_quant",
        "method": "recent_to_long_run_volatility_ratio",
        "p_loss": round(adjusted, 6),
        "volatility_ratio": round(ratio, 6),
    }
