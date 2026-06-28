"""
7 free external data sources for improving prediction accuracy.
All sources have graceful fallback if unavailable.
No paid API keys required — all use free tiers or public data.

Sources:
1. Alpha Vantage — earnings surprises, fundamentals (free key)
2. Finnhub — analyst recommendations, insider trading (free key)
3. SEC EDGAR — insider transactions, institutional holdings
4. CBOE — put/call ratio, VIX futures
5. Quandl/Nasdaq Data Link — macro, yield curves
6. OpenBB/yfinance — short interest proxy
7. Stocksera/Finviz — fails-to-deliver, analyst consensus
"""

import json
import urllib.request
import urllib.error
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta

_cache: Dict[str, any] = {}
_TIMEOUT = 8


def _http_get_json(url: str, headers: Optional[Dict] = None) -> Optional[Dict]:
    """Safe HTTP GET returning parsed JSON or None."""
    try:
        hdrs = {"User-Agent": "Mozilla/5.0 Phoenix-Terminal/1.0"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# 1. ALPHA VANTAGE — earnings surprises + fundamentals
# ═══════════════════════════════════════════════════════════════

def get_alpha_vantage_earnings(ticker: str) -> Dict:
    """Earnings surprises from Alpha Vantage (free, 5 req/min).
    Key signal: consistent positive surprises → lower P(KI)."""
    cache_key = f"av_earn_{ticker}"
    if cache_key in _cache:
        return _cache[cache_key]

    api_key = os.environ.get("ALPHA_VANTAGE_KEY", "demo")
    url = f"https://www.alphavantage.co/query?function=EARNINGS&symbol={ticker}&apikey={api_key}"
    data = _http_get_json(url)

    result = {"available": False, "ticker": ticker}
    if data and "quarterlyEarnings" in data:
        quarters = data["quarterlyEarnings"][:8]
        surprises = []
        for q in quarters:
            try:
                surprise_pct = float(q.get("surprisePercentage", 0))
                surprises.append(surprise_pct)
            except (ValueError, TypeError):
                pass

        if surprises:
            result["available"] = True
            result["n_quarters"] = len(surprises)
            result["avg_surprise_pct"] = round(sum(surprises) / len(surprises), 2)
            result["positive_surprises"] = sum(1 for s in surprises if s > 0)
            result["negative_surprises"] = sum(1 for s in surprises if s < 0)
            result["consistency"] = round(result["positive_surprises"] / len(surprises) * 100, 0)
            result["latest_surprise"] = round(surprises[0], 2)
            # Signal: mostly positive surprises → company beats expectations → lower risk
            result["signal"] = "POSITIVE" if result["consistency"] >= 75 else "NEGATIVE" if result["consistency"] <= 25 else "NEUTRAL"

    _cache[cache_key] = result
    return result


# ═══════════════════════════════════════════════════════════════
# 2. FINNHUB — analyst recommendations + insider trading
# ═══════════════════════════════════════════════════════════════

def get_finnhub_recommendations(ticker: str) -> Dict:
    """Analyst buy/sell/hold recommendations from Finnhub (free, 60 req/min).
    Key signal: consensus downgrade → higher P(KI)."""
    cache_key = f"fh_rec_{ticker}"
    if cache_key in _cache:
        return _cache[cache_key]

    api_key = os.environ.get("FINNHUB_KEY", "")
    if not api_key:
        result = {"available": False, "ticker": ticker, "reason": "no_api_key"}
        _cache[cache_key] = result
        return result

    url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={ticker}&token={api_key}"
    data = _http_get_json(url)

    result = {"available": False, "ticker": ticker}
    if data and isinstance(data, list) and len(data) > 0:
        latest = data[0]
        result["available"] = True
        result["buy"] = latest.get("buy", 0)
        result["hold"] = latest.get("hold", 0)
        result["sell"] = latest.get("sell", 0)
        result["strong_buy"] = latest.get("strongBuy", 0)
        result["strong_sell"] = latest.get("strongSell", 0)
        total = result["buy"] + result["hold"] + result["sell"] + result["strong_buy"] + result["strong_sell"]
        if total > 0:
            bullish = (result["buy"] + result["strong_buy"]) / total
            result["bullish_pct"] = round(bullish * 100, 0)
            result["signal"] = "BULLISH" if bullish >= 0.6 else "BEARISH" if bullish <= 0.3 else "NEUTRAL"
        else:
            result["bullish_pct"] = 50
            result["signal"] = "NEUTRAL"
        result["period"] = latest.get("period", "")

    _cache[cache_key] = result
    return result


def get_finnhub_insider(ticker: str) -> Dict:
    """Insider trading from Finnhub. Heavy insider selling → warning signal."""
    cache_key = f"fh_ins_{ticker}"
    if cache_key in _cache:
        return _cache[cache_key]

    api_key = os.environ.get("FINNHUB_KEY", "")
    if not api_key:
        result = {"available": False, "ticker": ticker, "reason": "no_api_key"}
        _cache[cache_key] = result
        return result

    today = datetime.now().strftime("%Y-%m-%d")
    three_months_ago = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    url = f"https://finnhub.io/api/v1/stock/insider-transactions?symbol={ticker}&from={three_months_ago}&to={today}&token={api_key}"
    data = _http_get_json(url)

    result = {"available": False, "ticker": ticker}
    if data and "data" in data:
        transactions = data["data"]
        buys = sum(1 for t in transactions if t.get("transactionType", "").lower() in ("p-purchase", "purchase"))
        sells = sum(1 for t in transactions if t.get("transactionType", "").lower() in ("s-sale", "sale"))
        result["available"] = True
        result["n_transactions"] = len(transactions)
        result["insider_buys"] = buys
        result["insider_sells"] = sells
        result["net_direction"] = "BUYING" if buys > sells * 1.5 else "SELLING" if sells > buys * 1.5 else "NEUTRAL"

    _cache[cache_key] = result
    return result


# ═══════════════════════════════════════════════════════════════
# 3. SEC EDGAR — institutional holdings + insider filings
# ═══════════════════════════════════════════════════════════════

def get_sec_insider_summary(ticker: str) -> Dict:
    """SEC EDGAR insider transaction summary (free, no key).
    Uses SEC full-text search for recent insider filings."""
    cache_key = f"sec_{ticker}"
    if cache_key in _cache:
        return _cache[cache_key]

    result = {"available": False, "ticker": ticker}
    try:
        url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt={(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')}&enddt={datetime.now().strftime('%Y-%m-%d')}&forms=4"
        data = _http_get_json(url)
        if data and "hits" in data:
            n_filings = data["hits"].get("total", {}).get("value", 0)
            result["available"] = True
            result["n_form4_filings"] = n_filings
            result["filing_frequency"] = "HIGH" if n_filings > 20 else "NORMAL" if n_filings > 5 else "LOW"
    except Exception:
        pass

    # Fallback: use yfinance institutional holders
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        inst = stock.institutional_holders
        if inst is not None and not inst.empty:
            result["available"] = True
            result["n_institutional_holders"] = len(inst)
            result["top_holder"] = str(inst.iloc[0, 0]) if len(inst) > 0 else "Unknown"
            total_shares = inst["Shares"].sum() if "Shares" in inst.columns else 0
            result["institutional_shares"] = int(total_shares)
    except Exception:
        pass

    _cache[cache_key] = result
    return result


# ═══════════════════════════════════════════════════════════════
# 4. CBOE — put/call ratio
# ═══════════════════════════════════════════════════════════════

def get_put_call_ratio(ticker: str) -> Dict:
    """Put/Call ratio from options data. High ratio → bearish sentiment."""
    cache_key = f"pcr_{ticker}"
    if cache_key in _cache:
        return _cache[cache_key]

    result = {"available": False, "ticker": ticker}
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if expirations:
            chain = stock.option_chain(expirations[0])
            call_volume = chain.calls["volume"].sum() if "volume" in chain.calls.columns else 0
            put_volume = chain.puts["volume"].sum() if "volume" in chain.puts.columns else 0
            call_oi = chain.calls["openInterest"].sum() if "openInterest" in chain.calls.columns else 0
            put_oi = chain.puts["openInterest"].sum() if "openInterest" in chain.puts.columns else 0

            pcr_volume = round(put_volume / max(call_volume, 1), 2)
            pcr_oi = round(put_oi / max(call_oi, 1), 2)

            result["available"] = True
            result["pcr_volume"] = pcr_volume
            result["pcr_oi"] = pcr_oi
            result["call_volume"] = int(call_volume)
            result["put_volume"] = int(put_volume)
            # Interpretation: PCR > 1.0 = bearish, PCR < 0.7 = bullish
            result["sentiment"] = "BEARISH" if pcr_volume > 1.0 else "BULLISH" if pcr_volume < 0.7 else "NEUTRAL"
    except Exception:
        pass

    _cache[cache_key] = result
    return result


# ═══════════════════════════════════════════════════════════════
# 5. QUANDL / NASDAQ DATA LINK — macro + yield curves
# ═══════════════════════════════════════════════════════════════

def get_quandl_macro() -> Dict:
    """Macro data from Nasdaq Data Link (free tier, 50 req/day).
    Yield curve shape is a strong recession predictor."""
    if "quandl_macro" in _cache:
        return _cache["quandl_macro"]

    api_key = os.environ.get("QUANDL_KEY", "")
    result = {"available": False}

    # Fallback to FRED data if no Quandl key
    try:
        from src.fred_data import get_fred_data
        fred = get_fred_data()
        result["available"] = True
        result["source"] = "fred_fallback"
        result["yield_curve_slope"] = fred.get("yield_curve_slope", 0.2)
        result["yield_curve_inverted"] = fred.get("yield_curve_inverted", False)
        result["vix"] = fred.get("vix", 20.0)
        result["credit_spread"] = fred.get("credit_spread", 1.5)
        result["recession_signal"] = fred.get("yield_curve_inverted", False)
    except Exception:
        pass

    if api_key:
        # Try Nasdaq Data Link for additional data
        try:
            url = f"https://data.nasdaq.com/api/v3/datasets/FRED/T10Y2Y/data.json?rows=1&api_key={api_key}"
            data = _http_get_json(url)
            if data and "dataset_data" in data:
                rows = data["dataset_data"].get("data", [])
                if rows:
                    spread = float(rows[0][1])
                    result["available"] = True
                    result["source"] = "quandl"
                    result["yield_curve_slope"] = round(spread, 2)
                    result["yield_curve_inverted"] = spread < 0
                    result["recession_signal"] = spread < -0.5
        except Exception:
            pass

    _cache["quandl_macro"] = result
    return result


# ═══════════════════════════════════════════════════════════════
# 6. SHORT INTEREST (yfinance proxy)
# ═══════════════════════════════════════════════════════════════

def get_short_interest(ticker: str) -> Dict:
    """Short interest proxy from yfinance. High SI → risk of squeeze or decline."""
    cache_key = f"si_{ticker}"
    if cache_key in _cache:
        return _cache[cache_key]

    result = {"available": False, "ticker": ticker}
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        short_pct = info.get("shortPercentOfFloat", 0)
        short_ratio = info.get("shortRatio", 0)  # days to cover

        if short_pct or short_ratio:
            result["available"] = True
            result["short_pct_float"] = round(float(short_pct) * 100 if short_pct < 1 else float(short_pct), 2)
            result["short_ratio"] = round(float(short_ratio), 2)
            # High short interest (>10%) = elevated risk
            result["risk_level"] = "HIGH" if result["short_pct_float"] > 10 else "ELEVATED" if result["short_pct_float"] > 5 else "NORMAL"
    except Exception:
        pass

    _cache[cache_key] = result
    return result


# ═══════════════════════════════════════════════════════════════
# 7. FINVIZ — analyst consensus + targets
# ═══════════════════════════════════════════════════════════════

def get_analyst_targets(ticker: str) -> Dict:
    """Analyst price targets and consensus from yfinance (Finviz alternative)."""
    cache_key = f"targets_{ticker}"
    if cache_key in _cache:
        return _cache[cache_key]

    result = {"available": False, "ticker": ticker}
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        target_mean = info.get("targetMeanPrice")
        target_low = info.get("targetLowPrice")
        target_high = info.get("targetHighPrice")
        current = info.get("currentPrice", info.get("regularMarketPrice"))
        recommendation = info.get("recommendationKey", "")
        n_analysts = info.get("numberOfAnalystOpinions", 0)

        if target_mean and current:
            result["available"] = True
            result["current_price"] = round(float(current), 2)
            result["target_mean"] = round(float(target_mean), 2)
            result["target_low"] = round(float(target_low), 2) if target_low else None
            result["target_high"] = round(float(target_high), 2) if target_high else None
            result["upside_pct"] = round((float(target_mean) / float(current) - 1) * 100, 1)
            result["downside_to_low"] = round((float(target_low) / float(current) - 1) * 100, 1) if target_low else None
            result["recommendation"] = recommendation
            result["n_analysts"] = int(n_analysts) if n_analysts else 0
            # If analyst target is below current price → bearish
            result["signal"] = "BULLISH" if result["upside_pct"] > 10 else "BEARISH" if result["upside_pct"] < -5 else "NEUTRAL"
    except Exception:
        pass

    _cache[cache_key] = result
    return result


# ═══════════════════════════════════════════════════════════════
# AGGREGATOR — fetch all sources for a basket
# ═══════════════════════════════════════════════════════════════

def fetch_all_external_data(tickers: List[str]) -> Dict:
    """Fetch all 7 external data sources for a basket of tickers.
    Returns aggregated results with per-ticker and basket-level signals."""
    result = {
        "macro": get_quandl_macro(),
        "per_ticker": {},
        "basket_signals": {},
        "sources_available": 0,
        "sources_total": 7,
    }

    # Per-ticker data (limit to 6 tickers to avoid rate limiting)
    for t in tickers[:6]:
        ticker_data = {
            "earnings": get_alpha_vantage_earnings(t),
            "put_call": get_put_call_ratio(t),
            "short_interest": get_short_interest(t),
            "analyst_targets": get_analyst_targets(t),
            "sec_insider": get_sec_insider_summary(t),
        }

        # Finnhub (only if key available)
        finnhub_key = os.environ.get("FINNHUB_KEY", "")
        if finnhub_key:
            ticker_data["recommendations"] = get_finnhub_recommendations(t)
            ticker_data["insider_trading"] = get_finnhub_insider(t)

        result["per_ticker"][t] = ticker_data

    # Count available sources
    available = set()
    if result["macro"].get("available"):
        available.add("macro")
    for t, td in result["per_ticker"].items():
        for source, data in td.items():
            if isinstance(data, dict) and data.get("available"):
                available.add(source)
    result["sources_available"] = len(available)

    # Aggregate basket-level signals
    signals = _compute_basket_signals(result)
    result["basket_signals"] = signals

    return result


def _compute_basket_signals(data: Dict) -> Dict:
    """Compute aggregate signals from all data sources for scoring adjustment."""
    signals = {
        "earnings_quality": 0,      # -5 to +5 score adjustment
        "analyst_consensus": 0,     # -3 to +3
        "options_sentiment": 0,     # -3 to +3
        "short_interest_risk": 0,   # -3 to 0
        "insider_signal": 0,        # -2 to +2
        "macro_risk": 0,            # -5 to 0
        "total_adjustment": 0,
    }

    per_ticker = data.get("per_ticker", {})
    n_tickers = max(len(per_ticker), 1)

    # 1. Earnings quality
    surprise_scores = []
    for t, td in per_ticker.items():
        earn = td.get("earnings", {})
        if earn.get("available"):
            consistency = earn.get("consistency", 50)
            surprise_scores.append((consistency - 50) / 25)  # normalize to [-2, +2]
    if surprise_scores:
        signals["earnings_quality"] = round(sum(surprise_scores) / len(surprise_scores) * 2.5, 1)

    # 2. Analyst consensus
    upside_scores = []
    for t, td in per_ticker.items():
        targets = td.get("analyst_targets", {})
        if targets.get("available"):
            upside = targets.get("upside_pct", 0)
            upside_scores.append(min(3, max(-3, upside / 10)))
    if upside_scores:
        signals["analyst_consensus"] = round(sum(upside_scores) / len(upside_scores), 1)

    # 3. Options sentiment (put/call ratio)
    pcr_scores = []
    for t, td in per_ticker.items():
        pcr = td.get("put_call", {})
        if pcr.get("available"):
            pcr_vol = pcr.get("pcr_volume", 1.0)
            # PCR > 1.2 = very bearish (-3), PCR < 0.5 = very bullish (+3)
            score = (1.0 - pcr_vol) * 3
            pcr_scores.append(min(3, max(-3, score)))
    if pcr_scores:
        signals["options_sentiment"] = round(sum(pcr_scores) / len(pcr_scores), 1)

    # 4. Short interest risk
    si_penalties = []
    for t, td in per_ticker.items():
        si = td.get("short_interest", {})
        if si.get("available"):
            si_pct = si.get("short_pct_float", 0)
            if si_pct > 15:
                si_penalties.append(-3)
            elif si_pct > 10:
                si_penalties.append(-2)
            elif si_pct > 5:
                si_penalties.append(-1)
            else:
                si_penalties.append(0)
    if si_penalties:
        signals["short_interest_risk"] = round(sum(si_penalties) / len(si_penalties), 1)

    # 5. Insider signal
    for t, td in per_ticker.items():
        insider = td.get("insider_trading", td.get("sec_insider", {}))
        if isinstance(insider, dict) and insider.get("available"):
            direction = insider.get("net_direction", "NEUTRAL")
            if direction == "BUYING":
                signals["insider_signal"] += 1
            elif direction == "SELLING":
                signals["insider_signal"] -= 1
    signals["insider_signal"] = round(min(2, max(-2, signals["insider_signal"] / n_tickers)), 1)

    # 6. Macro risk
    macro = data.get("macro", {})
    if macro.get("available"):
        if macro.get("recession_signal"):
            signals["macro_risk"] = -5
        elif macro.get("yield_curve_inverted"):
            signals["macro_risk"] = -3
        vix = macro.get("vix", 20)
        if vix > 30:
            signals["macro_risk"] = min(signals["macro_risk"], -4)
        elif vix > 25:
            signals["macro_risk"] = min(signals["macro_risk"], -2)

    # Total
    signals["total_adjustment"] = round(sum(v for k, v in signals.items() if k != "total_adjustment"), 1)
    signals["total_adjustment"] = min(10, max(-15, signals["total_adjustment"]))

    return signals
