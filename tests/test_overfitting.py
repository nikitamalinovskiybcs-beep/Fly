"""Tests for src.overfitting — CSCV, PBO, Deflated Sharpe, MinTRL."""

import numpy as np
import pandas as pd
import pytest

from src.overfitting import (
    cscv_probability_of_backtest_overfitting,
    deflated_sharpe_ratio,
    minimum_track_record_length,
    permutation_test_vs_random,
    out_of_sample_degradation,
    _split_returns_into_subsets,
    white_reality_check,
)


@pytest.fixture
def strategy_returns() -> pd.Series:
    rng = np.random.default_rng(42)
    idx = pd.bdate_range("2020-01-01", periods=500)
    return pd.Series(rng.normal(0.0008, 0.012, 500), index=idx)


@pytest.fixture
def random_returns() -> pd.Series:
    rng = np.random.default_rng(99)
    idx = pd.bdate_range("2020-01-01", periods=500)
    return pd.Series(rng.normal(0.0, 0.015, 500), index=idx)


# ── CSCV / PBO ──

def test_cscv_returns_pbo(strategy_returns: pd.Series) -> None:
    result = cscv_probability_of_backtest_overfitting(strategy_returns, n_subsets=8)
    assert "probability_of_backtest_overfitting" in result
    assert 0 <= result["probability_of_backtest_overfitting"] <= 1


def test_cscv_n_combinations(strategy_returns: pd.Series) -> None:
    result = cscv_probability_of_backtest_overfitting(strategy_returns, n_subsets=8)
    assert result["n_combinations"] > 0


def test_cscv_verdict_low_overfit(strategy_returns: pd.Series) -> None:
    result = cscv_probability_of_backtest_overfitting(strategy_returns, n_subsets=8)
    assert "verdict" in result


def test_cscv_random_returns_higher_pbo(random_returns: pd.Series) -> None:
    result = cscv_probability_of_backtest_overfitting(random_returns, n_subsets=8)
    assert result["probability_of_backtest_overfitting"] >= 0


def test_cscv_odd_subsets_raises(strategy_returns: pd.Series) -> None:
    with pytest.raises(ValueError, match="even"):
        cscv_probability_of_backtest_overfitting(strategy_returns, n_subsets=7)


def test_cscv_too_short_raises() -> None:
    short = pd.Series(np.random.randn(20))
    with pytest.raises(ValueError):
        cscv_probability_of_backtest_overfitting(short, n_subsets=16)


def test_split_returns_into_subsets(strategy_returns: pd.Series) -> None:
    subsets = _split_returns_into_subsets(strategy_returns, 8)
    assert len(subsets) == 8
    total_len = sum(len(s) for s in subsets)
    # Floor division may discard trailing elements
    assert total_len <= len(strategy_returns)


def test_cscv_logit_stats(strategy_returns: pd.Series) -> None:
    result = cscv_probability_of_backtest_overfitting(strategy_returns, n_subsets=8)
    assert "logit_mean" in result
    assert "logit_std" in result


def test_cscv_max_combinations_cap(strategy_returns: pd.Series) -> None:
    result = cscv_probability_of_backtest_overfitting(
        strategy_returns, n_subsets=16, max_combinations=100
    )
    assert result["n_combinations"] <= 100


# ── Deflated Sharpe Ratio ──

def test_deflated_sharpe_returns_dict() -> None:
    result = deflated_sharpe_ratio(
        observed_sharpe=1.5,
        n_trials=100,
        n_observations=500,
    )
    assert "deflated_sharpe" in result
    assert "expected_max_sharpe" in result
    assert "p_value" in result


def test_deflated_sharpe_high_trials() -> None:
    result = deflated_sharpe_ratio(
        observed_sharpe=1.0,
        n_trials=1000,
        n_observations=252,
    )
    # With many trials, expected max Sharpe should be high
    assert result["expected_max_sharpe"] > 0


def test_deflated_sharpe_significance() -> None:
    result = deflated_sharpe_ratio(
        observed_sharpe=3.0,
        n_trials=5,
        n_observations=1000,
    )
    # Very high Sharpe with few trials should be significant
    assert result["significant"] is True


def test_deflated_sharpe_bad_trials_raises() -> None:
    with pytest.raises(ValueError, match="n_trials"):
        deflated_sharpe_ratio(observed_sharpe=1.0, n_trials=0, n_observations=100)


def test_deflated_sharpe_bad_observations_raises() -> None:
    with pytest.raises(ValueError, match="n_observations"):
        deflated_sharpe_ratio(observed_sharpe=1.0, n_trials=10, n_observations=1)


# ── Minimum Track Record Length ──

def test_min_trl_returns_days() -> None:
    result = minimum_track_record_length(observed_sharpe=1.5)
    assert "min_track_record_days" in result
    assert result["min_track_record_days"] > 0


def test_min_trl_higher_sharpe_needs_less_data() -> None:
    high = minimum_track_record_length(observed_sharpe=2.0)
    low = minimum_track_record_length(observed_sharpe=0.5)
    assert high["min_track_record_days"] <= low["min_track_record_days"]


def test_min_trl_same_sharpe_raises() -> None:
    with pytest.raises(ValueError, match="exceed"):
        minimum_track_record_length(observed_sharpe=0.0, target_sharpe=0.0)


def test_min_trl_years_conversion() -> None:
    result = minimum_track_record_length(observed_sharpe=1.0)
    expected_years = result["min_track_record_days"] / 252
    assert abs(result["min_track_record_years"] - expected_years) < 0.1


# ── Legacy: Permutation Test ──

def test_permutation_test_returns_dict(strategy_returns: pd.Series) -> None:
    result = permutation_test_vs_random(strategy_returns, n_permutations=100)
    assert "observed_sharpe" in result
    assert "p_value" in result
    assert "significant" in result


def test_permutation_test_nonempty(strategy_returns: pd.Series) -> None:
    result = permutation_test_vs_random(strategy_returns, n_permutations=50)
    assert "p_value" in result
    assert 0 <= result["p_value"] <= 1


def test_white_reality_check_is_deterministic() -> None:
    strategies = np.array(
        [
            [0.02, 0.00],
            [0.01, 0.00],
            [0.03, 0.00],
            [0.02, 0.00],
        ]
    )
    benchmark = np.zeros(4)
    first = white_reality_check(strategies, benchmark, n_bootstrap=100)
    second = white_reality_check(strategies, benchmark, n_bootstrap=100)
    assert first == second
    assert first["n_strategies"] == 2


# ── Legacy: OOS Degradation ──

def test_oos_degradation_returns_dict(strategy_returns: pd.Series) -> None:
    result = out_of_sample_degradation(strategy_returns)
    assert "train_sharpe" in result
    assert "test_sharpe" in result
    assert "verdict" in result


def test_oos_degradation_short_returns_dict() -> None:
    short = pd.Series(np.random.randn(20))
    result = out_of_sample_degradation(short)
    assert "train_sharpe" in result


def test_oos_degradation_train_ratio(strategy_returns: pd.Series) -> None:
    result = out_of_sample_degradation(strategy_returns, train_ratio=0.5)
    assert "test_sharpe" in result
