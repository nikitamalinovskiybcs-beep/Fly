"""Markowitz mean-variance optimizer (scipy SLSQP)."""

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ._common import TRADING_DAYS, build_allocation
from .models import PortfolioAllocation


class MeanVarianceOptimizer:
    """Markowitz mean-variance optimization with long-only constraints."""

    def __init__(self, max_weight: float = 1.0):
        self.max_weight = max_weight

    def _prep(self, returns: pd.DataFrame):
        tickers = list(returns.columns)
        n = len(tickers)
        mean = returns.mean().to_numpy() * TRADING_DAYS
        cov = returns.cov().to_numpy() * TRADING_DAYS
        bounds = [(0.0, self.max_weight)] * n
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        x0 = np.repeat(1.0 / n, n)
        return tickers, n, mean, cov, bounds, constraints, x0

    def max_sharpe(self, returns: pd.DataFrame, risk_free: float = 0.02) -> PortfolioAllocation:
        tickers, n, mean, cov, bounds, constraints, x0 = self._prep(returns)

        def neg_sharpe(w):
            ret = float(np.dot(w, mean))
            vol = float(np.sqrt(max(w @ cov @ w, 1e-12)))
            return -(ret - risk_free) / vol

        res = minimize(neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=constraints)
        w = res.x if res.success else x0
        return build_allocation(tickers, w, "max_sharpe", returns, risk_free)

    def min_variance(self, returns: pd.DataFrame) -> PortfolioAllocation:
        tickers, n, mean, cov, bounds, constraints, x0 = self._prep(returns)

        def variance(w):
            return float(w @ cov @ w)

        res = minimize(variance, x0, method="SLSQP", bounds=bounds, constraints=constraints)
        w = res.x if res.success else x0
        return build_allocation(tickers, w, "min_variance", returns)

    def target_return(self, returns: pd.DataFrame, target: float) -> PortfolioAllocation:
        """Min-variance portfolio achieving at least `target` annual return (fraction)."""
        tickers, n, mean, cov, bounds, constraints, x0 = self._prep(returns)
        cons = [
            *constraints,
            {"type": "ineq", "fun": lambda w: float(np.dot(w, mean)) - target},
        ]

        def variance(w):
            return float(w @ cov @ w)

        res = minimize(variance, x0, method="SLSQP", bounds=bounds, constraints=cons)
        w = res.x if res.success else x0
        return build_allocation(tickers, w, "target_return", returns)

    def efficient_frontier(self, returns: pd.DataFrame, n_points: int = 20) -> list[dict]:
        mean = returns.mean().to_numpy() * TRADING_DAYS
        lo, hi = float(mean.min()), float(mean.max())
        targets = np.linspace(lo, hi, n_points)
        frontier = []
        for t in targets:
            alloc = self.target_return(returns, t)
            frontier.append(
                {
                    "target_return": round(float(t) * 100, 4),
                    "expected_return": alloc.expected_return,
                    "expected_volatility": alloc.expected_volatility,
                    "expected_sharpe": alloc.expected_sharpe,
                }
            )
        return frontier
