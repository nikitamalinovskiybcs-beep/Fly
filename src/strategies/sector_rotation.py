"""Sector rotation — rotate into strongest momentum names."""

from src.backtester.strategy_base import BaseStrategy


class SectorRotationStrategy(BaseStrategy):
    """Rank by 30d momentum; buy the top third, sell the bottom third.

    Operates over whatever universe is passed (proxy for sector ETFs).
    """

    def name(self) -> str:
        return "Sector Rotation"

    def generate_signals(self, data, features, date) -> dict[str, float]:
        ranked = [
            (t, f.momentum_30d)
            for t, f in features.items()
            if f.momentum_30d is not None
        ]
        signals: dict[str, float] = {t: 0.0 for t in features}
        if len(ranked) < 3:
            return signals
        ranked.sort(key=lambda x: x[1], reverse=True)
        n = max(1, len(ranked) // 3)
        for t, _ in ranked[:n]:
            signals[t] = 1.0
        for t, _ in ranked[-n:]:
            signals[t] = -1.0
        return signals
