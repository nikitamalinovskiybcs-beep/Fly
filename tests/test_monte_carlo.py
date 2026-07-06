"""Tests for src.monte_carlo — Regime-conditional Monte Carlo."""

import numpy as np
import pandas as pd
import pytest

from src.monte_carlo import (
    RegimeModel,
    fit_regime_model_from_returns,
    regime_conditional_monte_carlo,
    simple_gbm_monte_carlo,
)


@pytest.fixture
def default_model() -> RegimeModel:
    return RegimeModel()


@pytest.fixture
def daily_returns() -> pd.Series:
    rng = np.random.default_rng(42)
    idx = pd.bdate_range("2020-01-01", periods=500)
    return pd.Series(rng.normal(0.0005, 0.012, 500), index=idx)


# ── RegimeModel ──

def test_default_model_has_3_regimes(default_model: RegimeModel) -> None:
    assert default_model.n_regimes == 3
    assert "BULL" in default_model.regime_names
    assert "BEAR" in default_model.regime_names


def test_regime_index(default_model: RegimeModel) -> None:
    assert default_model.regime_index("BULL") in (0, 1, 2)


def test_regime_index_invalid_raises(default_model: RegimeModel) -> None:
    with pytest.raises(ValueError, match="Unknown regime"):
        default_model.regime_index("CRASH")


def test_custom_model() -> None:
    params = {
        "UP": {"mu": 0.001, "sigma": 0.01},
        "DOWN": {"mu": -0.001, "sigma": 0.02},
    }
    trans = np.array([[0.9, 0.1], [0.2, 0.8]])
    model = RegimeModel(params, trans, ["UP", "DOWN"])
    assert model.n_regimes == 2


def test_bad_transition_shape_raises() -> None:
    params = {"A": {"mu": 0, "sigma": 0.01}, "B": {"mu": 0, "sigma": 0.01}}
    trans = np.array([[0.9, 0.1, 0.0], [0.2, 0.8, 0.0]])  # Wrong shape
    with pytest.raises(ValueError, match="shape"):
        RegimeModel(params, trans, ["A", "B"])


# ── Fit from returns ──

def test_fit_regime_model(daily_returns: pd.Series) -> None:
    model = fit_regime_model_from_returns(daily_returns)
    assert model.n_regimes == 3
    assert model.transition_matrix.shape == (3, 3)


def test_fit_model_transition_rows_sum_to_1(daily_returns: pd.Series) -> None:
    model = fit_regime_model_from_returns(daily_returns)
    row_sums = model.transition_matrix.sum(axis=1)
    np.testing.assert_allclose(row_sums, 1.0, atol=0.01)


def test_fit_model_too_short_raises() -> None:
    with pytest.raises(ValueError, match="50"):
        fit_regime_model_from_returns(pd.Series(np.random.randn(20)))


def test_fit_model_wrong_n_regimes_raises(daily_returns: pd.Series) -> None:
    with pytest.raises(ValueError, match="3"):
        fit_regime_model_from_returns(daily_returns, n_regimes=5)


# ── Regime-conditional MC ──

def test_regime_mc_returns_dict(default_model: RegimeModel) -> None:
    result = regime_conditional_monte_carlo(default_model, n_paths=500, n_days=100)
    assert isinstance(result, dict)
    assert "mean_return" in result
    assert "mc_var_95" in result


def test_regime_mc_var_ordering(default_model: RegimeModel) -> None:
    result = regime_conditional_monte_carlo(default_model, n_paths=1000, n_days=252)
    assert result["mc_var_99"] <= result["mc_var_95"]


def test_regime_mc_prob_loss(default_model: RegimeModel) -> None:
    result = regime_conditional_monte_carlo(default_model, n_paths=1000, n_days=252)
    assert 0 <= result["prob_loss"] <= 1


def test_regime_mc_occupancy(default_model: RegimeModel) -> None:
    result = regime_conditional_monte_carlo(default_model, n_paths=500, n_days=252)
    occ = result["regime_occupancy_pct"]
    total = sum(occ.values())
    assert abs(total - 100) < 5  # should sum to ~100%


def test_regime_mc_bad_initial_raises(default_model: RegimeModel) -> None:
    with pytest.raises(ValueError, match="Unknown regime"):
        regime_conditional_monte_carlo(default_model, initial_regime="CRASH")


def test_regime_mc_too_few_paths_raises(default_model: RegimeModel) -> None:
    with pytest.raises(ValueError, match="n_paths"):
        regime_conditional_monte_carlo(default_model, n_paths=10)


# ── Simple GBM MC ──

def test_simple_gbm_returns_dict() -> None:
    result = simple_gbm_monte_carlo(mu=0.10, sigma=0.20, n_paths=500, n_days=252)
    assert "mean_return" in result
    assert result["regime_aware"] is False


def test_simple_gbm_positive_mu_positive_mean() -> None:
    result = simple_gbm_monte_carlo(mu=0.15, sigma=0.10, n_paths=5000, n_days=252)
    assert result["mean_return"] > 0


def test_simple_gbm_too_few_paths_raises() -> None:
    with pytest.raises(ValueError, match="n_paths"):
        simple_gbm_monte_carlo(mu=0.10, sigma=0.20, n_paths=50)
