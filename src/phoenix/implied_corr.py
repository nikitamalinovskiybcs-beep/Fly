"""Implied correlation engine — dispersion-based correlation analysis.

Formula: ρ_impl = (σ_index² - Σ(wi²·σi²)) / (Σ(i≠j) wi·wj·σi·σj)
Uses SPY as index proxy. FREE — only needs options IV data.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.phoenix.models import ImpliedCorrelationResult

logger = logging.getLogger(__name__)


class ImpliedCorrelationEngine:
    """Calculate implied correlation from dispersion trading logic."""

    def __init__(self) -> None:
        from src.phoenix.implied_vol import ImpliedVolEngine
        self._vol_engine = ImpliedVolEngine()

    def calculate(
        self,
        tickers: list[str],
        weights: Optional[list[float]] = None,
    ) -> ImpliedCorrelationResult:
        """Calculate implied correlation for a basket.

        Args:
            tickers: List of ticker symbols.
            weights: Portfolio weights (equal weight if None).

        Returns:
            ImpliedCorrelationResult with implied vs realized correlation.
        """
        n = len(tickers)
        if n < 2:
            return ImpliedCorrelationResult(
                realized_correlation=0.0,
                implied_correlation=0.0,
                correlation_risk_premium=0.0,
                is_overpriced=False,
            )

        w = np.array(weights) if weights else np.ones(n) / n
        w = w / w.sum()

        ivs = np.array([self._vol_engine.get_atm_iv(t) for t in tickers])
        index_iv = self._vol_engine.get_atm_iv("SPY")

        implied_corr = self._dispersion_implied_corr(w, ivs, index_iv)
        realized_corr = self._realized_correlation(tickers, days=60)
        premium = implied_corr - realized_corr

        return ImpliedCorrelationResult(
            realized_correlation=round(realized_corr, 4),
            implied_correlation=round(implied_corr, 4),
            correlation_risk_premium=round(premium, 4),
            is_overpriced=implied_corr > realized_corr,
        )

    def pairwise_implied(self, ticker_a: str, ticker_b: str) -> float:
        """Estimate pairwise implied correlation.

        Uses portfolio variance decomposition:
        σ_p² = wa²σa² + wb²σb² + 2·wa·wb·ρ·σa·σb

        Args:
            ticker_a: First ticker.
            ticker_b: Second ticker.

        Returns:
            Pairwise implied correlation estimate.
        """
        try:
            iv_a = self._vol_engine.get_atm_iv(ticker_a)
            iv_b = self._vol_engine.get_atm_iv(ticker_b)
            index_iv = self._vol_engine.get_atm_iv("SPY")

            w = 0.5
            numerator = index_iv**2 - w**2 * iv_a**2 - w**2 * iv_b**2
            denominator = 2 * w**2 * iv_a * iv_b

            if abs(denominator) < 1e-10:
                return self._realized_pairwise(ticker_a, ticker_b)

            rho = numerator / denominator
            return float(np.clip(rho, -1.0, 1.0))
        except Exception as exc:
            logger.warning("Pairwise implied corr failed: %s", exc)
            return self._realized_pairwise(ticker_a, ticker_b)

    def _dispersion_implied_corr(
        self, weights: np.ndarray, ivs: np.ndarray, index_iv: float,
    ) -> float:
        """Apply dispersion formula.

        ρ_impl = (σ_index² - Σ(wi²·σi²)) / (Σ(i≠j) wi·wj·σi·σj)
        """
        n = len(weights)
        weighted_var_sum = float(np.sum(weights**2 * ivs**2))
        cross_sum = 0.0
        for i in range(n):
            for j in range(n):
                if i != j:
                    cross_sum += weights[i] * weights[j] * ivs[i] * ivs[j]

        if abs(cross_sum) < 1e-10:
            return 0.0

        rho = (index_iv**2 - weighted_var_sum) / cross_sum
        return float(np.clip(rho, -1.0, 1.0))

    def _realized_correlation(self, tickers: list[str], days: int = 60) -> float:
        """Calculate realized correlation from historical returns."""
        try:
            import yfinance as yf
            returns_list = []
            for ticker in tickers:
                hist = yf.Ticker(ticker).history(period=f"{days}d")
                if hist.empty:
                    continue
                ret = hist["Close"].pct_change().dropna()
                returns_list.append(ret)

            if len(returns_list) < 2:
                return 0.0

            min_len = min(len(r) for r in returns_list)
            aligned = np.column_stack([r.values[-min_len:] for r in returns_list])
            corr_matrix = np.corrcoef(aligned, rowvar=False)

            n = corr_matrix.shape[0]
            off_diag = corr_matrix[np.triu_indices(n, k=1)]
            return float(np.mean(off_diag)) if len(off_diag) > 0 else 0.0
        except Exception as exc:
            logger.warning("Realized correlation failed: %s", exc)
            return 0.0

    def _realized_pairwise(self, ticker_a: str, ticker_b: str) -> float:
        """Fallback: realized pairwise correlation."""
        try:
            import yfinance as yf
            hist_a = yf.Ticker(ticker_a).history(period="3mo")["Close"].pct_change().dropna()
            hist_b = yf.Ticker(ticker_b).history(period="3mo")["Close"].pct_change().dropna()
            min_len = min(len(hist_a), len(hist_b))
            if min_len < 10:
                return 0.0
            return float(np.corrcoef(hist_a.values[-min_len:], hist_b.values[-min_len:])[0, 1])
        except Exception:
            return 0.0
