"""Tests for the backtesting engine, broker, and portfolio simulators."""

import numpy as np
import pandas as pd
import pytest

from src.backtester import (
    BacktestConfig,
    BacktestEngine,
    BacktestReporter,
    BacktestResult,
)
from src.backtester.broker_sim import SimulatedBroker
from src.backtester.portfolio_sim import PortfolioSimulator
from src.strategies import EnsembleStrategy, MomentumStrategy, TrendFollowingStrategy


def _make_data(ticker, start, end, seed=0):
    rng = np.random.default_rng(abs(hash(ticker)) % 1000 + seed)
    idx = pd.bdate_range(start, end)
    n = len(idx)
    price = 100 * np.cumprod(1 + rng.standard_normal(n) * 0.012 + 0.0004)
    price = pd.Series(price, index=idx)
    return pd.DataFrame(
        {
            "Open": price,
            "High": price * 1.01,
            "Low": price * 0.99,
            "Close": price,
            "Volume": pd.Series(rng.integers(1_000_000, 5_000_000, n), index=idx),
        }
    )


class TestSimulatedBroker:
    def test_buy_adds_slippage_and_commission(self):
        broker = SimulatedBroker(commission_pct=0.001, slippage_pct=0.0005)
        fill, comm, slip = broker.execute_buy(100.0, 10)
        assert fill > 100.0  # slippage pushes price up on buy
        assert comm > 0
        assert slip > 0

    def test_sell_reduces_price(self):
        broker = SimulatedBroker(slippage_pct=0.0005)
        fill, comm, slip = broker.execute_sell(100.0, 10)
        assert fill < 100.0  # slippage pushes price down on sell


class TestPortfolioSimulator:
    def test_buy_reduces_cash(self):
        pf = PortfolioSimulator(100000)
        ok = pf.buy("AAPL", 100.0, 10, "2024-01-01", 1.0, 0.5)
        assert ok
        assert pf.cash < 100000
        assert "AAPL" in pf.positions

    def test_cannot_buy_beyond_cash(self):
        pf = PortfolioSimulator(500)
        ok = pf.buy("AAPL", 100.0, 10, "2024-01-01", 1.0, 0.5)
        assert not ok

    def test_sell_records_trade(self):
        pf = PortfolioSimulator(100000)
        pf.buy("AAPL", 100.0, 10, "2024-01-01", 1.0, 0.5)
        pf.sell("AAPL", 110.0, 10, "2024-01-10", 1.0, 0.5)
        assert len(pf.trades) == 1
        trade = pf.trades[0]
        assert trade.ticker == "AAPL"
        assert trade.pnl > 0
        assert trade.hold_days == 9
        assert "AAPL" not in pf.positions

    def test_get_value(self):
        pf = PortfolioSimulator(100000)
        pf.buy("AAPL", 100.0, 10, "2024-01-01", 0.0, 0.0)
        value = pf.get_value({"AAPL": 120.0})
        assert value == pytest.approx(100000 - 1000 + 1200, rel=1e-6)


class TestBacktestEngine:
    def _run(self, strategy):
        cfg = BacktestConfig(
            tickers=["AAPL", "MSFT", "GOOG"],
            start_date="2022-01-01",
            end_date="2023-12-31",
            rebalance_freq="weekly",
        )
        return BacktestEngine(strategy, cfg, data_fetcher=_make_data).run()

    def test_returns_result(self):
        result = self._run(MomentumStrategy())
        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) > 0

    def test_metrics_populated(self):
        result = self._run(TrendFollowingStrategy())
        assert result.total_trades >= 0
        assert result.equity_curve[-1]["value"] > 0
        # sharpe/maxdd are finite numbers
        assert np.isfinite(result.sharpe)
        assert result.max_drawdown <= 0

    def test_no_open_positions_after_run(self):
        result = self._run(MomentumStrategy())
        # engine closes all positions at the end
        eng = BacktestEngine(
            MomentumStrategy(),
            BacktestConfig(tickers=["AAPL"], start_date="2022-01-01", end_date="2023-06-30"),
            data_fetcher=_make_data,
        )
        eng.run()
        assert len(eng.portfolio.positions) == 0
        assert result is not None

    def test_empty_data_returns_empty_result(self):
        cfg = BacktestConfig(tickers=["AAPL"], start_date="2022-01-01", end_date="2022-12-31")
        result = BacktestEngine(MomentumStrategy(), cfg, data_fetcher=lambda *a, **k: pd.DataFrame()).run()
        assert result.total_trades == 0
        assert result.equity_curve == []

    def test_ensemble_runs(self):
        result = self._run(EnsembleStrategy())
        assert isinstance(result, BacktestResult)


class TestReporter:
    def test_summary_and_frames(self):
        cfg = BacktestConfig(
            tickers=["AAPL", "MSFT"],
            start_date="2022-01-01",
            end_date="2023-12-31",
            rebalance_freq="weekly",
        )
        result = BacktestEngine(MomentumStrategy(), cfg, data_fetcher=_make_data).run()
        reporter = BacktestReporter()
        assert "Backtest:" in reporter.summary(result)
        eq_df = reporter.to_dataframe(result)
        assert "value" in eq_df.columns
        # monthly table + trades frame do not crash
        reporter.monthly_table(result)
        reporter.trades_dataframe(result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
