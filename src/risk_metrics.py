"""Risk Metrics — VaR, CVaR, EVT (Extreme Value Theory), Drawdown, Stress Tests.

Provides historical, parametric, and EVT-based risk measures for portfolio returns.
EVT uses scipy.stats.genpareto with automated Mean Excess threshold selection.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# VaR / CVaR
# ═══════════════════════════════════════════════════════════════


def value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    """Historical VaR at given confidence level.

    Args:
        returns: Daily returns series.
        confidence: Confidence level (e.g. 0.95 for 95%).

    Returns:
        VaR value (negative = loss).

    Raises:
        ValueError: If returns is empty or confidence out of range.
    """
    if len(returns) == 0:
        raise ValueError("returns must not be empty")
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    return float(np.percentile(returns, (1 - confidence) * 100))


def conditional_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """CVaR (Expected Shortfall) — mean of tail beyond VaR.

    Args:
        returns: Daily returns series.
        confidence: Confidence level.

    Returns:
        CVaR value (negative = loss).

    Raises:
        ValueError: If returns is empty.
    """
    if len(returns) == 0:
        raise ValueError("returns must not be empty")
    var = value_at_risk(returns, confidence)
    tail = returns[returns <= var]
    if len(tail) == 0:
        return var
    return float(tail.mean())


def parametric_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Parametric VaR assuming normal distribution.

    Args:
        returns: Daily returns series.
        confidence: Confidence level.

    Returns:
        VaR value under normality assumption.

    Raises:
        ValueError: If returns is empty.
    """
    if len(returns) == 0:
        raise ValueError("returns must not be empty")
    mu = float(returns.mean())
    sigma = float(returns.std())
    z = float(stats.norm.ppf(1 - confidence))
    return mu + z * sigma


# ═══════════════════════════════════════════════════════════════
# EVT — Extreme Value Theory (Generalized Pareto Distribution)
# ═══════════════════════════════════════════════════════════════


def _mean_excess_plot(losses: np.ndarray) -> np.ndarray:
    """Compute mean excess values for automated threshold selection.

    Args:
        losses: Array of positive loss values (negated returns).

    Returns:
        Array of (threshold, mean_excess) pairs.
    """
    sorted_losses = np.sort(losses)
    n = len(sorted_losses)
    thresholds = sorted_losses[int(n * 0.8):int(n * 0.98)]
    me_values = []
    for u in thresholds:
        exceedances = losses[losses > u] - u
        if len(exceedances) >= 10:
            me_values.append((u, float(exceedances.mean())))
    return np.array(me_values) if me_values else np.array([]).reshape(0, 2)


def _select_evt_threshold(losses: np.ndarray) -> float:
    """Automated threshold selection via Mean Excess plot stability.

    Args:
        losses: Array of positive loss values.

    Returns:
        Optimal threshold for GPD fitting.
    """
    me_data = _mean_excess_plot(losses)
    if len(me_data) < 3:
        return float(np.percentile(losses, 90))

    thresholds = me_data[:, 0]
    me_vals = me_data[:, 1]

    best_u = thresholds[len(thresholds) // 2]
    if len(me_vals) >= 5:
        diffs = np.abs(np.diff(me_vals, 2))
        if len(diffs) > 0:
            stable_idx = int(np.argmin(diffs))
            best_u = float(thresholds[stable_idx + 1])

    return best_u


def evt_var_cvar(
    returns: pd.Series,
    confidence_levels: Optional[list[float]] = None,
) -> dict:
    """EVT-based VaR and CVaR using Generalized Pareto Distribution.

    Args:
        returns: Daily returns series (at least 50 observations).
        confidence_levels: List of confidence levels (default [0.95, 0.99]).

    Returns:
        Dict with evt_var_95, evt_var_99, evt_cvar_95, evt_cvar_99, etc.

    Raises:
        ValueError: If returns has fewer than 50 observations.
    """
    if confidence_levels is None:
        confidence_levels = [0.95, 0.99]
    if len(returns) < 50:
        raise ValueError(f"EVT requires >= 50 observations, got {len(returns)}")

    losses = -returns.values.astype(float)
    n = len(losses)
    threshold = _select_evt_threshold(losses)
    exceedances = losses[losses > threshold] - threshold
    n_exceed = len(exceedances)

    result: dict = {
        "threshold": round(float(threshold), 6),
        "n_exceedances": n_exceed,
        "threshold_method": "mean_excess_stability",
        "gpd_fit_ok": False,
    }

    if n_exceed < 10:
        logger.warning("EVT: only %d exceedances, falling back to historical", n_exceed)
        for cl in confidence_levels:
            pct = int(cl * 100)
            result[f"evt_var_{pct}"] = value_at_risk(returns, cl)
            result[f"evt_cvar_{pct}"] = conditional_var(returns, cl)
        result["shape_xi"] = 0.0
        result["scale_beta"] = 0.0
        return result

    try:
        shape, _loc, scale = stats.genpareto.fit(exceedances, floc=0)
    except Exception:
        logger.warning("EVT: GPD fit failed, falling back to historical")
        for cl in confidence_levels:
            pct = int(cl * 100)
            result[f"evt_var_{pct}"] = value_at_risk(returns, cl)
            result[f"evt_cvar_{pct}"] = conditional_var(returns, cl)
        result["shape_xi"] = 0.0
        result["scale_beta"] = 0.0
        return result

    result["shape_xi"] = round(float(shape), 6)
    result["scale_beta"] = round(float(scale), 6)
    result["gpd_fit_ok"] = True

    tail_prob = n_exceed / n
    for cl in confidence_levels:
        pct = int(cl * 100)
        p = 1 - cl
        if abs(shape) < 1e-10:
            gpd_quantile = scale * np.log(tail_prob / p)
        else:
            gpd_quantile = (scale / shape) * (((tail_prob / p) ** shape) - 1)

        evt_var = -(threshold + gpd_quantile)
        result[f"evt_var_{pct}"] = round(float(evt_var), 6)

        if shape < 1:
            evt_cvar_val = evt_var / (1 - shape) + (scale - shape * threshold) / (1 - shape)
            result[f"evt_cvar_{pct}"] = round(float(-evt_cvar_val), 6)
        else:
            result[f"evt_cvar_{pct}"] = round(float(evt_var * 1.3), 6)

    return result


# ═══════════════════════════════════════════════════════════════
# Drawdown
# ═══════════════════════════════════════════════════════════════


def drawdown_series(returns: pd.Series) -> pd.Series:
    """Compute drawdown series from returns.

    Args:
        returns: Daily returns series.

    Returns:
        Series of drawdown values (all <= 0).
    """
    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    return (cum - peak) / peak


def drawdown_distribution(returns: pd.Series, n_bins: int = 50) -> dict:
    """Drawdown distribution statistics.

    Args:
        returns: Daily returns series.
        n_bins: Number of histogram bins (unused, kept for API compat).

    Returns:
        Dict with mean, median, worst, std, percentile_5, series.
    """
    dd = drawdown_series(returns)
    return {
        "mean": float(dd.mean()),
        "median": float(dd.median()),
        "worst": float(dd.min()),
        "std": float(dd.std()),
        "percentile_5": float(np.percentile(dd, 5)),
        "series": dd,
    }


# ═══════════════════════════════════════════════════════════════
# Stress Tests
# ═══════════════════════════════════════════════════════════════

STRESS_SCENARIOS: dict[str, tuple[str, str]] = {
    "GFC 2008": ("2008-09-01", "2009-03-31"),
    "COVID 2020": ("2020-02-15", "2020-04-15"),
    "Rate Hike 2022": ("2022-01-01", "2022-10-31"),
    "SVB Crisis 2023": ("2023-03-01", "2023-03-31"),
}


def stress_test(
    returns: pd.Series,
    scenarios: Optional[dict[str, tuple[str, str]]] = None,
) -> list[dict]:
    """Compute cumulative return and max drawdown for each crisis period.

    Args:
        returns: Daily returns with DatetimeIndex.
        scenarios: Dict of scenario_name -> (start_date, end_date).

    Returns:
        List of dicts with scenario, period, cum_return, max_dd, n_days.
    """
    if scenarios is None:
        scenarios = STRESS_SCENARIOS

    results: list[dict] = []
    for name, (start, end) in scenarios.items():
        mask = (returns.index >= start) & (returns.index <= end)
        subset = returns.loc[mask]
        if len(subset) < 2:
            results.append({
                "scenario": name, "period": f"{start} -> {end}",
                "cum_return": float("nan"), "max_dd": float("nan"),
                "n_days": 0, "warning": "No data for period",
            })
            continue

        cum_ret = float((1 + subset).prod() - 1)
        dd = drawdown_series(subset)
        results.append({
            "scenario": name, "period": f"{start} -> {end}",
            "cum_return": cum_ret, "max_dd": float(dd.min()),
            "n_days": len(subset), "warning": None,
        })

    return results


# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════


def risk_summary(returns: pd.Series) -> dict:
    """Full risk summary: historical, parametric, and EVT VaR/CVaR.

    Args:
        returns: Daily returns series.

    Returns:
        Dict with VaR/CVaR at 95% and 99% (historical + parametric + EVT).
    """
    result = {
        "VaR_95": value_at_risk(returns, 0.95),
        "CVaR_95": conditional_var(returns, 0.95),
        "VaR_99": value_at_risk(returns, 0.99),
        "CVaR_99": conditional_var(returns, 0.99),
        "Parametric_VaR_95": parametric_var(returns, 0.95),
        "Parametric_VaR_99": parametric_var(returns, 0.99),
    }
    if len(returns) >= 50:
        try:
            evt = evt_var_cvar(returns, [0.95, 0.99])
            result["EVT_VaR_95"] = evt.get("evt_var_95", float("nan"))
            result["EVT_CVaR_95"] = evt.get("evt_cvar_95", float("nan"))
            result["EVT_VaR_99"] = evt.get("evt_var_99", float("nan"))
            result["EVT_CVaR_99"] = evt.get("evt_cvar_99", float("nan"))
            result["EVT_shape_xi"] = evt.get("shape_xi", 0)
            result["EVT_gpd_fit_ok"] = evt.get("gpd_fit_ok", False)
        except Exception as exc:
            logger.warning("EVT computation failed: %s", exc)
    return result
