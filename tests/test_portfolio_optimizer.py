"""Tests for the portfolio optimizer (risk parity, mean-variance, HRP)."""

import numpy as np
import pandas as pd
import pytest

from src.portfolio_optimizer import (
    HRPOptimizer,
    MeanVarianceOptimizer,
    PortfolioAllocation,
    RiskParityOptimizer,
)
from src.portfolio_optimizer.optimizer import PortfolioOptimizer


def _returns(seed=0):
    rng = np.random.default_rng(seed)
    n = 400
    cols = ["AAPL", "MSFT", "GOOG", "TLT", "GLD"]
    data = {c: rng.standard_normal(n) * 0.012 + 0.0004 for c in cols}
    data["TLT"] = rng.standard_normal(n) * 0.005  # low vol asset
    return pd.DataFrame(data)


def _assert_valid(alloc: PortfolioAllocation):
    assert isinstance(alloc, PortfolioAllocation)
    assert alloc.weights
    total = sum(alloc.weights.values())
    assert total == pytest.approx(1.0, abs=1e-4)
    for w in alloc.weights.values():
        assert -1e-6 <= w <= 1.0 + 1e-6


class TestRiskParity:
    def test_weights_sum_to_one(self):
        _assert_valid(RiskParityOptimizer().optimize(_returns()))

    def test_low_vol_gets_higher_weight(self):
        alloc = RiskParityOptimizer().optimize(_returns())
        assert alloc.weights["TLT"] == max(alloc.weights.values())


class TestMeanVariance:
    def test_max_sharpe(self):
        alloc = MeanVarianceOptimizer().max_sharpe(_returns())
        _assert_valid(alloc)
        assert alloc.method == "max_sharpe"

    def test_min_variance(self):
        alloc = MeanVarianceOptimizer().min_variance(_returns())
        _assert_valid(alloc)

    def test_min_variance_lower_vol_than_equal_weight(self):
        rets = _returns()
        alloc = MeanVarianceOptimizer().min_variance(rets)
        eq_w = np.repeat(1 / rets.shape[1], rets.shape[1])
        eq_vol = float(np.sqrt(eq_w @ rets.cov().to_numpy() @ eq_w * 252)) * 100
        assert alloc.expected_volatility <= eq_vol + 1e-6

    def test_efficient_frontier(self):
        frontier = MeanVarianceOptimizer().efficient_frontier(_returns(), n_points=6)
        assert len(frontier) == 6
        assert all("expected_volatility" in p for p in frontier)

    def test_max_weight_constraint(self):
        alloc = MeanVarianceOptimizer(max_weight=0.3).max_sharpe(_returns())
        assert max(alloc.weights.values()) <= 0.3 + 1e-4


class TestHRP:
    def test_weights_sum_to_one(self):
        _assert_valid(HRPOptimizer().optimize(_returns()))

    def test_single_asset(self):
        rets = pd.DataFrame({"AAPL": np.random.randn(100) * 0.01})
        alloc = HRPOptimizer().optimize(rets)
        assert alloc.weights["AAPL"] == pytest.approx(1.0)


class TestFacade:
    @pytest.mark.parametrize("method", ["risk_parity", "max_sharpe", "min_variance", "hrp"])
    def test_all_methods(self, method):
        alloc = PortfolioOptimizer().optimize(_returns(), method=method)
        _assert_valid(alloc)

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError):
            PortfolioOptimizer().optimize(_returns(), method="nope")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
