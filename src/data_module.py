"""
Data Module — market data via xfinlink (primary) + yfinance (fallback).

xfinlink: research-grade US equity data (requires XFINLINK_API_KEY env var).
yfinance: free fallback, less reliable on cloud deployments.

Pattern: try xfinlink first → if unavailable/error → yfinance fallback.
"""

import datetime as dt
import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# ── xfinlink setup ──
try:
    import xfinlink as xfl
    _XFL_KEY = os.environ.get("XFINLINK_API_KEY", "")
    if _XFL_KEY:
        xfl.set_api_key(_XFL_KEY)
        XFL_AVAILABLE = True
    else:
        XFL_AVAILABLE = False
except ImportError:
    XFL_AVAILABLE = False

# ── yfinance setup ──
try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False


def fetch_prices(
    tickers: List[str],
    period: str = "2y",
) -> pd.DataFrame:
    """Fetch close prices for a list of tickers.
    Returns DataFrame with tickers as columns, dates as index.
    Uses xfinlink if available, yfinance as fallback.
    """
    if XFL_AVAILABLE:
        try:
            df = xfl.prices(tickers, period=period, fields=["close"])
            if not df.empty:
                if "ticker" in df.columns:
                    # Multi-ticker: pivot to wide format
                    df = df.pivot_table(index="date", columns="ticker", values="close")
                return df.dropna(how="all").ffill()
        except Exception:
            pass

    # Fallback: yfinance
    if YF_AVAILABLE:
        try:
            raw = yf.download(tickers, period=period, progress=False, threads=True)
            if raw.empty:
                return pd.DataFrame()
            if isinstance(raw.columns, pd.MultiIndex):
                closes = raw.xs("Close", axis=1, level=1)
            else:
                closes = raw[["Close"]].rename(columns={"Close": tickers[0]})
            return closes.dropna(how="all").ffill()
        except Exception:
            pass

    return pd.DataFrame()


def fetch_ticker_data(tickers: List[str], period: str = "2y") -> Dict:
    """Fetch comprehensive ticker data (spot, vol, returns, beta).
    Returns dict[ticker] = {spot, iv30, real_1y, vol_used, beta, ema200_pct, ...}
    Used by precompute.py for all market-dependent calculations.
    """
    result = {}

    # Try xfinlink first
    if XFL_AVAILABLE and tickers:
        try:
            for t in tickers:
                try:
                    df = xfl.prices(t, period=period, fields=["close"])
                    if df is None or df.empty or len(df) < 50:
                        continue
                    closes = df["close"].dropna().values
                    returns = np.diff(np.log(closes))
                    vol_1y = float(np.std(returns[-252:]) * np.sqrt(252)) if len(returns) >= 252 else float(np.std(returns) * np.sqrt(252))
                    real_1y = float((closes[-1] / closes[-min(252, len(closes))] - 1)) if len(closes) > 1 else 0
                    ema200 = float(np.mean(closes[-200:])) if len(closes) >= 200 else float(np.mean(closes))
                    ema200_pct = float((closes[-1] / ema200 - 1) * 100) if ema200 > 0 else 0
                    spot = float(closes[-1])
                    beta_est = 1.0 + (vol_1y - 0.2) * 2 if vol_1y > 0.2 else 1.0

                    result[t] = {
                        "spot": round(spot, 2),
                        "iv30": round(vol_1y * 100, 1),
                        "real_1y": round(real_1y * 100, 1),
                        "vol_used": round(vol_1y * 100 * 0.9, 1),
                        "beta": round(float(beta_est), 2),
                        "ema200_pct": round(ema200_pct, 1),
                        "closes": closes,
                        "returns": returns,
                        "source": "xfinlink",
                    }
                except Exception:
                    continue
            if result:
                return result
        except Exception:
            pass

    # Fallback: yfinance batch download
    if YF_AVAILABLE and tickers:
        try:
            raw = yf.download(tickers, period=period, progress=False, threads=True)
            if raw.empty:
                return {}
            for t in tickers:
                try:
                    if len(tickers) == 1:
                        closes_s = raw["Close"]
                    else:
                        closes_s = raw["Close"][t] if t in raw["Close"].columns else None
                    if closes_s is None:
                        continue
                    closes_s = closes_s.dropna()
                    if len(closes_s) < 50:
                        continue
                    closes = closes_s.values
                    returns = np.diff(np.log(closes))
                    vol_1y = float(np.std(returns[-252:]) * np.sqrt(252)) if len(returns) >= 252 else float(np.std(returns) * np.sqrt(252))
                    real_1y = float((closes[-1] / closes[-min(252, len(closes))] - 1)) if len(closes) > 1 else 0
                    ema200 = float(np.mean(closes[-200:])) if len(closes) >= 200 else float(np.mean(closes))
                    ema200_pct = float((closes[-1] / ema200 - 1) * 100) if ema200 > 0 else 0
                    spot = float(closes[-1])
                    beta_est = 1.0 + (vol_1y - 0.2) * 2 if vol_1y > 0.2 else 1.0

                    result[t] = {
                        "spot": round(spot, 2),
                        "iv30": round(vol_1y * 100, 1),
                        "real_1y": round(real_1y * 100, 1),
                        "vol_used": round(vol_1y * 100 * 0.9, 1),
                        "beta": round(float(beta_est), 2),
                        "ema200_pct": round(ema200_pct, 1),
                        "closes": closes,
                        "returns": returns,
                        "source": "yfinance",
                    }
                except Exception:
                    continue
        except Exception:
            pass

    return result


def get_data_source_status() -> str:
    """Return which data source is active."""
    if XFL_AVAILABLE:
        return "xfinlink"
    elif YF_AVAILABLE:
        return "yfinance"
    return "none"


def market_is_closed() -> bool:
    """Rough check — NYSE closes at 21:00 UTC on weekdays."""
    now = dt.datetime.now(dt.timezone.utc)
    if now.weekday() >= 5:
        return True
    return now.hour >= 21 or now.hour < 13
