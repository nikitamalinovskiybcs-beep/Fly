"""Dividend analysis — forecast dividends and barrier impact.

On ex-dates, spot drops by approximately the dividend amount.
If spot is close to barrier, dividends can push through.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.phoenix.models import DividendForecast

logger = logging.getLogger(__name__)


class DividendAnalyzer:
    """Forecast dividends and their impact on barrier proximity."""

    def analyze(self, ticker: str, barrier: float) -> DividendForecast:
        """Full dividend analysis.

        Args:
            ticker: Ticker symbol.
            barrier: Barrier level for the structured product.

        Returns:
            DividendForecast with yield, ex-dates, and barrier impact.
        """
        try:
            import yfinance as yf
            tk = yf.Ticker(ticker)

            info = tk.info
            spot = float(info.get("regularMarketPrice", info.get("previousClose", 100)))

            divs = tk.dividends
            current_yield = self._calc_current_yield(divs, spot)
            forward_yield = self._calc_forward_yield(divs, spot, info)
            ex_dates = self._forecast_ex_dates(divs)
            impact = self._calc_barrier_impact(divs, spot, barrier)

            return DividendForecast(
                ticker=ticker,
                current_yield=round(current_yield, 4),
                forward_yield=round(forward_yield, 4),
                ex_dates_next_12m=ex_dates,
                impact_on_barrier_pct=round(impact, 4),
            )
        except Exception as exc:
            logger.warning("Dividend analysis failed for %s: %s", ticker, exc)
            return DividendForecast(
                ticker=ticker, current_yield=0.0,
                forward_yield=0.0, impact_on_barrier_pct=0.0,
            )

    def _calc_current_yield(self, divs: pd.Series, spot: float) -> float:
        """Current yield = last 4 quarters / spot."""
        if divs.empty or spot <= 0:
            return 0.0
        try:
            last_year = divs.last("365D")
            annual_div = float(last_year.sum())
            return annual_div / spot
        except Exception:
            return 0.0

    def _calc_forward_yield(
        self, divs: pd.Series, spot: float, info: dict,
    ) -> float:
        """Forward yield from analyst estimate or extrapolation."""
        try:
            fwd = info.get("dividendYield")
            if fwd and fwd > 0:
                return float(fwd)
        except Exception:
            pass
        return self._calc_current_yield(divs, spot)

    def _forecast_ex_dates(self, divs: pd.Series) -> list[str]:
        """Estimate next 4 quarterly ex-dates."""
        if divs.empty:
            return []
        try:
            from datetime import datetime, timedelta
            recent = divs.index[-4:] if len(divs) >= 4 else divs.index
            if len(recent) < 2:
                return []

            intervals = []
            for i in range(1, len(recent)):
                delta = (recent[i] - recent[i - 1]).days
                intervals.append(delta)
            avg_interval = int(np.mean(intervals)) if intervals else 90

            last_date = recent[-1]
            if hasattr(last_date, "to_pydatetime"):
                last_date = last_date.to_pydatetime()
            last_date = last_date.replace(tzinfo=None)

            forecasts = []
            for i in range(1, 5):
                next_date = last_date + timedelta(days=avg_interval * i)
                forecasts.append(next_date.strftime("%Y-%m-%d"))
            return forecasts
        except Exception:
            return []

    def _calc_barrier_impact(
        self, divs: pd.Series, spot: float, barrier: float,
    ) -> float:
        """How much dividends reduce effective distance to barrier.

        impact = annual_dividend / spot (as %)
        """
        if divs.empty or spot <= 0:
            return 0.0
        try:
            last_year = divs.last("365D")
            annual_div = float(last_year.sum())
            return annual_div / spot
        except Exception:
            return 0.0
