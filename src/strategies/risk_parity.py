"""Risk parity strategy — allocate inversely to volatility."""

from src.backtester.strategy_base import BaseStrategy


class RiskParityStrategy(BaseStrategy):
    """Equal risk allocation: weight_i = (1/vol_i) / sum(1/vol_j).

    Emits a positive signal proportional to each asset's inverse-vol weight.
    """

    def name(self) -> str:
        return "Risk Parity"

    def generate_signals(self, data, features, date) -> dict[str, float]:
        inv_vol: dict[str, float] = {}
        for ticker, feat in features.items():
            vol = feat.volatility_30d
            if vol is not None and vol > 0:
                inv_vol[ticker] = 1.0 / vol
        total = sum(inv_vol.values())
        signals: dict[str, float] = {t: 0.0 for t in features}
        if total <= 0:
            return signals
        # scale weights so the max weight maps to signal 1.0
        max_w = max(inv_vol.values()) / total
        for ticker, iv in inv_vol.items():
            w = iv / total
            signals[ticker] = max(0.0, min(1.0, w / max_w)) if max_w > 0 else 0.0
        return signals
