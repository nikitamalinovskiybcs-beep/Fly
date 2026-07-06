"""Barrier risk analysis for worst-of structured products.

Analyzes:
- Distance to barrier
- Gap risk (overnight jump through barrier)
- Digital risk (spot within 2% of barrier at observation)
- Time to barrier at current drift
"""

import logging
from typing import Optional

import numpy as np

from src.phoenix.models import BarrierRiskReport

logger = logging.getLogger(__name__)


class BarrierRiskAnalyzer:
    """Analyze barrier-specific risks for Phoenix/Autocall products."""

    def analyze(
        self,
        ticker: str,
        spot: float,
        barrier: float,
        iv: float = 0.30,
        days_to_next_obs: int = 30,
    ) -> BarrierRiskReport:
        """Full barrier risk analysis.

        Args:
            ticker: Ticker symbol.
            spot: Current spot price.
            barrier: Barrier level.
            iv: Implied volatility.
            days_to_next_obs: Days until next observation date.

        Returns:
            BarrierRiskReport with all risk metrics.
        """
        distance_pct = (spot - barrier) / barrier if barrier > 0 else 0.0

        barrier_delta = self._calc_barrier_delta(spot, barrier, iv, days_to_next_obs)
        gap_risk = self._calc_gap_risk(spot, barrier, iv)
        digital_risk = self._calc_digital_risk(spot, barrier, iv, days_to_next_obs)
        time_to_barrier = self._time_to_barrier(ticker, spot, barrier)

        return BarrierRiskReport(
            ticker=ticker,
            spot=round(spot, 2),
            barrier=round(barrier, 2),
            distance_pct=round(distance_pct, 4),
            barrier_delta=round(barrier_delta, 4),
            gap_risk_overnight=round(gap_risk, 4),
            digital_risk_pct=round(digital_risk, 4),
            time_to_barrier_days=time_to_barrier,
        )

    def _calc_barrier_delta(
        self, spot: float, barrier: float, iv: float, days: int,
    ) -> float:
        """Approximate barrier delta using Black-Scholes down-and-out formula.

        barrier_delta ≈ N(d2) × (barrier/spot)^(2r/σ²)
        """
        if spot <= 0 or barrier <= 0:
            return 0.0
        try:
            from scipy.stats import norm
            r = 0.05
            t = max(days / 365.25, 0.01)
            d2 = (np.log(spot / barrier) + (r - 0.5 * iv**2) * t) / (iv * np.sqrt(t))
            power = 2 * r / (iv**2) if iv > 0 else 0
            barrier_ratio = (barrier / spot) ** power
            return float(norm.cdf(d2) * barrier_ratio)
        except Exception:
            return 0.0

    def _calc_gap_risk(self, spot: float, barrier: float, iv: float) -> float:
        """P(overnight gap through barrier).

        Uses normal approximation with overnight vol ≈ daily vol × 0.6.
        """
        if spot <= 0 or barrier >= spot:
            return 1.0
        try:
            from scipy.stats import norm
            daily_vol = iv / np.sqrt(252)
            overnight_vol = daily_vol * 0.6
            log_return_needed = np.log(barrier / spot)
            return float(norm.cdf(log_return_needed / overnight_vol))
        except Exception:
            return 0.0

    def _calc_digital_risk(
        self, spot: float, barrier: float, iv: float, days: int,
    ) -> float:
        """P(spot within 2% of barrier at any observation date).

        Simple MC estimation.
        """
        if spot <= 0 or barrier <= 0:
            return 0.0
        try:
            n_sims = 5000
            dt = days / 365.25
            daily_vol = iv / np.sqrt(252)
            n_days = max(1, days)

            rng = np.random.default_rng(42)
            paths = spot * np.exp(
                np.cumsum(
                    (0.05 - 0.5 * daily_vol**2) / 252
                    + daily_vol * rng.standard_normal((n_sims, n_days)) / np.sqrt(1),
                    axis=1,
                )
            )

            near_barrier = np.any(
                (paths >= barrier * 0.98) & (paths <= barrier * 1.02), axis=1,
            )
            return float(near_barrier.mean())
        except Exception:
            return 0.0

    def _time_to_barrier(
        self, ticker: str, spot: float, barrier: float,
    ) -> Optional[float]:
        """Estimate days until spot reaches barrier at current drift.

        Returns None if drift is away from barrier.
        """
        try:
            import yfinance as yf
            hist = yf.Ticker(ticker).history(period="1mo")
            if hist.empty or len(hist) < 5:
                return None

            prices = hist["Close"].values
            daily_drift = (prices[-1] / prices[0]) ** (1 / len(prices)) - 1

            if daily_drift >= 0 and barrier < spot:
                return None

            if abs(daily_drift) < 1e-6:
                return None

            log_distance = abs(np.log(barrier / spot))
            abs_drift = abs(daily_drift)
            days_est = log_distance / abs_drift
            return round(days_est, 1) if days_est < 365 else None
        except Exception:
            return None
