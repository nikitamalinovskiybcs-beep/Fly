"""Worst-of prediction — identify most likely underperformer."""

import logging


from src.basket.models import AssetProfile

logger = logging.getLogger(__name__)


class WorstOfPredictor:
    """Predict which asset is most likely to be worst-of."""

    def predict(
        self,
        assets: list[AssetProfile],
        horizon_days: int = 90,
    ) -> dict[str, float]:
        """Predict worst-of probability per asset.

        Uses feature-based scoring: distance to barrier, RSI, ATR%, IV.
        Falls back to equal probability if insufficient data.

        Args:
            assets: List of asset profiles.
            horizon_days: Prediction horizon in days.

        Returns:
            Dict of ticker → P(worst-of).
        """
        if not assets:
            return {}

        scores: dict[str, float] = {}
        for a in assets:
            risk_score = 0.0

            if a.distance_to_barrier_pct is not None:
                if a.distance_to_barrier_pct < 0.10:
                    risk_score += 40
                elif a.distance_to_barrier_pct < 0.20:
                    risk_score += 25
                elif a.distance_to_barrier_pct < 0.30:
                    risk_score += 10

            if a.rsi is not None:
                if a.rsi < 30:
                    risk_score += 15
                elif a.rsi > 70:
                    risk_score += 5

            risk_score += min(a.atr_pct * 5, 20)

            if a.implied_vol is not None:
                risk_score += min(a.implied_vol * 30, 20)

            risk_score += min(abs(a.max_drawdown_60d) * 50, 20)

            if not a.is_profitable:
                risk_score += 15

            scores[a.ticker] = max(risk_score, 1.0)

        total = sum(scores.values())
        if total > 0:
            return {t: round(s / total, 4) for t, s in scores.items()}
        n = len(assets)
        return {a.ticker: round(1.0 / n, 4) for a in assets}
