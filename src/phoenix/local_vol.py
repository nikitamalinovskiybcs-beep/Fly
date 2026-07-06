"""Dupire local volatility surface.

σ_local²(K,T) = 2·(∂C/∂T + r·K·∂C/∂K + q·C) / (K²·∂²C/∂K²)

Simplified implementation using finite differences on market option prices.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LocalVolSurface:
    """Dupire local volatility from options data."""

    def __init__(self, risk_free_rate: float = 0.05) -> None:
        self._r = risk_free_rate
        self._grid: Optional[dict] = None

    def build(self, ticker: str) -> dict:
        """Build local volatility surface from options chain.

        Args:
            ticker: Ticker symbol.

        Returns:
            Dict with grid, local_vols, spot, and metadata.
        """
        try:
            import yfinance as yf
            tk = yf.Ticker(ticker)
            expiries = tk.options
            if not expiries or len(expiries) < 2:
                return {"ticker": ticker, "error": "insufficient options data"}

            info = tk.info
            spot = float(info.get("regularMarketPrice", info.get("previousClose", 100)))
            selected = expiries[:4]

            strikes_list: list[float] = []
            times_list: list[float] = []
            prices_grid: list[list[float]] = []

            from datetime import datetime
            today = datetime.now().date()

            for expiry in selected:
                exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                t = max((exp_date - today).days / 365.25, 0.01)
                times_list.append(t)

                chain = tk.option_chain(expiry)
                calls = chain.calls
                if calls.empty:
                    continue

                valid = calls[calls["lastPrice"] > 0].copy()
                if valid.empty:
                    continue

                if not strikes_list:
                    low = spot * 0.80
                    high = spot * 1.20
                    mask = (valid["strike"] >= low) & (valid["strike"] <= high)
                    strikes_list = sorted(valid.loc[mask, "strike"].tolist())
                    if len(strikes_list) < 3:
                        strikes_list = sorted(valid["strike"].tolist())[:10]

                row = []
                for k in strikes_list:
                    idx = (valid["strike"] - k).abs().idxmin()
                    row.append(float(valid.loc[idx, "lastPrice"]))
                prices_grid.append(row)

            if len(prices_grid) < 2 or len(strikes_list) < 3:
                return {"ticker": ticker, "error": "insufficient grid data"}

            strikes = np.array(strikes_list)
            times = np.array(times_list[:len(prices_grid)])
            prices = np.array(prices_grid)

            local_vols = self._compute_dupire(prices, strikes, times, spot)

            self._grid = {
                "ticker": ticker,
                "spot": spot,
                "strikes": strikes.tolist(),
                "times": times.tolist(),
                "prices": prices.tolist(),
                "local_vols": local_vols.tolist(),
            }
            return self._grid
        except Exception as exc:
            logger.warning("Local vol surface build failed for %s: %s", ticker, exc)
            return {"ticker": ticker, "error": str(exc)}

    def get_local_vol(self, strike: float, time_to_expiry: float) -> float:
        """Interpolate local vol at any (K, T) point.

        Args:
            strike: Strike price.
            time_to_expiry: Time to expiry in years.

        Returns:
            Local volatility. Falls back to 0.3 if surface not built.
        """
        if self._grid is None or "local_vols" not in self._grid:
            return 0.30

        try:
            strikes = np.array(self._grid["strikes"])
            times = np.array(self._grid["times"])
            lvols = np.array(self._grid["local_vols"])

            k_idx = int(np.argmin(np.abs(strikes - strike)))
            t_idx = int(np.argmin(np.abs(times - time_to_expiry)))

            t_idx = min(t_idx, lvols.shape[0] - 1)
            k_idx = min(k_idx, lvols.shape[1] - 1)

            return float(lvols[t_idx, k_idx])
        except Exception:
            return 0.30

    def _compute_dupire(
        self, prices: np.ndarray, strikes: np.ndarray,
        times: np.ndarray, spot: float,
    ) -> np.ndarray:
        """Apply Dupire formula using finite differences.

        σ_local²(K,T) = 2·(∂C/∂T + r·K·∂C/∂K) / (K²·∂²C/∂K²)
        """
        n_t, n_k = prices.shape
        local_vols = np.full((n_t, n_k), 0.30)

        for i in range(n_t):
            for j in range(1, n_k - 1):
                try:
                    dC_dK = (prices[i, j + 1] - prices[i, j - 1]) / (strikes[j + 1] - strikes[j - 1])
                    d2C_dK2 = (
                        prices[i, j + 1] - 2 * prices[i, j] + prices[i, j - 1]
                    ) / ((strikes[j + 1] - strikes[j - 1]) / 2) ** 2

                    if i < n_t - 1:
                        dC_dT = (prices[i + 1, j] - prices[i, j]) / (times[i + 1] - times[i])
                    elif i > 0:
                        dC_dT = (prices[i, j] - prices[i - 1, j]) / (times[i] - times[i - 1])
                    else:
                        dC_dT = 0.0

                    numerator = 2.0 * (dC_dT + self._r * strikes[j] * dC_dK)
                    denominator = strikes[j] ** 2 * d2C_dK2

                    if denominator > 1e-6:
                        lv_sq = numerator / denominator
                        if lv_sq > 0:
                            local_vols[i, j] = float(np.sqrt(lv_sq))
                except Exception:
                    continue

        return local_vols
