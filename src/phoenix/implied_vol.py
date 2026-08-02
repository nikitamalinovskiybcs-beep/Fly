"""Implied volatility engine — extract IV from yfinance options chains.

FREE data source — no Bloomberg needed. Uses yfinance options chain
to extract ATM IV, vol smile, skew, and IV percentile.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.phoenix.models import VolPoint, VolSurface

logger = logging.getLogger(__name__)


class ImpliedVolEngine:
    """Extract implied volatility from yfinance options data."""

    def get_atm_iv(self, ticker: str) -> float:
        """Get ATM implied volatility for a ticker.

        Args:
            ticker: Ticker symbol.

        Returns:
            ATM IV as decimal (e.g. 0.32 = 32%). Falls back to historical estimate.
        """
        try:
            import yfinance as yf
            tk = yf.Ticker(ticker)
            expiries = tk.options
            if not expiries:
                return self._historical_vol_estimate(ticker)

            target_expiry = self._pick_nearest_monthly(expiries)
            if not target_expiry:
                return self._historical_vol_estimate(ticker)

            chain = tk.option_chain(target_expiry)
            spot = self._get_spot(tk)
            if spot <= 0:
                return self._historical_vol_estimate(ticker)

            atm_iv = self._extract_atm_iv(chain, spot)
            return atm_iv if atm_iv > 0 else self._historical_vol_estimate(ticker)
        except Exception as exc:
            logger.warning("IV fetch failed for %s: %s", ticker, exc)
            return self._historical_vol_estimate(ticker)

    def get_vol_smile(self, ticker: str) -> list[VolPoint]:
        """Extract IV at multiple strikes and expiries.

        Args:
            ticker: Ticker symbol.

        Returns:
            List of VolPoint for the vol surface.
        """
        points: list[VolPoint] = []
        try:
            import yfinance as yf
            tk = yf.Ticker(ticker)
            expiries = tk.options
            if not expiries:
                return points

            spot = self._get_spot(tk)
            if spot <= 0:
                return points

            strike_pcts = [0.80, 0.90, 1.00, 1.10, 1.20]
            selected_expiries = expiries[:3]

            for expiry in selected_expiries:
                chain = tk.option_chain(expiry)
                days = self._days_to_expiry(expiry)
                for pct in strike_pcts:
                    target_strike = spot * pct
                    iv = self._iv_at_strike(chain, target_strike)
                    if iv > 0:
                        points.append(VolPoint(
                            strike=round(target_strike, 2),
                            expiry_days=days, iv=round(iv, 4),
                        ))
        except Exception as exc:
            logger.warning("Vol smile failed for %s: %s", ticker, exc)
        return points

    def get_skew(self, ticker: str) -> float:
        """Get put/call IV skew.

        Skew = IV(90% strike put) / IV(110% strike call).
        > 1.0 means bearish skew (market expects downside).

        Args:
            ticker: Ticker symbol.

        Returns:
            Skew ratio. 1.0 if unavailable.
        """
        try:
            import yfinance as yf
            tk = yf.Ticker(ticker)
            expiries = tk.options
            if not expiries:
                return 1.0

            target = self._pick_nearest_monthly(expiries)
            if not target:
                return 1.0

            chain = tk.option_chain(target)
            spot = self._get_spot(tk)
            if spot <= 0:
                return 1.0

            put_iv = self._iv_at_strike_puts(chain.puts, spot * 0.90)
            call_iv = self._iv_at_strike_calls(chain.calls, spot * 1.10)

            if call_iv > 0 and put_iv > 0:
                return round(put_iv / call_iv, 4)
            return 1.0
        except Exception as exc:
            logger.warning("Skew failed for %s: %s", ticker, exc)
            return 1.0

    def get_iv_percentile(self, ticker: str, lookback_days: int = 252) -> float:
        """Get IV percentile vs last year.

        Args:
            ticker: Ticker symbol.
            lookback_days: Historical lookback period.

        Returns:
            Percentile 0.0-1.0. 0.5 if unavailable.
        """
        try:
            import yfinance as yf
            tk = yf.Ticker(ticker)
            hist = tk.history(period="1y")
            if hist.empty or len(hist) < 30:
                return 0.5

            returns = hist["Close"].pct_change().dropna()
            rolling_vol = returns.rolling(30).std() * np.sqrt(252)
            rolling_vol = rolling_vol.dropna()
            if rolling_vol.empty:
                return 0.5

            current_vol = float(rolling_vol.iloc[-1])
            percentile = float((rolling_vol < current_vol).mean())
            return round(percentile, 4)
        except Exception as exc:
            logger.warning("IV percentile failed for %s: %s", ticker, exc)
            return 0.5

    def basket_iv_summary(self, tickers: list[str]) -> dict[str, VolSurface]:
        """Get VolSurface for each ticker in a basket.

        Args:
            tickers: List of ticker symbols.

        Returns:
            Dict of ticker -> VolSurface.
        """
        result: dict[str, VolSurface] = {}
        for ticker in tickers:
            atm = self.get_atm_iv(ticker)
            skew = self.get_skew(ticker)
            pct = self.get_iv_percentile(ticker)
            smile = self.get_vol_smile(ticker)
            result[ticker] = VolSurface(
                ticker=ticker, atm_iv=atm, skew_25d=skew,
                term_structure=smile, iv_percentile_1y=pct,
            )
        return result

    def _get_spot(self, tk: object) -> float:
        """Get current spot price."""
        try:
            info = tk.info
            return float(info.get("regularMarketPrice", info.get("previousClose", 0)))
        except Exception:
            try:
                hist = tk.history(period="1d")
                return float(hist["Close"].iloc[-1]) if not hist.empty else 0.0
            except Exception:
                return 0.0

    def _pick_nearest_monthly(self, expiries: list[str]) -> Optional[str]:
        """Pick expiry between 14 and 60 days out."""
        from datetime import datetime
        today = datetime.now().date()
        for exp in expiries:
            try:
                exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
                days = (exp_date - today).days
                if 14 <= days <= 60:
                    return exp
            except ValueError:
                continue
        return expiries[0] if expiries else None

    def _days_to_expiry(self, expiry: str) -> int:
        """Calculate days to expiry."""
        from datetime import datetime
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            return max(1, (exp_date - datetime.now().date()).days)
        except ValueError:
            return 30

    def _extract_atm_iv(self, chain: object, spot: float) -> float:
        """Extract ATM IV from options chain."""
        try:
            calls = chain.calls
            puts = chain.puts
            call_iv = self._iv_at_strike_calls(calls, spot)
            put_iv = self._iv_at_strike_puts(puts, spot)
            if call_iv > 0 and put_iv > 0:
                return (call_iv + put_iv) / 2
            return call_iv if call_iv > 0 else put_iv
        except Exception:
            return 0.0

    def _iv_at_strike(self, chain: object, target_strike: float) -> float:
        """Find IV closest to target strike from calls."""
        return self._iv_at_strike_calls(chain.calls, target_strike)

    def _iv_at_strike_calls(self, calls: pd.DataFrame, target: float) -> float:
        """Find IV for calls nearest to target strike."""
        try:
            if calls.empty or "impliedVolatility" not in calls.columns:
                return 0.0
            idx = (calls["strike"] - target).abs().idxmin()
            return float(calls.loc[idx, "impliedVolatility"])
        except Exception:
            return 0.0

    def _iv_at_strike_puts(self, puts: pd.DataFrame, target: float) -> float:
        """Find IV for puts nearest to target strike."""
        try:
            if puts.empty or "impliedVolatility" not in puts.columns:
                return 0.0
            idx = (puts["strike"] - target).abs().idxmin()
            return float(puts.loc[idx, "impliedVolatility"])
        except Exception:
            return 0.0

    def _historical_vol_estimate(self, ticker: str) -> float:
        """Fallback: estimate IV from historical vol * 1.2."""
        try:
            import yfinance as yf
            hist = yf.Ticker(ticker).history(period="3mo")
            if hist.empty:
                return 0.30
            returns = hist["Close"].pct_change().dropna()
            hist_vol = float(returns.std() * np.sqrt(252))
            return round(hist_vol * 1.2, 4)
        except Exception:
            return 0.30
