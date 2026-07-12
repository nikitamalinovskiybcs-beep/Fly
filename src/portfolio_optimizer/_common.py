"""Shared helpers for portfolio optimizers."""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def annualized_stats(weights: np.ndarray, returns: pd.DataFrame) -> tuple[float, float]:
    """Return (annualized_return_pct, annualized_vol_pct) for given weights."""
    mean_daily = returns.mean().to_numpy()
    cov_daily = returns.cov().to_numpy()
    port_ret = float(np.dot(weights, mean_daily) * TRADING_DAYS)
    port_var = float(weights @ cov_daily @ weights * TRADING_DAYS)
    port_vol = float(np.sqrt(max(port_var, 0.0)))
    return port_ret * 100, port_vol * 100


def build_allocation(tickers, weights, method, returns, risk_free=0.02, extra=None):
    from .models import PortfolioAllocation

    w = {t: float(x) for t, x in zip(tickers, weights)}
    exp_ret, exp_vol = annualized_stats(np.asarray(weights, dtype=float), returns)
    sharpe = (exp_ret / 100 - risk_free) / (exp_vol / 100) if exp_vol > 0 else 0.0
    return PortfolioAllocation(
        tickers=list(tickers),
        weights=w,
        method=method,
        expected_return=round(exp_ret, 4),
        expected_volatility=round(exp_vol, 4),
        expected_sharpe=round(float(sharpe), 4),
        max_weight=round(float(max(weights)), 4) if len(weights) else 0.0,
        min_weight=round(float(min(weights)), 4) if len(weights) else 0.0,
        extra=extra or {},
    )
