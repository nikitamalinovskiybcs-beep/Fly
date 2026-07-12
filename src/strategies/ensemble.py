"""Ensemble strategy — weighted combination of multiple strategies."""

from src.backtester.strategy_base import BaseStrategy

from .breakout import BreakoutStrategy
from .carry import CarryStrategy
from .mean_reversion import MeanReversionStrategy
from .momentum import MomentumStrategy
from .multi_factor import MultiFactorStrategy
from .risk_parity import RiskParityStrategy
from .trend_following import TrendFollowingStrategy
from .volatility_target import VolatilityTargetStrategy

DEFAULT_WEIGHTS = {
    "Momentum": 0.20,
    "Mean Reversion": 0.15,
    "Trend Following": 0.15,
    "Breakout": 0.10,
    "Volatility Target": 0.10,
    "Risk Parity": 0.10,
    "Multi-Factor": 0.10,
    "Carry": 0.10,
}


class EnsembleStrategy(BaseStrategy):
    """Combine signals from multiple strategies via a weighted average."""

    def __init__(self, strategies: list[BaseStrategy] | None = None, weights: dict[str, float] | None = None):
        if strategies is None:
            strategies = [
                MomentumStrategy(),
                MeanReversionStrategy(),
                TrendFollowingStrategy(),
                BreakoutStrategy(),
                VolatilityTargetStrategy(),
                RiskParityStrategy(),
                MultiFactorStrategy(),
                CarryStrategy(),
            ]
        self.strategies = strategies
        self.weights = weights or {
            s.name(): DEFAULT_WEIGHTS.get(s.name(), 1.0 / len(strategies)) for s in strategies
        }

    def name(self) -> str:
        return "Ensemble"

    def generate_signals(self, data, features, date) -> dict[str, float]:
        combined: dict[str, float] = {}
        for strat in self.strategies:
            sigs = strat.generate_signals(data, features, date)
            w = self.weights.get(strat.name(), 0.0)
            for ticker, sig in sigs.items():
                combined[ticker] = combined.get(ticker, 0.0) + sig * w
        return {t: max(-1.0, min(1.0, s)) for t, s in combined.items()}
