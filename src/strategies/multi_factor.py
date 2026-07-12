"""Multi-factor strategy — Value + Momentum + Quality blend."""

from src.backtester.strategy_base import BaseStrategy


class MultiFactorStrategy(BaseStrategy):
    """Combine Value, Momentum and Quality into a single score.

    Score = 0.33*value + 0.33*momentum + 0.33*quality.

    Feature proxies (from FeatureVector):
    - value:    distance below SMA200 (cheaper = higher score)
    - momentum: 30d momentum
    - quality:  low realized volatility (stable = higher score)
    """

    def name(self) -> str:
        return "Multi-Factor"

    def generate_signals(self, data, features, date) -> dict[str, float]:
        signals: dict[str, float] = {}
        for ticker, feat in features.items():
            value = 0.0
            if feat.distance_to_sma200_pct is not None:
                value = max(-1.0, min(1.0, -feat.distance_to_sma200_pct / 20.0))
            momentum = 0.0
            if feat.momentum_30d is not None:
                momentum = max(-1.0, min(1.0, feat.momentum_30d / 15.0))
            quality = 0.0
            if feat.volatility_30d is not None and feat.volatility_30d > 0:
                quality = max(-1.0, min(1.0, (30.0 - feat.volatility_30d) / 30.0))
            score = 0.34 * value + 0.33 * momentum + 0.33 * quality
            signals[ticker] = max(-1.0, min(1.0, score))
        return signals
