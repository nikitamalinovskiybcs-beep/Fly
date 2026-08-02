"""Momentum strategy — buy winners, sell losers."""

from src.backtester.strategy_base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """Buy winners, sell losers. Filter by regime (no buys in bear)."""

    def name(self) -> str:
        return "Momentum"

    def generate_signals(self, data, features, date) -> dict[str, float]:
        signals: dict[str, float] = {}
        for ticker, feat in features.items():
            if feat.regime == "bear":
                signals[ticker] = 0.0
                continue
            score = 0.0
            if feat.momentum_30d is not None and feat.momentum_30d > 5:
                score += 0.4
            if feat.rsi_14 is not None and feat.rsi_14 < 70:
                score += 0.2
            if feat.distance_to_sma50_pct is not None and feat.distance_to_sma50_pct > 0:
                score += 0.2
            if feat.volume_ratio_20d is not None and feat.volume_ratio_20d > 1.2:
                score += 0.2
            if feat.rsi_14 is not None and feat.rsi_14 > 75:
                score = -0.5  # overbought
            signals[ticker] = max(-1.0, min(1.0, score))
        return signals
