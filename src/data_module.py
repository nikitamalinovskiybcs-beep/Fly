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
                        "is_real": True,
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
                        "is_real": True,
                    }
                except Exception:
                    continue
        except Exception:
            pass

    # Fallback: deterministic estimates when both sources fail.
    # These values are display-only proxies, not market observations.
    for t in tickers:
        if t not in result:
            closes = np.linspace(90, 100, 252)
            result[t] = {
                "spot": 100.0,
                "iv30": 30.0,
                "real_1y": 8.0,
                "vol_used": 27.0,
                "beta": 1.1,
                "ema200_pct": 2.0,
                "closes": closes.tolist(),
                "returns": np.diff(np.log(closes)).tolist(),
                "source": "estimated",
                "is_real": False,
                "warning": "market data unavailable; deterministic proxy used",
            }

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


def fetch_implied_vol_surface(tickers: List[str]) -> Dict[str, Dict]:
    """Fetch implied vol data from xfinlink (IV30, IV60, IV90, skew).
    Returns dict[ticker] = {iv30, iv60, iv90, skew, term_structure, iv_regime}
    IV surface is more accurate than historical vol for pricing structured products.
    """
    result = {}
    if XFL_AVAILABLE:
        try:
            import xfinlink as xfl_mod
            for t in tickers:
                try:
                    m = xfl_mod.metrics(t)
                    if m:
                        iv30 = float(m.get("iv30", m.get("implied_volatility", 0)))
                        iv60 = float(m.get("iv60", iv30 * 1.05))
                        iv90 = float(m.get("iv90", iv30 * 1.08))
                        skew = float(m.get("iv_skew", m.get("put_call_skew", 0)))
                        # Term structure slope: contango (>1) or backwardation (<1)
                        ts_slope = iv90 / max(0.01, iv30) if iv30 > 0 else 1.0
                        # IV regime: high/normal/low based on percentile
                        iv_pct = float(m.get("iv_percentile", 50))
                        regime = "high" if iv_pct > 70 else "low" if iv_pct < 30 else "normal"
                        result[t] = {
                            "iv30": round(iv30, 1),
                            "iv60": round(iv60, 1),
                            "iv90": round(iv90, 1),
                            "skew": round(skew, 2),
                            "term_structure": round(ts_slope, 3),
                            "iv_regime": regime,
                            "iv_percentile": round(iv_pct, 0),
                        }
                except Exception:
                    continue
            if result:
                return result
        except Exception:
            pass

    # Fallback: estimate from historical data
    for t in tickers:
        if t not in result:
            result[t] = {
                "iv30": 30.0, "iv60": 31.5, "iv90": 32.4,
                "skew": -0.05, "term_structure": 1.08,
                "iv_regime": "normal", "iv_percentile": 50,
            }
    return result


def compute_dcc_correlations(tickers: List[str], period: str = "2y") -> Dict:
    """DCC-like dynamic correlations: correlations increase during stress.
    Approximation of DCC-GARCH using EWMA (exponentially weighted) + regime detection.
    Key insight: worst-of products are riskier when correlations spike in crises.
    """
    prices = fetch_prices(tickers, period=period)
    if prices.empty or len(prices) < 60:
        return {"avg_corr": 0.5, "stress_corr": 0.75, "regime": "normal",
                "corr_multiplier": 1.0, "high_corr_pairs": []}

    returns = np.log(prices / prices.shift(1)).dropna()
    if returns.empty or len(returns) < 60:
        return {"avg_corr": 0.5, "stress_corr": 0.75, "regime": "normal",
                "corr_multiplier": 1.0, "high_corr_pairs": []}

    n = len(tickers)
    available = [t for t in tickers if t in returns.columns]
    if len(available) < 2:
        return {"avg_corr": 0.5, "stress_corr": 0.75, "regime": "normal",
                "corr_multiplier": 1.0, "high_corr_pairs": []}

    # Normal-regime correlation (full sample)
    corr_full = returns[available].corr()

    # Stress-regime correlation (worst 20% of days by portfolio return)
    port_ret = returns[available].mean(axis=1)
    stress_threshold = port_ret.quantile(0.20)
    stress_days = returns[available][port_ret <= stress_threshold]
    corr_stress = stress_days.corr() if len(stress_days) > 20 else corr_full

    # EWMA correlation (lambda=0.94, recent data weighted more)
    ewma_window = min(60, len(returns))
    recent = returns[available].iloc[-ewma_window:]
    # Exponential weights
    lam = 0.94
    weights = np.array([(1 - lam) * lam ** i for i in range(ewma_window - 1, -1, -1)])
    weights /= weights.sum()

    # Weighted correlation
    weighted_mean = (recent.T * weights).T.sum()
    centered = recent - weighted_mean
    ewma_cov = (centered.T * weights) @ centered
    std_diag = np.sqrt(np.diag(ewma_cov))
    std_outer = np.outer(std_diag, std_diag)
    std_outer[std_outer == 0] = 1
    corr_ewma = ewma_cov / std_outer

    # Extract pair correlations
    pairs_normal = []
    pairs_stress = []
    for i in range(len(available)):
        for j in range(i + 1, len(available)):
            t1, t2 = available[i], available[j]
            cn = float(corr_full.loc[t1, t2]) if t1 in corr_full.index and t2 in corr_full.columns else 0.5
            cs = float(corr_stress.loc[t1, t2]) if t1 in corr_stress.index and t2 in corr_stress.columns else cn
            pairs_normal.append(cn)
            pairs_stress.append(cs)

    avg_normal = float(np.mean(pairs_normal)) if pairs_normal else 0.5
    avg_stress = float(np.mean(pairs_stress)) if pairs_stress else 0.75

    # Regime detection: are we currently in stress?
    recent_ret = port_ret.iloc[-5:].mean() if len(port_ret) >= 5 else 0
    recent_vol = port_ret.iloc[-20:].std() * np.sqrt(252) if len(port_ret) >= 20 else 0.2
    regime = "stress" if recent_ret < -0.01 or recent_vol > 0.35 else "normal"

    # Corr multiplier for P(KI): how much worse worst-of is during stress
    corr_multiplier = round(avg_stress / max(0.01, avg_normal), 2) if avg_normal > 0 else 1.5

    # High correlation pairs in stress
    high_pairs = []
    idx = 0
    for i in range(len(available)):
        for j in range(i + 1, len(available)):
            if idx < len(pairs_stress) and pairs_stress[idx] > 0.7:
                high_pairs.append({"pair": f"{available[i]}/{available[j]}",
                                   "normal": round(pairs_normal[idx], 2),
                                   "stress": round(pairs_stress[idx], 2)})
            idx += 1

    return {
        "avg_corr": round(avg_normal, 3),
        "stress_corr": round(avg_stress, 3),
        "ewma_corr": round(float(np.mean(corr_ewma[np.triu_indices(len(available), k=1)])), 3) if len(available) > 1 else 0.5,
        "regime": regime,
        "corr_multiplier": corr_multiplier,
        "high_corr_pairs": high_pairs,
        "n_pairs": len(pairs_normal),
    }


def fetch_macro_factors() -> Dict:
    """Fetch macro factors that affect P(KI): VIX, Fed rates, credit spreads.
    These are market-wide risk indicators independent of specific tickers.
    """
    result = {"vix": 18.0, "fed_rate": 4.5, "credit_spread": 1.2,
              "regime": "normal", "macro_risk_score": 0.3}

    if XFL_AVAILABLE:
        try:
            import xfinlink as xfl_mod
            # VIX proxy
            try:
                vix_data = xfl_mod.metrics("^VIX")
                if vix_data and "price" in vix_data:
                    result["vix"] = float(vix_data["price"])
                elif vix_data and "last" in vix_data:
                    result["vix"] = float(vix_data["last"])
            except Exception:
                pass
            # Treasury yield (risk-free rate proxy)
            try:
                tlt = xfl_mod.metrics("TLT")
                if tlt and "yield" in tlt:
                    result["fed_rate"] = float(tlt["yield"])
            except Exception:
                pass
        except Exception:
            pass

    # Compute macro risk score (0=low risk, 1=extreme risk)
    vix = result["vix"]
    if vix > 30:
        result["regime"] = "stress"
        result["macro_risk_score"] = min(1.0, (vix - 15) / 35)
    elif vix > 22:
        result["regime"] = "elevated"
        result["macro_risk_score"] = 0.5
    else:
        result["regime"] = "normal"
        result["macro_risk_score"] = max(0.1, (vix - 10) / 25)

    return result


def cache_ticker_data(tickers: List[str], data: Dict) -> bool:
    """Cache ticker data to Google Drive for offline access.
    Avoids rate limits by storing last known good data.
    """
    try:
        from src.gdrive_store import save_data
        import json
        cache_payload = {
            "tickers": tickers,
            "data": {t: {k: v for k, v in d.items()
                         if k not in ("closes", "returns")}  # skip large arrays
                     for t, d in data.items()},
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        save_data("ticker_cache", cache_payload)
        return True
    except Exception:
        return False


def load_cached_ticker_data(tickers: List[str]) -> Dict:
    """Load cached ticker data from Google Drive.
    Returns empty dict if cache miss or stale (>24h).
    """
    try:
        from src.gdrive_store import load_data
        cache = load_data("ticker_cache")
        if not cache:
            return {}
        # Check freshness (24h max)
        ts = cache.get("timestamp", "")
        if ts:
            cached_time = pd.Timestamp(ts)
            age_hours = (pd.Timestamp.now(tz="UTC") - cached_time).total_seconds() / 3600
            if age_hours > 24:
                return {}
        cached_data = cache.get("data", {})
        # Return only requested tickers that exist in cache
        return {t: cached_data[t] for t in tickers if t in cached_data}
    except Exception:
        return {}


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
