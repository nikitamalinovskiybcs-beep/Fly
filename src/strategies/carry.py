"""Carry strategy — favor stable, trending names as a yield proxy."""

from src.backtester.strategy_base import BaseStrategy


class CarryStrategy(BaseStrategy):
    """Rank by a carry proxy and buy the highest, sell the lowest.

    True carry needs dividend yield; without a fundamentals feed we proxy
    "carry" as steady low-volatility uptrend (positive momentum + low vol),
    which captures the same buy-stable-yielders intent.
    """

    def name(self) -> str:
        return "Carry"

    def generate_signals(self, data, features, date) -> dict[str, float]:
        scores: dict[str, float] = {}
        for ticker, feat in features.items():
            if feat.volatility_30d is None or feat.volatility_30d <= 0:
                continue
            mom = feat.momentum_30d if feat.momentum_30d is not None else 0.0
            # higher when trend is positive and vol is low
            scores[ticker] = mom / feat.volatility_30d
        signals: dict[str, float] = {t: 0.0 for t in features}
        if len(scores) < 2:
            return signals
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        n = max(1, len(ranked) // 3)
        for t, _ in ranked[:n]:
            signals[t] = 1.0
        for t, _ in ranked[-n:]:
            signals[t] = -1.0
        return signals
