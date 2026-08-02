"""Tests for src.risk_metrics — VaR, CVaR, EVT, Drawdown, Stress Tests."""

import math

import numpy as np
import pandas as pd
import pytest

from src.risk_metrics import (
    value_at_risk,
    conditional_var,
    parametric_var,
    evt_var_cvar,
    drawdown_series,
    drawdown_distribution,
    stress_test,
    risk_summary,
    _mean_excess_plot,
    _select_evt_threshold,
)


@pytest.fixture
def normal_returns() -> pd.Series:
    rng = np.random.default_rng(42)
    return pd.Series(rng.normal(0.0005, 0.01, 500))


@pytest.fixture
def fat_tail_returns() -> pd.Series:
    rng = np.random.default_rng(42)
    base = rng.normal(0.0003, 0.012, 500)
    # Inject fat tails
    base[:10] = rng.normal(-0.05, 0.02, 10)
    return pd.Series(base)


@pytest.fixture
def dated_returns() -> pd.Series:
    rng = np.random.default_rng(42)
    idx = pd.bdate_range("2020-01-01", periods=500)
    return pd.Series(rng.normal(0.0005, 0.015, 500), index=idx)


# ── VaR tests ──

def test_var_returns_float(normal_returns: pd.Series) -> None:
    result = value_at_risk(normal_returns, 0.95)
    assert isinstance(result, float)


def test_var_95_less_than_median(normal_returns: pd.Series) -> None:
    var = value_at_risk(normal_returns, 0.95)
    assert var < float(normal_returns.median())


def test_var_99_more_extreme_than_95(normal_returns: pd.Series) -> None:
    var95 = value_at_risk(normal_returns, 0.95)
    var99 = value_at_risk(normal_returns, 0.99)
    assert var99 <= var95


def test_var_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        value_at_risk(pd.Series([], dtype=float))


def test_var_bad_confidence(normal_returns: pd.Series) -> None:
    with pytest.raises(ValueError, match="confidence"):
        value_at_risk(normal_returns, 1.5)


# ── CVaR tests ──

def test_cvar_more_extreme_than_var(normal_returns: pd.Series) -> None:
    var = value_at_risk(normal_returns, 0.95)
    cvar = conditional_var(normal_returns, 0.95)
    assert cvar <= var


def test_cvar_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        conditional_var(pd.Series([], dtype=float))


# ── Parametric VaR tests ──

def test_parametric_var_returns_float(normal_returns: pd.Series) -> None:
    result = parametric_var(normal_returns, 0.95)
    assert isinstance(result, float)


def test_parametric_var_empty_raises() -> None:
    with pytest.raises(ValueError):
        parametric_var(pd.Series([], dtype=float))


# ── EVT tests ──

def test_evt_returns_dict(normal_returns: pd.Series) -> None:
    result = evt_var_cvar(normal_returns)
    assert isinstance(result, dict)
    assert "evt_var_95" in result
    assert "evt_var_99" in result
    assert "evt_cvar_95" in result
    assert "evt_cvar_99" in result


def test_evt_gpd_fit_ok(fat_tail_returns: pd.Series) -> None:
    result = evt_var_cvar(fat_tail_returns)
    assert "gpd_fit_ok" in result
    assert "shape_xi" in result
    assert "scale_beta" in result


def test_evt_threshold_selected(normal_returns: pd.Series) -> None:
    result = evt_var_cvar(normal_returns)
    assert result["threshold"] > 0
    assert result["n_exceedances"] >= 1


def test_evt_too_short_raises() -> None:
    with pytest.raises(ValueError, match="50"):
        evt_var_cvar(pd.Series(np.random.randn(20)))


def test_evt_custom_confidence(normal_returns: pd.Series) -> None:
    result = evt_var_cvar(normal_returns, confidence_levels=[0.90, 0.95, 0.99])
    assert "evt_var_90" in result
    assert "evt_var_95" in result
    assert "evt_var_99" in result


def test_mean_excess_plot() -> None:
    rng = np.random.default_rng(42)
    losses = np.abs(rng.normal(0, 0.02, 500))
    me = _mean_excess_plot(losses)
    assert me.shape[1] == 2 or len(me) == 0


def test_select_evt_threshold() -> None:
    rng = np.random.default_rng(42)
    losses = np.abs(rng.normal(0, 0.02, 500))
    u = _select_evt_threshold(losses)
    assert isinstance(u, float)
    assert u > 0


# ── Drawdown tests ──

def test_drawdown_all_negative(normal_returns: pd.Series) -> None:
    dd = drawdown_series(normal_returns)
    assert (dd <= 0).all() or dd.iloc[0] == 0


def test_drawdown_distribution_keys(normal_returns: pd.Series) -> None:
    result = drawdown_distribution(normal_returns)
    assert "mean" in result
    assert "worst" in result
    assert "percentile_5" in result
    assert result["worst"] <= 0


# ── Stress test ──

def test_stress_test_returns_list(dated_returns: pd.Series) -> None:
    results = stress_test(dated_returns)
    assert isinstance(results, list)
    assert len(results) > 0


def test_stress_test_custom_scenarios(dated_returns: pd.Series) -> None:
    scenarios = {"Test": ("2020-01-15", "2020-03-31")}
    results = stress_test(dated_returns, scenarios)
    assert len(results) == 1
    assert results[0]["n_days"] > 0


# ── Risk summary ──

def test_risk_summary_has_evt(normal_returns: pd.Series) -> None:
    result = risk_summary(normal_returns)
    assert "VaR_95" in result
    assert "EVT_VaR_95" in result
    assert "EVT_gpd_fit_ok" in result


def test_risk_summary_short_no_evt() -> None:
    short = pd.Series(np.random.randn(30))
    result = risk_summary(short)
    assert "VaR_95" in result
    assert "EVT_VaR_95" not in result
