"""Fly Portfolio Optimizer — risk parity, mean-variance, and HRP allocation.

Usage:
    from src.portfolio_optimizer import (
        RiskParityOptimizer, MeanVarianceOptimizer, HRPOptimizer,
    )
    alloc = RiskParityOptimizer().optimize(returns_df)
    print(alloc.weights)
"""

from .hrp import HRPOptimizer
from .mean_variance import MeanVarianceOptimizer
from .models import PortfolioAllocation
from .risk_parity import RiskParityOptimizer

__all__ = [
    "PortfolioAllocation",
    "RiskParityOptimizer",
    "MeanVarianceOptimizer",
    "HRPOptimizer",
]
