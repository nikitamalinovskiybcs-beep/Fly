"""Sector classification and conditional correlation."""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SECTOR_MAP: dict[str, dict] = {
    "Technology": {"mainstream": True, "cyclical": True},
    "Healthcare": {"mainstream": True, "cyclical": False},
    "Financial Services": {"mainstream": True, "cyclical": True},
    "Consumer Cyclical": {"mainstream": True, "cyclical": True},
    "Consumer Defensive": {"mainstream": True, "cyclical": False},
    "Communication Services": {"mainstream": True, "cyclical": True},
    "Industrials": {"mainstream": True, "cyclical": True},
    "Energy": {"mainstream": True, "cyclical": True},
    "Real Estate": {"mainstream": True, "cyclical": True},
    "Basic Materials": {"mainstream": True, "cyclical": True},
    "Utilities": {"mainstream": True, "cyclical": False},
}


def classify(ticker: str) -> str:
    """Get sector for a ticker using yfinance."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return info.get("sector", "Unknown")
    except Exception:
        return "Unknown"


def is_mainstream(sector: str) -> bool:
    """Check if a sector is mainstream."""
    entry = SECTOR_MAP.get(sector, {})
    return entry.get("mainstream", False)


def unique_sector_count(sectors: list[str]) -> int:
    """Count unique non-Unknown sectors."""
    return len(set(s for s in sectors if s != "Unknown"))


def conditional_correlation(
    returns_df: pd.DataFrame,
    sectors: list[str],
    threshold_pct: float = 5.0,
) -> float:
    """Calculate correlation during stress for same-sector assets.

    Args:
        returns_df: DataFrame with columns as tickers.
        sectors: Sector per column.
        threshold_pct: Bottom percentile to define stress.

    Returns:
        Average pairwise correlation during stress.
    """
    if returns_df.shape[1] < 2:
        return 0.0

    try:
        market_ret = returns_df.mean(axis=1)
        threshold = np.percentile(market_ret.dropna(), threshold_pct)
        stress_mask = market_ret <= threshold

        stress_returns = returns_df.loc[stress_mask]
        if len(stress_returns) < 5:
            return 0.0

        corr = stress_returns.corr()
        n = corr.shape[0]
        off_diag = corr.values[np.triu_indices(n, k=1)]
        return float(np.mean(off_diag)) if len(off_diag) > 0 else 0.0
    except Exception:
        return 0.0
