"""Overfitting Checks — CSCV/PBO, Deflated Sharpe, MinTRL, Permutation, OOS.

Implements Bailey & Lopez de Prado (2014) methodology for detecting
backtest overfitting via Combinatorially Symmetric Cross-Validation.
"""

import logging
import math
from itertools import combinations
from typing import Optional

import numpy as np
import pandas as pd

from src.core_metrics import sharpe_ratio, performance_summary

logger = logging.getLogger(__name__)

EULER_MASCHERONI = 0.5772156649


# ═══════════════════════════════════════════════════════════════
# CSCV — Combinatorially Symmetric Cross-Validation
# ═══════════════════════════════════════════════════════════════


def _split_returns_into_subsets(
    returns: pd.Series, n_subsets: int = 16,
) -> list[np.ndarray]:
    """Split returns into S equal-size subsets.

    Args:
        returns: Daily returns series.
        n_subsets: Number of subsets (must be even).

    Returns:
        List of numpy arrays, one per subset.

    Raises:
        ValueError: If n_subsets is odd or returns too short.
    """
    if n_subsets % 2 != 0:
        raise ValueError(f"n_subsets must be even, got {n_subsets}")
    arr = returns.values.astype(float)
    if len(arr) < n_subsets * 2:
        raise ValueError(
            f"Need at least {n_subsets * 2} obs, got {len(arr)}"
        )
    chunk = len(arr) // n_subsets
    return [arr[i * chunk:(i + 1) * chunk] for i in range(n_subsets)]


def _compute_sharpe_for_combo(
    subsets: list[np.ndarray],
    train_indices: tuple,
    all_indices: set,
) -> tuple[float, float]:
    """Compute Sharpe ratio for train and test splits of one combination.

    Args:
        subsets: List of return subsets.
        train_indices: Tuple of indices forming the train split.
        all_indices: Full set of all indices.

    Returns:
        (train_sharpe, test_sharpe) tuple.
    """
    test_indices = all_indices - set(train_indices)
    train_rets = np.concatenate([subsets[i] for i in train_indices])
    test_rets = np.concatenate([subsets[i] for i in test_indices])

    train_sr = float(train_rets.mean() / (train_rets.std() + 1e-12) * np.sqrt(252))
    test_sr = float(test_rets.mean() / (test_rets.std() + 1e-12) * np.sqrt(252))
    return train_sr, test_sr


def cscv_probability_of_backtest_overfitting(
    returns: pd.Series,
    n_subsets: int = 16,
    max_combinations: int = 5000,
    seed: int = 42,
) -> dict:
    """CSCV-based Probability of Backtest Overfitting (PBO).

    Args:
        returns: Daily returns series.
        n_subsets: Number of subsets S (must be even, default 16).
        max_combinations: Cap on number of combinations to evaluate.
        seed: Random seed for subsampling combinations.

    Returns:
        Dict with probability_of_backtest_overfitting, n_combinations,
        logit_mean, logit_std, pbo_pvalue, verdict.
    """
    subsets = _split_returns_into_subsets(returns, n_subsets)
    half = n_subsets // 2
    all_idx = set(range(n_subsets))

    all_combos = list(combinations(range(n_subsets), half))
    rng = np.random.default_rng(seed)
    if len(all_combos) > max_combinations:
        chosen = rng.choice(len(all_combos), size=max_combinations, replace=False)
        combos = [all_combos[i] for i in chosen]
    else:
        combos = all_combos

    logits: list[float] = []
    for combo in combos:
        train_sr, test_sr = _compute_sharpe_for_combo(subsets, combo, all_idx)
        if test_sr != 0:
            w = train_sr / (abs(test_sr) + 1e-12)
            logit = np.log(max(w, 1e-12) / max(1e-12, 1))
            logits.append(float(logit))
        else:
            logits.append(0.0)

    logit_arr = np.array(logits)
    pbo = float((logit_arr < 0).sum() / len(logit_arr))
    logit_mean = float(logit_arr.mean())
    logit_std = float(logit_arr.std())

    if pbo > 0.5:
        verdict = "HIGH overfitting risk"
    elif pbo > 0.3:
        verdict = "MODERATE overfitting risk"
    else:
        verdict = "LOW overfitting risk"

    return {
        "probability_of_backtest_overfitting": round(pbo, 4),
        "n_combinations": len(combos),
        "logit_mean": round(logit_mean, 4),
        "logit_std": round(logit_std, 4),
        "pbo_pvalue": round(pbo, 4),
        "verdict": verdict,
    }


# ═══════════════════════════════════════════════════════════════
# Deflated Sharpe Ratio
# ═══════════════════════════════════════════════════════════════


def deflated_sharpe_ratio(
    observed_sharpe: float,
    n_trials: int,
    n_observations: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    sharpe_std: float = 1.0,
) -> dict:
    """Deflated Sharpe Ratio — adjusts for multiple testing bias.

    Args:
        observed_sharpe: Observed Sharpe ratio.
        n_trials: Number of strategy variations tried.
        n_observations: Number of return observations.
        skewness: Return skewness (default 0).
        kurtosis: Return kurtosis (default 3).
        sharpe_std: Std of Sharpe ratios across trials (default 1).

    Returns:
        Dict with deflated_sharpe, expected_max_sharpe, p_value, significant.

    Raises:
        ValueError: If n_trials < 1 or n_observations < 2.
    """
    if n_trials < 1:
        raise ValueError(f"n_trials must be >= 1, got {n_trials}")
    if n_observations < 2:
        raise ValueError(f"n_observations must be >= 2, got {n_observations}")

    expected_max = sharpe_std * (
        (1 - EULER_MASCHERONI) * math.sqrt(2 * math.log(n_trials))
        + EULER_MASCHERONI * math.sqrt(2 * math.log(n_trials))
        if n_trials > 1 else 0
    )

    non_normality_adj = 1 - (skewness * observed_sharpe) / 6 + (
        (kurtosis - 3) * observed_sharpe ** 2
    ) / 24
    se = math.sqrt(non_normality_adj / n_observations)

    z = (observed_sharpe - expected_max) / (se + 1e-12)
    from scipy.stats import norm
    p_value = float(1 - norm.cdf(z))

    return {
        "deflated_sharpe": round(float(z), 4),
        "expected_max_sharpe": round(float(expected_max), 4),
        "p_value": round(p_value, 6),
        "significant": p_value < 0.05,
        "n_trials": n_trials,
        "n_observations": n_observations,
    }


# ═══════════════════════════════════════════════════════════════
# Minimum Track Record Length
# ═══════════════════════════════════════════════════════════════


def minimum_track_record_length(
    observed_sharpe: float,
    target_sharpe: float = 0.0,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    confidence: float = 0.95,
) -> dict:
    """Minimum number of observations to trust a Sharpe ratio.

    Args:
        observed_sharpe: Observed Sharpe ratio (annualized).
        target_sharpe: Target Sharpe to beat (default 0).
        skewness: Return skewness.
        kurtosis: Return kurtosis.
        confidence: Confidence level (default 0.95).

    Returns:
        Dict with min_track_record_days, min_track_record_years.

    Raises:
        ValueError: If observed_sharpe <= target_sharpe.
    """
    if observed_sharpe <= target_sharpe:
        raise ValueError(
            f"observed_sharpe ({observed_sharpe}) must exceed target ({target_sharpe})"
        )

    from scipy.stats import norm
    z_alpha = float(norm.ppf(confidence))
    sr_daily = observed_sharpe / np.sqrt(252)
    sr_target = target_sharpe / np.sqrt(252)
    excess = sr_daily - sr_target

    non_normality = 1 - skewness * sr_daily / 6 + (kurtosis - 3) * sr_daily ** 2 / 24
    min_trl = float((z_alpha / excess) ** 2 * non_normality)
    min_trl = max(min_trl, 1.0)

    return {
        "min_track_record_days": int(math.ceil(min_trl)),
        "min_track_record_years": round(min_trl / 252, 2),
        "observed_sharpe": observed_sharpe,
        "target_sharpe": target_sharpe,
        "confidence": confidence,
    }


# ═══════════════════════════════════════════════════════════════
# Legacy — backward-compatible functions
# ═══════════════════════════════════════════════════════════════


def permutation_test_vs_random(
    strategy_returns: pd.Series,
    n_permutations: int = 2000,
    seed: int = 42,
) -> dict:
    """Compare strategy Sharpe against permuted returns.

    Args:
        strategy_returns: Daily strategy returns.
        n_permutations: Number of permutations (max 2000).
        seed: Random seed.

    Returns:
        Dict with observed_sharpe, p_value, significant, verdict.
    """
    n_permutations = min(n_permutations, 2000)
    rng = np.random.default_rng(seed)
    observed = sharpe_ratio(strategy_returns)
    arr = strategy_returns.values.copy()
    perm_sharpes = np.empty(n_permutations)
    for i in range(n_permutations):
        rng.shuffle(arr)
        perm_sharpes[i] = sharpe_ratio(pd.Series(arr, index=strategy_returns.index))

    p_val = float((perm_sharpes >= observed).sum() / n_permutations)
    return {
        "observed_sharpe": observed,
        "mean_permuted_sharpe": float(perm_sharpes.mean()),
        "std_permuted_sharpe": float(perm_sharpes.std()),
        "p_value": p_val,
        "significant": p_val < 0.05,
        "distribution": perm_sharpes,
        "verdict": (
            "Statistically significant (p < 0.05)"
            if p_val < 0.05
            else "WARNING: not significant — possible overfitting"
        ),
    }


def out_of_sample_degradation(
    returns: pd.Series, train_ratio: float = 0.7,
) -> dict:
    """Check Sharpe/CAGR degradation on out-of-sample data.

    Args:
        returns: Daily returns series.
        train_ratio: Fraction used for training (default 0.7).

    Returns:
        Dict with train/test Sharpe, degradation, warnings, verdict.
    """
    split_idx = int(len(returns) * train_ratio)
    train = returns.iloc[:split_idx]
    test = returns.iloc[split_idx:]

    train_perf = performance_summary(train)
    test_perf = performance_summary(test)

    sharpe_deg = train_perf.sharpe - test_perf.sharpe
    return_deg = train_perf.cagr - test_perf.cagr

    warnings: list[str] = []
    if sharpe_deg > 0.5:
        warnings.append(f"Sharpe degradation: {sharpe_deg:.2f}")
    if test_perf.sharpe < 0:
        warnings.append("OOS Sharpe < 0")
    if abs(return_deg) > 0.1:
        warnings.append(f"CAGR degradation: {return_deg:.1%}")

    return {
        "train_sharpe": train_perf.sharpe,
        "test_sharpe": test_perf.sharpe,
        "sharpe_degradation": sharpe_deg,
        "train_cagr": train_perf.cagr,
        "test_cagr": test_perf.cagr,
        "return_degradation": return_deg,
        "train_max_dd": train_perf.max_drawdown,
        "test_max_dd": test_perf.max_drawdown,
        "warnings": warnings,
        "verdict": (
            "OOS result stable"
            if not warnings
            else f"WARNING: {len(warnings)} issue(s) detected"
        ),
    }
