"""Copula analysis — normal vs crisis correlation structure."""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CopulaAnalyzer:
    """Simplified t-copula for tail dependence analysis."""

    def fit(self, returns_df: pd.DataFrame) -> dict:
        """Fit copula and compare normal vs crisis correlation.

        Args:
            returns_df: DataFrame with columns as tickers, rows as returns.

        Returns:
            Dict with normal_corr, crisis_corr, max_crisis_corr.
        """
        if returns_df.shape[1] < 2 or len(returns_df) < 30:
            return {
                "normal_corr": 0.0,
                "crisis_corr": 0.0,
                "max_crisis_corr": 0.0,
                "corr_increase": 0.0,
            }

        normal_corr = self._normal_correlation(returns_df)
        crisis_corr = self._crisis_correlation(returns_df)
        max_crisis = float(np.max(np.abs(crisis_corr[np.triu_indices(crisis_corr.shape[0], k=1)]))) if crisis_corr.shape[0] > 1 else 0.0
        avg_normal = self._avg_off_diagonal(normal_corr)
        avg_crisis = self._avg_off_diagonal(crisis_corr)

        return {
            "normal_corr": round(avg_normal, 4),
            "crisis_corr": round(avg_crisis, 4),
            "max_crisis_corr": round(max_crisis, 4),
            "corr_increase": round(avg_crisis - avg_normal, 4),
            "normal_matrix": normal_corr.tolist(),
            "crisis_matrix": crisis_corr.tolist(),
        }

    def _normal_correlation(self, returns_df: pd.DataFrame) -> np.ndarray:
        """Full-sample Pearson correlation."""
        return returns_df.corr().values

    def _crisis_correlation(self, returns_df: pd.DataFrame, pct: float = 5.0) -> np.ndarray:
        """Correlation using only bottom 5% of return days."""
        market_ret = returns_df.mean(axis=1)
        threshold = np.percentile(market_ret.dropna(), pct)
        crisis_mask = market_ret <= threshold
        crisis_data = returns_df.loc[crisis_mask]

        if len(crisis_data) < 5:
            return self._normal_correlation(returns_df)
        return crisis_data.corr().values

    def _avg_off_diagonal(self, matrix: np.ndarray) -> float:
        """Average absolute off-diagonal correlation."""
        n = matrix.shape[0]
        if n < 2:
            return 0.0
        off_diag = matrix[np.triu_indices(n, k=1)]
        return float(np.mean(np.abs(off_diag)))
