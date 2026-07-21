"""Fly Backtesting Engine — event-driven strategy simulation.

Usage:
    from src.backtester import BacktestEngine, BacktestConfig
    from src.strategies import MomentumStrategy

    config = BacktestConfig(tickers=["AAPL", "MSFT"],
                            start_date="2023-01-01", end_date="2024-12-31")
    result = BacktestEngine(MomentumStrategy(), config).run()
    print(result.sharpe, result.total_return)
"""

from .engine import BacktestEngine
from .models import BacktestConfig, BacktestResult, BacktestTrade
from .report import BacktestReporter
from .strategy_base import BaseStrategy

__all__ = [
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "BacktestTrade",
    "BacktestReporter",
    "BaseStrategy",
]
