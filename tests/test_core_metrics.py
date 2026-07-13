"""Unit tests for core_metrics module."""

import pytest
import pandas as pd
import numpy as np
from src.core_metrics import (
    sharpe_ratio, sortino_ratio, max_drawdown, total_return, cagr,
    profit_factor, win_rate, performance_summary, monte_carlo_permutation_test,
    walk_forward_analysis
)


class TestBasicMetrics:
    """Test basic metric calculations."""

    def test_sharpe_ratio_constant_returns(self):
        """Sharpe ratio for constant positive returns."""
        returns = pd.Series([0.01] * 252)
        sharpe = sharpe_ratio(returns)
        assert sharpe > 0
        assert np.isfinite(sharpe)

    def test_sharpe_ratio_zero_returns(self):
        """Sharpe ratio for zero returns."""
        returns = pd.Series([0.0] * 252)
        sharpe = sharpe_ratio(returns)
        assert sharpe == 0.0

    def test_max_drawdown_all_gains(self):
        """Max drawdown should be 0 for all positive returns."""
        returns = pd.Series([0.01] * 100)
        dd = max_drawdown(returns)
        assert dd == 0.0

    def test_max_drawdown_crash(self):
        """Max drawdown for a 50% crash."""
        returns = pd.Series([0.01] * 50 + [-0.01] * 50)
        dd = max_drawdown(returns)
        assert dd < 0
        assert dd > -1

    def test_total_return_single_trade(self):
        """Total return for single 10% gain."""
        returns = pd.Series([0.1])
        tr = total_return(returns)
        assert tr == pytest.approx(0.1, rel=1e-6)

    def test_profit_factor_all_winners(self):
        """Profit factor when all returns are positive."""
        returns = pd.Series([0.01, 0.02, 0.03])
        pf = profit_factor(returns)
        assert pf == float('inf')

    def test_profit_factor_all_losers(self):
        """Profit factor when all returns are negative."""
        returns = pd.Series([-0.01, -0.02, -0.03])
        pf = profit_factor(returns)
        assert pf == 0.0

    def test_win_rate_half(self):
        """Win rate for 50/50 split."""
        returns = pd.Series([0.01, -0.01, 0.01, -0.01])
        wr = win_rate(returns)
        assert wr == pytest.approx(0.5, rel=1e-6)

    def test_performance_summary_shapes(self):
        """Performance summary returns all required fields."""
        returns = pd.Series(np.random.randn(252) * 0.01)
        perf = performance_summary(returns)
        
        assert hasattr(perf, 'sharpe')
        assert hasattr(perf, 'sortino')
        assert hasattr(perf, 'max_drawdown')
        assert hasattr(perf, 'cagr')


class TestMonteCarlo:
    """Test Monte Carlo permutation test."""

    def test_mc_basic(self):
        """Basic MC test runs without errors."""
        returns = pd.Series(np.random.randn(252) * 0.01)
        result = monte_carlo_permutation_test(returns, n_permutations=100)
        
        assert "observed" in result
        assert "p_value" in result
        assert 0 <= result["p_value"] <= 1

    def test_mc_permutation_count(self):
        """MC returns correct number of permutations."""
        returns = pd.Series(np.random.randn(252) * 0.01)
        result = monte_carlo_permutation_test(returns, n_permutations=500)
        
        assert len(result["permuted_distribution"]) == 500


class TestWalkForward:
    """Test walk-forward analysis."""

    def test_wf_basic(self):
        """Basic walk-forward runs without errors."""
        returns = pd.Series(np.random.randn(252) * 0.01)
        results = walk_forward_analysis(returns, n_splits=5)
        
        assert len(results) > 0
        assert all('fold' in r for r in results)
        assert all('train_metric' in r for r in results)
        assert all('test_metric' in r for r in results)

    def test_wf_degradation(self):
        """Walk-forward degradation column exists."""
        returns = pd.Series(np.random.randn(252) * 0.01)
        results = walk_forward_analysis(returns, n_splits=5)
        
        assert all('degradation' in r for r in results)
