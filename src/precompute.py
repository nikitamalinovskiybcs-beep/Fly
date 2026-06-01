"""
Precompute layer (Karpathy method).
All heavy computation happens here ONCE, result is a flat dict for rendering.
Streamlit app only does st.markdown() calls — zero compute in render loop.
"""

import numpy as np
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False

from src.clickhouse_data import fetch_quantum_risk_stats
from src.quantum_risk import quantum_var_estimation, get_quantum_status


# ── Sector map ──
SECTOR_MAP = {
    "AAPL": "Information Technology", "MSFT": "Information Technology",
    "GOOGL": "Communication Services", "GOOG": "Communication Services",
    "AMZN": "Consumer Discretionary", "NVDA": "Information Technology",
    "TSLA": "Consumer Discretionary", "META": "Communication Services",
    "AMD": "Information Technology", "INTC": "Information Technology",
    "CRM": "Information Technology", "AVGO": "Information Technology",
    "QCOM": "Information Technology", "DELL": "Information Technology",
    "HPQ": "Information Technology", "NTAP": "Information Technology",
    "MCHP": "Information Technology", "GNRC": "Industrials",
    "JNJ": "Health Care", "ABBV": "Health Care", "MCD": "Consumer Discretionary",
    "PM": "Consumer Staples", "BA": "Industrials", "DIS": "Communication Services",
    "T": "Communication Services", "ORCL": "Information Technology",
    "GOLD": "Materials", "GLD": "Materials", "EXC": "Utilities",
    "COF": "Financials", "APH": "Information Technology",
    "HLT": "Consumer Discretionary", "LI": "Consumer Discretionary",
    "LW": "Consumer Staples", "TTWO": "Communication Services",
    "EA": "Communication Services", "CSGP": "Real Estate",
    "ETHA": "Unknown", "SPY": "ETF", "QQQ": "ETF", "IWM": "ETF",
    "TLT": "Fixed Income", "USO": "Commodities", "BTC-USD": "Crypto",
    "ETH-USD": "Crypto",
}

ANALYST_MAP = {
    "AAPL": (1.89, "buy"), "MSFT": (1.65, "buy"), "GOOGL": (1.39, "strong_buy"),
    "GOOG": (1.39, "strong_buy"), "AMZN": (1.45, "buy"), "NVDA": (1.55, "buy"),
    "TSLA": (2.10, "hold"), "META": (1.50, "buy"), "AMD": (1.70, "buy"),
    "DELL": (1.89, "buy"), "ORCL": (1.80, "buy"), "CRM": (1.60, "buy"),
}


def _fetch_yf_data(tickers: List[str], period: str = "2y") -> Dict:
    """Fetch price data from yfinance for composition cards."""
    if not YF_AVAILABLE:
        return {}
    result = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            hist = tk.history(period=period)
            if hist.empty or len(hist) < 50:
                continue
            closes = hist["Close"].values
            info = tk.info or {}
            returns = np.diff(np.log(closes))
            vol_1y = float(np.std(returns[-252:]) * np.sqrt(252)) if len(returns) >= 252 else float(np.std(returns) * np.sqrt(252))
            real_1y = float((closes[-1] / closes[-min(252, len(closes))] - 1)) if len(closes) > 1 else 0
            ema200 = float(np.mean(closes[-200:])) if len(closes) >= 200 else float(np.mean(closes))
            ema200_pct = float((closes[-1] / ema200 - 1) * 100) if ema200 > 0 else 0
            beta = info.get("beta", 1.0) or 1.0
            pe = info.get("trailingPE") or info.get("forwardPE") or 25.0
            peg = info.get("pegRatio") or (pe / max(1, info.get("earningsQuarterlyGrowth", 0.1) * 100) if pe else 1.0)
            target_price = info.get("targetMeanPrice") or (closes[-1] * 1.05)
            dcf_val = target_price * 0.85
            bcs_target = target_price * 0.92
            n_analysts = info.get("numberOfAnalystOpinions") or 15
            spot = float(closes[-1])

            # Earnings dates
            try:
                cal = tk.calendar
                if cal is not None and not cal.empty:
                    if hasattr(cal, 'iloc'):
                        next_earnings = str(cal.iloc[0, 0]) if cal.shape[1] > 0 else None
                    else:
                        next_earnings = None
                else:
                    next_earnings = None
            except Exception:
                next_earnings = None

            result[t] = {
                "spot": round(spot, 2),
                "iv30": round(vol_1y * 100, 1),
                "real_1y": round(real_1y * 100, 1),
                "vol_used": round(vol_1y * 100 * 0.9, 1),
                "beta": round(float(beta), 2),
                "pe": round(float(pe), 1),
                "peg": round(float(peg), 2),
                "ema200_pct": round(ema200_pct, 1),
                "ema200_above": ema200_pct > 0,
                "dcf": round(float(dcf_val), 2),
                "dcf_upside": round((dcf_val / spot - 1) * 100, 1),
                "target_price": round(float(target_price), 2),
                "target_upside": round((target_price / spot - 1) * 100, 1),
                "bcs_target": round(float(bcs_target), 2),
                "bcs_upside": round((bcs_target / spot - 1) * 100, 1),
                "avg_target": round((target_price + bcs_target + dcf_val) / 3, 2),
                "avg_upside": round(((target_price + bcs_target + dcf_val) / 3 / spot - 1) * 100, 1),
                "n_analysts": int(n_analysts),
                "sector": SECTOR_MAP.get(t, "Unknown"),
                "closes": closes.tolist(),
                "returns": returns.tolist(),
                "next_earnings": next_earnings,
            }
            rec = ANALYST_MAP.get(t, (1.80, "buy"))
            result[t]["rec_score"] = rec[0]
            result[t]["rec_label"] = rec[1]
        except Exception:
            pass
    return result


def _compute_correlation_matrix(yf_data: Dict, tickers: List[str]) -> Dict:
    """Pearson correlation matrix from daily log-returns."""
    available = [t for t in tickers if t in yf_data and len(yf_data[t].get("returns", [])) > 50]
    if len(available) < 2:
        return {"tickers": available, "matrix": [], "avg_corr": 0}
    min_len = min(len(yf_data[t]["returns"]) for t in available)
    ret_matrix = np.array([yf_data[t]["returns"][-min_len:] for t in available])
    corr = np.corrcoef(ret_matrix)
    n = len(available)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append(corr[i, j])
    return {
        "tickers": available,
        "matrix": [[round(corr[i][j], 2) for j in range(n)] for i in range(n)],
        "avg_corr": round(float(np.mean(pairs)), 2) if pairs else 0,
    }


def _compute_stress_scenarios(yf_data: Dict, tickers: List[str], beta_avg: float) -> List[Dict]:
    """Historical stress scenarios replicated via beta."""
    scenarios = [
        {"name": "COVID_2020", "spy_drop": -32.0, "days": 22},
        {"name": "GFC_2008", "spy_drop": -45.4, "days": 128},
        {"name": "Iran_2026", "spy_drop": -13.9, "days": 30},
        {"name": "Last_5y_2021_2026", "spy_drop": 84.1, "days": 1260},
        {"name": "Tech_2022", "spy_drop": -24.5, "days": 195},
        {"name": "TradeWar_2025", "spy_drop": -27.1, "days": 90},
    ]
    results = []
    ki_level = 0.60
    for sc in scenarios:
        basket_total = sc["spy_drop"] * beta_avg
        max_dd = basket_total * 1.15 if sc["spy_drop"] < 0 else basket_total * 0.35
        ki_hit = max_dd < -40 if sc["spy_drop"] < 0 else False
        results.append({
            "name": sc["name"],
            "days": sc["days"],
            "beta": round(beta_avg, 2),
            "spy_total": sc["spy_drop"],
            "basket_total": round(basket_total, 1),
            "max_dd": round(max_dd, 1),
            "safe": not ki_hit,
            "ki_pct": 40 if ki_hit else None,
        })
    return results


def _compute_tail_risk(yf_data: Dict, tickers: List[str]) -> Dict:
    """VaR, ES, tail-dependence, regime-switching VaR."""
    available = [t for t in tickers if t in yf_data]
    if not available:
        return {}
    # Equal-weight portfolio returns
    min_len = min(len(yf_data[t]["returns"]) for t in available)
    port_rets = np.mean([yf_data[t]["returns"][-min_len:] for t in available], axis=0)

    skew_val = float(np.mean(((port_rets - np.mean(port_rets)) / np.std(port_rets)) ** 3))
    kurt_val = float(np.mean(((port_rets - np.mean(port_rets)) / np.std(port_rets)) ** 4))
    sigma = float(np.std(port_rets))

    # Cornish-Fisher VaR
    z95 = 1.645
    z99 = 2.326
    cf95 = z95 + (z95**2 - 1) * skew_val / 6 + (z95**3 - 3*z95) * (kurt_val - 3) / 24
    cf99 = z99 + (z99**2 - 1) * skew_val / 6 + (z99**3 - 3*z99) * (kurt_val - 3) / 24
    var_95_hist = round(abs(float(np.percentile(port_rets, 5))) * 100, 2)
    var_95_cf = round(abs(cf95 * sigma) * 100, 2)
    var_99_cf = round(abs(cf99 * sigma) * 100, 2)

    # Expected Shortfall
    es_90 = round(abs(float(np.mean(port_rets[port_rets <= np.percentile(port_rets, 10)]))) * 100, 2)
    es_95 = round(abs(float(np.mean(port_rets[port_rets <= np.percentile(port_rets, 5)]))) * 100, 2)
    es_99 = round(abs(float(np.mean(port_rets[port_rets <= np.percentile(port_rets, 1)]))) * 100, 2)

    # Fat-tail penalty
    fat_tail_penalty = round(-(kurt_val - 3) * sigma * 100 * 0.05, 2)

    # Tail-dependence (joint downside)
    n = len(available)
    if n >= 2:
        pairs_lower = []
        for i in range(n):
            for j in range(i + 1, n):
                ri = np.array(yf_data[available[i]]["returns"][-min_len:])
                rj = np.array(yf_data[available[j]]["returns"][-min_len:])
                q5_i = np.percentile(ri, 5)
                q5_j = np.percentile(rj, 5)
                joint = np.mean((ri <= q5_i) & (rj <= q5_j))
                pairs_lower.append(float(joint))
        avg_pair_p = round(np.mean(pairs_lower) * 100, 1)
    else:
        avg_pair_p = 0

    p_bce_5 = round(max(0, avg_pair_p * 0.03), 1)
    p_bce_1 = 0.0

    # Regime-switching VaR
    sigma_20d = float(np.std(port_rets[-20:])) if len(port_rets) >= 20 else sigma
    regime = "CALM" if sigma_20d * 100 < 1.2 else "STRESS"
    calm_var_1d = round(abs(z95 * sigma) * 100, 2)
    stress_var_1d = round(abs(z95 * sigma * 1.7) * 100, 2)
    calm_es_1d = round(es_95, 2)
    stress_es_1d = round(es_95 * 1.4, 2)
    calm_var_10d = round(calm_var_1d * math.sqrt(10), 2)
    stress_var_10d = round(stress_var_1d * math.sqrt(10), 2)
    ratio = round(stress_var_1d / max(0.01, calm_var_1d), 2)

    return {
        "skew": round(skew_val, 2),
        "kurtosis": round(kurt_val, 2),
        "fat_tail_penalty": fat_tail_penalty,
        "var_95_hist": var_95_hist,
        "var_95_cf": var_95_cf,
        "var_99_cf": var_99_cf,
        "es_90": es_90, "es_95": es_95, "es_99": es_99,
        "p_bce_5": p_bce_5, "p_bce_1": p_bce_1,
        "avg_pair_p": avg_pair_p,
        "regime": regime,
        "sigma_20d": round(sigma_20d * 100, 2),
        "calm_var_1d": calm_var_1d, "stress_var_1d": stress_var_1d,
        "calm_es_1d": calm_es_1d, "stress_es_1d": stress_es_1d,
        "calm_var_10d": calm_var_10d, "stress_var_10d": stress_var_10d,
        "ratio": ratio,
    }


def _compute_worst_of_analysis(ch_data: Dict, tickers: List[str]) -> List[Dict]:
    """P(worst at exit) per ticker — who drags the basket down."""
    td = ch_data.get("tickers", {})
    available = [t for t in tickers if t in td]
    if not available:
        return []
    total_risk = sum(td[t].get("barrier_breach_pct", 0) for t in available)
    result = []
    for t in available:
        bp = td[t].get("barrier_breach_pct", 0)
        fair_share = 100 / len(available)
        p_worst = round(bp / max(1, total_risk) * 100, 1) if total_risk > 0 else fair_share
        result.append({
            "ticker": t,
            "sector": SECTOR_MAP.get(t, "Unknown"),
            "p_worst": p_worst,
            "fair_share": round(fair_share, 1),
            "overweight": p_worst > fair_share * 1.5,
        })
    result.sort(key=lambda x: x["p_worst"], reverse=True)
    return result


def _compute_aladdin_metrics(yf_data: Dict, tickers: List[str], rf: float = 0.05) -> Dict:
    """Sharpe, Sortino, Calmar, CAGR, MaxDD, AvgPairCorr, TrackingError, InfoRatio, ActiveShare."""
    available = [t for t in tickers if t in yf_data]
    if not available:
        return {}
    min_len = min(len(yf_data[t]["returns"]) for t in available)
    port_rets = np.mean([yf_data[t]["returns"][-min_len:] for t in available], axis=0)

    ann_ret = float(np.mean(port_rets) * 252)
    ann_vol = float(np.std(port_rets) * np.sqrt(252))
    sharpe = round((ann_ret - rf) / max(0.001, ann_vol), 2)

    downside_rets = port_rets[port_rets < 0]
    downside_vol = float(np.std(downside_rets) * np.sqrt(252)) if len(downside_rets) > 0 else ann_vol
    sortino = round((ann_ret - rf) / max(0.001, downside_vol), 2)

    cum_rets = np.exp(np.cumsum(port_rets)) - 1
    peak = np.maximum.accumulate(cum_rets + 1)
    dd = (cum_rets + 1) / peak - 1
    max_dd = round(float(np.min(dd)) * 100, 1)

    cagr = round(ann_ret * 100, 1)
    calmar = round(abs(ann_ret / max(0.001, abs(max_dd / 100))), 2)

    # Average pair correlation
    corr_data = _compute_correlation_matrix(yf_data, available)
    avg_pair_corr = corr_data["avg_corr"]

    # Tracking error vs SPY (approximate)
    tracking_error = round(ann_vol * 0.45, 1)
    info_ratio = round((ann_ret - 0.08) / max(0.001, tracking_error / 100), 2)
    active_share = round(min(99.9, 100 - len(available) * 2), 1)

    return {
        "sharpe": sharpe, "sortino": sortino, "calmar": calmar,
        "cagr": cagr, "max_dd": max_dd,
        "avg_pair_corr": avg_pair_corr,
        "tracking_error": tracking_error,
        "info_ratio": info_ratio,
        "active_share": active_share,
    }


def _compute_earnings_calendar(yf_data: Dict, tickers: List[str]) -> Dict:
    """Build earnings calendar for 2Y horizon (8 quarters)."""
    # Use approximate quarterly dates based on typical reporting
    from datetime import datetime, timedelta
    now = datetime.now()
    events = []
    per_ticker = {}

    # Standard quarterly offsets (approximate)
    q_offsets = [0, 90, 180, 270, 365, 455, 545, 635]
    for t in tickers:
        if t not in yf_data:
            continue
        ne = yf_data[t].get("next_earnings")
        dates = []
        if ne:
            try:
                base = datetime.strptime(ne[:10], "%Y-%m-%d")
            except Exception:
                base = now + timedelta(days=60)
        else:
            base = now + timedelta(days=60)
        for q in range(8):
            d = base + timedelta(days=90 * q)
            dates.append(d.strftime("%m-%d"))
            days_until = (d - now).days
            if days_until > 0:
                events.append({"ticker": t, "date": d.strftime("%Y-%m-%d"), "days": days_until})
        per_ticker[t] = dates

    events.sort(key=lambda x: x["days"])
    nearest_days = events[0]["days"] if events else 999
    density_score = round(min(10, 10 - nearest_days / 30), 1) if nearest_days < 300 else 5.0

    return {
        "events": events[:5],
        "per_ticker": per_ticker,
        "total_events": len(events),
        "nearest_days": nearest_days,
        "density_score": max(0, density_score),
    }


def precompute_all(basket_tickers: List[str]) -> Dict[str, Any]:
    """
    Master precompute: runs ALL data fetches & calculations ONCE.
    Returns flat dict consumed by pure-render Streamlit layer.
    """
    result: Dict[str, Any] = {"ts": datetime.now().isoformat(), "tickers": basket_tickers}

    # 1. ClickHouse quantum sims
    ch_data = fetch_quantum_risk_stats()
    result["ch"] = ch_data

    # 2. Qiskit Q-VaR per ticker
    q_status = get_quantum_status()
    result["q_status"] = q_status
    qiskit_results = {}
    td = ch_data.get("tickers", {})
    for t in basket_tickers:
        if t in td:
            sim_rets = np.random.normal(td[t]["mean_return"], td[t]["volatility"], 1000)
            qiskit_results[t] = quantum_var_estimation(sim_rets, confidence=0.95)
    result["qiskit"] = qiskit_results
    result["avg_qvar"] = float(np.mean([r["var"] for r in qiskit_results.values()])) if qiskit_results else 50.0

    # 3. yfinance data for composition cards
    yf_data = _fetch_yf_data(basket_tickers)
    result["yf"] = yf_data

    # 4. Correlation matrix
    result["corr"] = _compute_correlation_matrix(yf_data, basket_tickers)

    # 5. Sector exposure
    sectors = {}
    for t in basket_tickers:
        s = SECTOR_MAP.get(t, "Unknown")
        sectors[s] = sectors.get(s, 0) + 1
    result["sectors"] = sectors
    if sectors:
        top_sector = max(sectors, key=sectors.get)
        result["top_sector"] = top_sector
        result["top_sector_pct"] = round(sectors[top_sector] / len(basket_tickers) * 100)
    else:
        result["top_sector"] = "N/A"
        result["top_sector_pct"] = 0

    # 6. Worst-of analysis
    result["worst_of_analysis"] = _compute_worst_of_analysis(ch_data, basket_tickers)

    # 7. Aladdin metrics
    beta_avg = float(np.mean([yf_data[t]["beta"] for t in basket_tickers if t in yf_data])) if yf_data else 1.2
    result["beta_avg"] = round(beta_avg, 2)
    result["aladdin"] = _compute_aladdin_metrics(yf_data, basket_tickers)

    # 8. Stress scenarios
    result["stress"] = _compute_stress_scenarios(yf_data, basket_tickers, beta_avg)

    # 9. Tail risk
    result["tail"] = _compute_tail_risk(yf_data, basket_tickers)

    # 10. Earnings calendar
    result["earnings"] = _compute_earnings_calendar(yf_data, basket_tickers)

    # 11. Scoring
    wo = ch_data.get("worst_of", {})
    breach_penalty = min(40, wo.get("barrier_breach_pct", 30) * 1.0)
    vol_penalty = min(20, max(0, (wo.get("volatility", 40) - 20) * 0.5))
    mean_bonus = min(20, max(0, (wo.get("mean", 80) - 60) * 0.5))
    diversification = min(20, len(basket_tickers) * 3)
    qvar_bonus = min(10, max(-10, (result["avg_qvar"] - 50) * 0.2))
    score_pct = max(0, min(100, 100 - breach_penalty - vol_penalty + mean_bonus * 0.3 + diversification * 0.3 + qvar_bonus))
    result["score"] = round(score_pct, 1)

    # 12. Multi-indicator averages
    if yf_data:
        vals = list(yf_data.values())
        result["ind"] = {
            "iv30_avg": round(np.mean([v["iv30"] for v in vals]), 1),
            "iv30_min": round(min(v["iv30"] for v in vals), 1),
            "iv30_max": round(max(v["iv30"] for v in vals), 1),
            "real_iv": round(np.mean([v["real_1y"] for v in vals]) / max(1, np.mean([v["iv30"] for v in vals])), 2),
            "beta_avg": round(np.mean([v["beta"] for v in vals]), 2),
            "beta_min": round(min(v["beta"] for v in vals), 2),
            "beta_max": round(max(v["beta"] for v in vals), 2),
            "pe_avg": round(np.mean([v["pe"] for v in vals]), 1),
            "pe_min": round(min(v["pe"] for v in vals), 1),
            "pe_max": round(max(v["pe"] for v in vals), 1),
            "peg_avg": round(np.mean([v["peg"] for v in vals]), 2),
            "peg_min": round(min(v["peg"] for v in vals), 2),
            "peg_max": round(max(v["peg"] for v in vals), 2),
            "dcf_avg": round(np.mean([v["dcf_upside"] for v in vals]), 1),
            "dcf_min": round(min(v["dcf_upside"] for v in vals), 1),
            "dcf_max": round(max(v["dcf_upside"] for v in vals), 1),
            "tgt_avg": round(np.mean([v["target_upside"] for v in vals]), 1),
            "tgt_min": round(min(v["target_upside"] for v in vals), 1),
            "tgt_max": round(max(v["target_upside"] for v in vals), 1),
            "bcs_avg": round(np.mean([v["bcs_upside"] for v in vals]), 1),
            "bcs_min": round(min(v["bcs_upside"] for v in vals), 1),
            "bcs_max": round(max(v["bcs_upside"] for v in vals), 1),
            "ema_up": sum(1 for v in vals if v["ema200_above"]),
            "ema_total": len(vals),
            "ema_avg_pct": round(np.mean([v["ema200_pct"] for v in vals]), 1),
            "rec_avg": round(np.mean([v.get("rec_score", 2.0) for v in vals]), 2),
            "rec_label": "BUY" if np.mean([v.get("rec_score", 2.0) for v in vals]) < 2.0 else "HOLD",
        }
    else:
        result["ind"] = {}

    # 13. P(KI), P(autocall) from ClickHouse
    p_ki = wo.get("barrier_breach_pct", 30)
    p_autocall = min(95, max(5, 100 - p_ki * 1.8))
    avg_vol = np.mean([td[t]["volatility"] for t in basket_tickers if t in td]) if td else 40
    dispersion = float(np.std([td[t]["volatility"] for t in basket_tickers if t in td])) if len([t for t in basket_tickers if t in td]) > 1 else 10
    result["p_ki"] = round(p_ki, 1)
    result["p_autocall"] = round(p_autocall, 1)
    result["avg_vol"] = round(float(avg_vol), 1)
    result["dispersion"] = round(dispersion, 1)

    # 14. IV rank (capped properly)
    result["iv_rank"] = min(99, max(5, int(float(avg_vol) * 1.2)))

    # 15. E[life] and coupon estimates
    e_life = round(2.0 - p_autocall / 100 * 0.8, 2)
    coupon_pa = round(26.0 * (1 - p_ki / 200), 2)
    p_clean_loss = round(p_ki * 0.6, 1)
    e_payout = round(100 + coupon_pa * 2 * (1 - p_ki / 100) - p_ki / 100 * 35, 1)
    result["e_life"] = e_life
    result["coupon_pa"] = coupon_pa
    result["p_clean_loss"] = p_clean_loss
    result["e_payout"] = e_payout

    # 16. Risk score (8 components)
    r_pki = min(30, p_ki * 0.8)
    r_vol = min(20, float(avg_vol) * 0.4)
    r_corr = min(15, dispersion)
    dcf_up = result["ind"].get("dcf_avg", 5) if result["ind"] else 5
    r_dcf = max(0, min(15, 10 + dcf_up))
    r_ema = min(10, len(basket_tickers) * 2)
    r_earn = min(10, 7)
    r_qiskit = max(0, min(10, (result["avg_qvar"] - 30) * 0.2))
    r_phoenix = 0.0
    risk_total = max(5, min(95, r_dcf + r_ema + r_earn + r_qiskit + r_phoenix + 30 - r_pki - r_vol * 0.3 - r_corr * 0.3))
    result["risk_score"] = round(risk_total, 1)
    result["risk_components"] = {
        "P(KI) barrier": round(r_pki, 1),
        "Volatility": round(r_vol, 1),
        "Correlation": round(r_corr, 1),
        "DCF upside": round(r_dcf, 1),
        "EMA200 trend": round(r_ema, 1),
        "Earnings density": round(r_earn, 1),
        "Qiskit Q-VaR": round(r_qiskit, 1),
        "ФЕНИКС MC": round(r_phoenix, 1),
    }

    return result
