"""Trend following — SMA crossover with ADX filter."""

from src.backtester.strategy_base import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    """Buy when SMA50 > SMA200 and ADX > 25. Sell when SMA50 < SMA200."""

    def name(self) -> str:
        return "Trend Following"

    def generate_signals(self, data, features, date) -> dict[str, float]:
        signals: dict[str, float] = {}
        for ticker, feat in features.items():
            score = 0.0
            if feat.sma_50 is not None and feat.sma_200 is not None:
                if feat.sma_50 > feat.sma_200:
                    score += 0.5
                    if feat.adx_14 is not None and feat.adx_14 > 25:
                        score += 0.5
                else:
                    score -= 0.6
            signals[ticker] = max(-1.0, min(1.0, score))
        return signals
