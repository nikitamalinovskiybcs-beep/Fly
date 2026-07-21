"""Unified portfolio optimizer facade."""

import pandas as pd

from .hrp import HRPOptimizer
from .mean_variance import MeanVarianceOptimizer
from .models import PortfolioAllocation
from .risk_parity import RiskParityOptimizer


class PortfolioOptimizer:
    """Single entry-point to all allocation methods."""

    METHODS = ("risk_parity", "max_sharpe", "min_variance", "hrp")

    def __init__(self, max_weight: float = 1.0):
        self.risk_parity = RiskParityOptimizer()
        self.mean_variance = MeanVarianceOptimizer(max_weight=max_weight)
        self.hrp = HRPOptimizer()

    def optimize(self, returns: pd.DataFrame, method: str = "hrp", **kwargs) -> PortfolioAllocation:
        if method == "risk_parity":
            return self.risk_parity.optimize(returns)
        if method == "max_sharpe":
            return self.mean_variance.max_sharpe(returns, **kwargs)
        if method == "min_variance":
            return self.mean_variance.min_variance(returns)
        if method == "hrp":
            return self.hrp.optimize(returns)
        raise ValueError(f"Unknown method: {method}. Choose from {self.METHODS}")
