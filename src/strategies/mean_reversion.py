"""Mean reversion strategy — buy oversold, sell overbought."""

from src.backtester.strategy_base import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    """Buy oversold, sell overbought. Best in sideways regime."""

    def name(self) -> str:
        return "Mean Reversion"

    def generate_signals(self, data, features, date) -> dict[str, float]:
        signals: dict[str, float] = {}
        for ticker, feat in features.items():
            score = 0.0
            if feat.rsi_14 is not None:
                if feat.rsi_14 < 30:
                    score += 0.5
                elif feat.rsi_14 > 70:
                    score -= 0.5
            if feat.distance_to_sma200_pct is not None:
                if feat.distance_to_sma200_pct < -10:
                    score += 0.3
                elif feat.distance_to_sma200_pct > 10:
                    score -= 0.3
            if feat.bollinger_pct_b is not None:
                if feat.bollinger_pct_b < 0:
                    score += 0.2
                elif feat.bollinger_pct_b > 1:
                    score -= 0.2
            signals[ticker] = max(-1.0, min(1.0, score))
        return signals
