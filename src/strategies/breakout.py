"""Breakout strategy — buy on channel breakout with volume surge."""

from src.backtester.strategy_base import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """Buy when price breaks above its recent range with a volume surge.

    Best in trending markets (high ADX).
    """

    def name(self) -> str:
        return "Breakout"

    def generate_signals(self, data, features, date) -> dict[str, float]:
        signals: dict[str, float] = {}
        for ticker, feat in features.items():
            score = 0.0
            # breakout above SMA50 with room below overbought
            if feat.distance_to_sma50_pct is not None and feat.distance_to_sma50_pct > 3:
                score += 0.4
            if feat.adx_14 is not None and feat.adx_14 > 25:
                score += 0.3
            if feat.volume_ratio_20d is not None and feat.volume_ratio_20d > 1.5:
                score += 0.3
            if feat.momentum_10d is not None and feat.momentum_10d < 0:
                score -= 0.4  # failed breakout / reversal
            signals[ticker] = max(-1.0, min(1.0, score))
        return signals
