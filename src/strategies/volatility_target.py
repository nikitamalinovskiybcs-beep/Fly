"""Volatility targeting — scale exposure to hit a target vol."""

from src.backtester.strategy_base import BaseStrategy


class VolatilityTargetStrategy(BaseStrategy):
    """Target constant portfolio volatility.

    Long bias, but position size scales inversely with realized vol so the
    contribution to portfolio vol stays near the target.
    """

    TARGET_VOL = 15.0  # % annualized

    def name(self) -> str:
        return "Volatility Target"

    def generate_signals(self, data, features, date) -> dict[str, float]:
        signals: dict[str, float] = {}
        for ticker, feat in features.items():
            if feat.regime == "bear":
                signals[ticker] = 0.0
                continue
            vol = feat.volatility_30d
            if vol is None or vol <= 0:
                signals[ticker] = 0.3
                continue
            scale = self.TARGET_VOL / vol
            signals[ticker] = max(-1.0, min(1.0, scale))
        return signals

    def position_size(self, ticker, signal, portfolio_value, current_price, max_position_pct=0.20):
        # signal already encodes vol-scaling; cap allocation at max_position_pct
        if current_price <= 0 or signal <= 0:
            return 0.0
        alloc = portfolio_value * max_position_pct * min(signal, 1.0)
        return float(alloc / current_price)
