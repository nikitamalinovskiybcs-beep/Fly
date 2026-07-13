"""Unit tests for risk_metrics module."""

import pytest
import pandas as pd
import numpy as np
from src.risk_metrics import (
    value_at_risk, conditional_var, parametric_var, drawdown_series,
    drawdown_distribution, stress_test, risk_summary, add_custom_stress_scenario,
    DEFAULT_STRESS_SCENARIOS
)


class TestVaR:
    """Test Value at Risk calculations."""

    def test_var_95_consistency(self):
        """VaR 95% should be negative for typical returns."""
        returns = pd.Series(np.random.randn(252) * 0.01)
        var = value_at_risk(returns, 0.95)
        assert var < 0

    def test_var_99_worse_than_95(self):
        """VaR 99% should be worse (lower) than VaR 95%."""
        returns = pd.Series(np.random.randn(252) * 0.01)
        var_95 = value_at_risk(returns, 0.95)
        var_99 = value_at_risk(returns, 0.99)
        assert var_99 < var_95


class TestDrawdown:
    """Test drawdown calculations."""

    def test_drawdown_no_gains(self):
        """Drawdown series should be all negative or zero."""
        returns = pd.Series([0.01] * 100)
        dd = drawdown_series(returns)
        assert (dd <= 0).all()

    def test_drawdown_distribution_fields(self):
        """Drawdown distribution should have all required fields."""
        returns = pd.Series(np.random.randn(252) * 0.01)
        dist = drawdown_distribution(returns)
        
        assert 'mean' in dist
        assert 'median' in dist
        assert 'worst' in dist


class TestStressTests:
    """Test stress test functionality."""

    def test_stress_test_default_scenarios(self):
        """Stress test runs with default scenarios."""
        returns = pd.Series(np.random.randn(252 * 15) * 0.01, 
                           index=pd.date_range('2010-01-01', periods=252*15))
        results = stress_test(returns)
        
        assert len(results) == len(DEFAULT_STRESS_SCENARIOS)

    def test_stress_test_custom_scenario(self):
        """Stress test accepts custom scenarios."""
        returns = pd.Series(np.random.randn(252) * 0.01,
                           index=pd.date_range('2023-01-01', periods=252))
        custom = {"My Crisis": ("2023-03-01", "2023-04-01")}
        results = stress_test(returns, scenarios=custom)
        
        assert len(results) == 1
        assert results[0]['scenario'] == "My Crisis"

    def test_add_custom_scenario(self):
        """Custom scenario helper works."""
        custom = add_custom_stress_scenario("Black Swan", "2024-01-01", "2024-02-01")
        
        assert "Black Swan" in custom
        assert "GFC 2008" in custom


class TestRiskSummary:
    """Test risk summary aggregation."""

    def test_risk_summary_fields(self):
        """Risk summary has all required fields."""
        returns = pd.Series(np.random.randn(252) * 0.01)
        summary = risk_summary(returns)
        
        assert 'VaR_95' in summary
        assert 'CVaR_95' in summary
        assert 'VaR_99' in summary
        assert 'CVaR_99' in summary
