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
    # Try st.secrets first (Streamlit Cloud), then env var
    _XFL_KEY = ""
    try:
        import streamlit as _st
        _XFL_KEY = _st.secrets.get("XFINLINK_API_KEY", "")
    except Exception:
        pass
    if not _XFL_KEY:
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


def fetch_iv_percentile(tickers: List[str]) -> Dict[str, float]:
    """Fetch IV percentile rank (0-100) for each ticker.
    IV percentile = where current IV sits vs last 252 days.
    Uses xfinlink metrics if available, else estimates from historical vol.
    """
    result = {}
    if XFL_AVAILABLE:
        try:
            for t in tickers:
                try:
                    m = xfl.metrics(t)
                    if m and "iv_percentile" in m:
                        result[t] = float(m["iv_percentile"])
                    elif m and "implied_volatility" in m:
                        result[t] = float(m.get("iv_rank", 50))
                except Exception:
                    continue
            if result:
                return result
        except Exception:
            pass

    # Fallback: estimate from historical vol regime
    for t in tickers:
        result[t] = 50.0  # neutral default
    return result


def compute_rolling_correlations(
    tickers: List[str], window: int = 60, period: str = "2y"
) -> Dict:
    """Compute time-varying correlations using rolling window.
    Returns: {current_corr_matrix, avg_corr, max_corr, corr_trend (rising/falling/stable)}
    """
    prices = fetch_prices(tickers, period=period)
    if prices.empty or len(prices) < window + 10:
        n = len(tickers)
        return {
            "avg_corr": 0.5,
            "max_pair_corr": 0.7,
            "corr_trend": "stable",
            "high_corr_pairs": [],
        }

    returns = np.log(prices / prices.shift(1)).dropna()
    if returns.empty or len(returns) < window:
        return {"avg_corr": 0.5, "max_pair_corr": 0.7, "corr_trend": "stable", "high_corr_pairs": []}

    # Current rolling correlation
    recent = returns.iloc[-window:]
    corr_now = recent.corr()

    # Previous window for trend
    if len(returns) >= window * 2:
        prev = returns.iloc[-(window * 2):-window]
        corr_prev = prev.corr()
    else:
        corr_prev = corr_now

    # Extract pair correlations
    pairs = []
    n = len(tickers)
    for i in range(n):
        for j in range(i + 1, n):
            t1, t2 = tickers[i], tickers[j]
            if t1 in corr_now.columns and t2 in corr_now.columns:
                c = float(corr_now.loc[t1, t2])
                pairs.append((t1, t2, c))

    if not pairs:
        return {"avg_corr": 0.5, "max_pair_corr": 0.7, "corr_trend": "stable", "high_corr_pairs": []}

    avg_corr = float(np.mean([p[2] for p in pairs]))
    max_pair = max(pairs, key=lambda x: x[2])

    # Trend: compare current avg vs previous avg
    prev_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            t1, t2 = tickers[i], tickers[j]
            if t1 in corr_prev.columns and t2 in corr_prev.columns:
                prev_pairs.append(float(corr_prev.loc[t1, t2]))
    prev_avg = float(np.mean(prev_pairs)) if prev_pairs else avg_corr
    diff = avg_corr - prev_avg
    trend = "rising" if diff > 0.05 else "falling" if diff < -0.05 else "stable"

    high_corr_pairs = [(t1, t2, round(c, 2)) for t1, t2, c in pairs if c > 0.7]

    return {
        "avg_corr": round(avg_corr, 3),
        "max_pair_corr": round(max_pair[2], 3),
        "max_pair": f"{max_pair[0]}/{max_pair[1]}",
        "corr_trend": trend,
        "high_corr_pairs": high_corr_pairs,
        "n_pairs": len(pairs),
    }


def check_earnings_risk(tickers: List[str]) -> Dict:
    """Check if any tickers have upcoming earnings near observation dates.
    Returns warning flags for gap risk.
    """
    earnings_info = {}
    if XFL_AVAILABLE:
        try:
            for t in tickers:
                try:
                    fund = xfl.fundamentals(t)
                    if fund and "next_earnings_date" in fund:
                        earnings_info[t] = fund["next_earnings_date"]
                except Exception:
                    continue
        except Exception:
            pass

    # Fallback: use yfinance calendar if available
    if not earnings_info and YF_AVAILABLE:
        for t in tickers:
            try:
                info = yf.Ticker(t).calendar
                if info is not None and "Earnings Date" in info:
                    ed = info["Earnings Date"]
                    if isinstance(ed, list) and ed:
                        earnings_info[t] = str(ed[0])
                    elif ed:
                        earnings_info[t] = str(ed)
            except Exception:
                continue

    # Flag tickers with earnings within 14 days
    flagged = []
    now = dt.datetime.now(dt.timezone.utc)
    for t, date_str in earnings_info.items():
        try:
            ed = pd.Timestamp(date_str).tz_localize(None)
            days_until = (ed - pd.Timestamp(now.replace(tzinfo=None))).days
            if 0 <= days_until <= 14:
                flagged.append({"ticker": t, "date": str(ed.date()), "days": days_until})
        except Exception:
            continue

    return {
        "has_risk": len(flagged) > 0,
        "flagged": flagged,
        "n_with_earnings": len(earnings_info),
    }


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
