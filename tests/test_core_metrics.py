"""Tests for src.core_metrics — Sharpe, Sortino, Calmar, Walk-Forward."""

import numpy as np
import pandas as pd
import pytest

from src.core_metrics import (
    returns_from_prices,
    total_return,
    cagr,
    annualized_volatility,
    sharpe_ratio,
    sortino_ratio,
    max_drawdown,
    max_drawdown_duration,
    profit_factor,
    win_rate,
    performance_summary,
    monte_carlo_permutation_test,
    walk_forward_analysis,
    stability_by_periods,
    PerformanceSummary,
)


@pytest.fixture
def positive_returns() -> pd.Series:
    rng = np.random.default_rng(42)
    idx = pd.bdate_range("2020-01-01", periods=500)
    return pd.Series(rng.normal(0.001, 0.01, 500), index=idx)


@pytest.fixture
def negative_returns() -> pd.Series:
    rng = np.random.default_rng(42)
    idx = pd.bdate_range("2020-01-01", periods=500)
    return pd.Series(rng.normal(-0.001, 0.015, 500), index=idx)


@pytest.fixture
def prices() -> pd.Series:
    rng = np.random.default_rng(42)
    rets = rng.normal(0.0005, 0.01, 500)
    prices_arr = 100 * np.cumprod(1 + rets)
    return pd.Series(prices_arr, index=pd.bdate_range("2020-01-01", periods=500))


# ── Basic metrics ──

def test_returns_from_prices(prices: pd.Series) -> None:
    rets = returns_from_prices(prices)
    assert len(rets) == len(prices) - 1


def test_total_return_positive(positive_returns: pd.Series) -> None:
    tr = total_return(positive_returns)
    assert tr > 0


def test_cagr_positive(positive_returns: pd.Series) -> None:
    c = cagr(positive_returns)
    assert c > 0


def test_cagr_empty() -> None:
    assert cagr(pd.Series([], dtype=float)) == 0.0


def test_annualized_vol_positive(positive_returns: pd.Series) -> None:
    vol = annualized_volatility(positive_returns)
    assert vol > 0


def test_sharpe_positive(positive_returns: pd.Series) -> None:
    sr = sharpe_ratio(positive_returns)
    assert sr > 0


def test_sharpe_zero_std() -> None:
    flat = pd.Series([0.0] * 100)
    assert sharpe_ratio(flat) == 0.0


def test_sortino_positive(positive_returns: pd.Series) -> None:
    s = sortino_ratio(positive_returns)
    assert s > 0


def test_max_drawdown_negative(positive_returns: pd.Series) -> None:
    mdd = max_drawdown(positive_returns)
    assert mdd <= 0


def test_max_drawdown_duration_positive(positive_returns: pd.Series) -> None:
    dur = max_drawdown_duration(positive_returns)
    assert dur >= 0


def test_profit_factor_positive(positive_returns: pd.Series) -> None:
    pf = profit_factor(positive_returns)
    assert pf > 1  # positive strategy should have PF > 1


def test_profit_factor_no_losses() -> None:
    gains_only = pd.Series([0.01, 0.02, 0.03])
    pf = profit_factor(gains_only)
    assert pf == float("inf")


def test_win_rate_positive(positive_returns: pd.Series) -> None:
    wr = win_rate(positive_returns)
    assert 0 < wr < 1


def test_win_rate_empty() -> None:
    assert win_rate(pd.Series([], dtype=float)) == 0.0


# ── Performance Summary ──

def test_performance_summary(positive_returns: pd.Series) -> None:
    ps = performance_summary(positive_returns)
    assert isinstance(ps, PerformanceSummary)
    assert ps.sharpe > 0
    assert ps.max_drawdown <= 0


def test_performance_summary_negative(negative_returns: pd.Series) -> None:
    ps = performance_summary(negative_returns)
    assert ps.sharpe < 0


# ── Monte Carlo Permutation ──

def test_mc_permutation(positive_returns: pd.Series) -> None:
    result = monte_carlo_permutation_test(positive_returns, n_permutations=200)
    assert "observed" in result
    assert "p_value" in result
    assert 0 <= result["p_value"] <= 1


# ── Walk-Forward ──

def test_walk_forward(positive_returns: pd.Series) -> None:
    results = walk_forward_analysis(positive_returns, n_splits=5)
    assert len(results) > 0
    assert "train_metric" in results[0]


def test_walk_forward_degradation(positive_returns: pd.Series) -> None:
    results = walk_forward_analysis(positive_returns, n_splits=5)
    for r in results:
        assert "degradation" in r


# ── Stability by Periods ──

def test_stability_by_periods(positive_returns: pd.Series) -> None:
    result = stability_by_periods(positive_returns)
    assert isinstance(result, dict)
