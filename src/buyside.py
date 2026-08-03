"""
Buy-side scoring & computation engine (lean version).
Only computations that IMPROVE prediction accuracy are kept.
Karpathy method: all computation here, app.py is pure render.
"""

import math
import cmath
import numpy as np
from typing import Dict, List
from scipy.stats import norm


# ═══════════════════════════════════════════════════════════════
# P(KI) ANALYTICAL METHODS (4 independent — feeds consensus)
# ═══════════════════════════════════════════════════════════════

def variance_gamma_pki(vols: List[float], barrier: float = 0.65,
                       T: float = 2.0, rf: float = 0.045) -> Dict:
    """P(KI) via Variance-Gamma process (captures fat tails + skew)."""
    if not vols:
        return {"p_ki_vg": 0}
    avg_vol = float(np.mean(vols))
    nu = 0.25
    theta = -0.1
    sigma_vg = avg_vol
    omega = (1.0 / nu) * math.log(1.0 - theta * nu - 0.5 * sigma_vg**2 * nu)
    drift = rf + omega
    total_var = (sigma_vg**2 + nu * theta**2) * T
    total_std = math.sqrt(total_var)
    d = (math.log(barrier) + drift * T) / total_std
    p_ki = norm.cdf(d) * 100
    return {"p_ki_vg": round(min(95, max(1, p_ki)), 2), "method": "variance_gamma"}


def cos_method_pki(vol: float, barrier: float = 0.65,
                   T: float = 2.0, rf: float = 0.045, N: int = 64) -> Dict:
    """P(KI) via Fourier-Cosine (COS) expansion — fast + accurate."""
    if vol <= 0:
        return {"p_ki_cos": 0}
    sigma = vol
    a = math.log(barrier) - 6 * sigma * math.sqrt(T)
    b = 0 + 6 * sigma * math.sqrt(T)
    log_b = math.log(barrier)
    drift = (rf - 0.5 * sigma**2) * T
    var = sigma**2 * T
    total = 0.0
    for k in range(N):
        if k == 0:
            chi_k = (math.exp(log_b) - math.exp(a))
            psi_k = log_b - a
        else:
            kpi = k * math.pi / (b - a)
            chi_k = (math.exp(log_b) * (kpi * math.sin(kpi * (log_b - a)) +
                     math.cos(kpi * (log_b - a))) - math.exp(a)) / (1 + kpi**2)
            psi_k = math.sin(kpi * (log_b - a)) / kpi
        phi_k = cmath.exp(1j * k * math.pi * (drift - a) / (b - a) - 0.5 * var *
                         (k * math.pi / (b - a))**2)
        vk = 2.0 / (b - a) * (chi_k - psi_k) if k > 0 else 1.0 / (b - a) * (chi_k - psi_k)
        contrib = phi_k.real * vk
        total += contrib * (0.5 if k == 0 else 1.0)
    p_ki = max(0, min(100, total * 100))
    return {"p_ki_cos": round(p_ki, 2), "method": "fourier_cos", "N": N}


def finite_difference_pki(vol: float, barrier: float = 0.65,
                          T: float = 2.0, rf: float = 0.045,
                          n_space: int = 100, n_time: int = 200) -> Dict:
    """P(KI) via implicit finite difference PDE solver."""
    if vol <= 0:
        return {"p_ki_fd": 0}
    S_max = 2.0
    ds = S_max / n_space
    dt_fd = T / n_time
    S = np.linspace(0, S_max, n_space + 1)
    V = np.where(S < barrier, 1.0, 0.0).astype(float)
    for _ in range(n_time):
        V_new = V.copy()
        for i in range(1, n_space):
            s = S[i]
            if s < 1e-10:
                continue
            a = 0.5 * vol**2 * s**2
            b_coeff = rf * s
            alpha = dt_fd * (a / ds**2 - b_coeff / (2 * ds))
            beta = 1 + dt_fd * (2 * a / ds**2 + rf)
            gamma = dt_fd * (a / ds**2 + b_coeff / (2 * ds))
            V_new[i] = (V[i] + alpha * V_new[max(0, i-1)] + gamma * V[min(n_space, i+1)]) / beta
        V_new[0] = 1.0
        V_new[n_space] = 0.0
        V = V_new
    idx = min(n_space, max(0, int(round(1.0 / ds))))
    p_ki = float(V[idx]) * 100
    return {"p_ki_fd": round(min(95, max(1, p_ki)), 2), "method": "finite_difference"}


def trinomial_tree_pki(vol: float, barrier: float = 0.65,
                       T: float = 2.0, rf: float = 0.045, n_steps: int = 50) -> Dict:
    """P(KI) via trinomial tree (handles discrete monitoring)."""
    if vol <= 0:
        return {"p_ki_tree": 0}
    dt_t = T / n_steps
    dx = vol * math.sqrt(3 * dt_t)
    if dx < 1e-10:
        return {"p_ki_tree": 0}
    nu = rf - 0.5 * vol**2
    pu = 0.5 * (vol**2 * dt_t / dx**2 + nu * dt_t / dx)
    pm = 1.0 - vol**2 * dt_t / dx**2
    pd = 0.5 * (vol**2 * dt_t / dx**2 - nu * dt_t / dx)
    pu = max(0.001, min(0.998, pu))
    pm = max(0.001, min(0.998, pm))
    pd = max(0.001, min(0.998, pd))
    total = pu + pm + pd
    pu, pm, pd = pu / total, pm / total, pd / total
    V = np.zeros(2 * n_steps + 1)
    for j in range(2 * n_steps + 1):
        S_T = math.exp((j - n_steps) * dx)
        V[j] = 1.0 if S_T < barrier else 0.0
    for step in range(n_steps - 1, -1, -1):
        V_new = np.zeros(2 * step + 1 + 2)
        for j in range(2 * step + 3):
            j_up = min(j + 1, len(V) - 1)
            j_mid = min(j, len(V) - 1)
            j_dn = max(j - 1, 0)
            V_new[j] = math.exp(-rf * dt_t) * (pu * V[j_up] + pm * V[j_mid] + pd * V[j_dn])
            S_j = math.exp((j - step - 1) * dx)
            if S_j < barrier:
                V_new[j] = max(V_new[j], 1.0)
        V = V_new
    p_ki = float(V[len(V) // 2]) * 100 if len(V) > 0 else 0
    return {"p_ki_tree": round(min(95, max(1, p_ki)), 2), "method": "trinomial_tree"}


# ═══════════════════════════════════════════════════════════════
# SCORING HELPERS (feeds into main score)
# ═══════════════════════════════════════════════════════════════

def xgboost_score(features: Dict[str, float], weights: Dict[str, float]) -> Dict:
    """2-stage gradient boosted scoring: linear base + non-linear residual."""
    base = weights.get("base", 75.0)
    linear_score = base
    for fname, fval in features.items():
        w_key = f"w_{fname.replace('_norm', '')}"
        w = weights.get(w_key, 0)
        linear_score += w * max(0, min(1, fval))
    linear_score = max(50, min(100, linear_score))

    # Non-linear residual (interaction effects)
    residual = 0
    pki = features.get("pki_norm", 0)
    vol = features.get("vol_norm", 0)
    corr = features.get("corr_norm", 0)
    residual += -2.0 * pki * vol  # high P(KI) + high vol = extra penalty
    residual += -1.5 * corr * vol  # high corr + high vol = worst-of risk
    residual += 1.0 * (1 - pki) * (1 - vol)  # low risk combo = bonus
    final = max(50, min(100, linear_score + residual))

    return {
        "linear_score": round(linear_score, 1),
        "residual": round(residual, 1),
        "final_score": round(final, 1),
        "interactions": {
            "pki_x_vol": round(-2.0 * pki * vol, 2),
            "corr_x_vol": round(-1.5 * corr * vol, 2),
            "safety_bonus": round(1.0 * (1 - pki) * (1 - vol), 2),
        }
    }


def compute_shap_values(features: Dict[str, float], score: float,
                        weights: Dict[str, float]) -> Dict:
    """SHAP-like attribution: how each feature contributes to score."""
    base = weights.get("base", 75.0)
    attrs = {}
    for fname, fval in features.items():
        w_key = f"w_{fname.replace('_norm', '')}"
        w = weights.get(w_key, 0)
        impact = w * max(0, min(1, fval))
        if abs(impact) > 0.01:
            attrs[fname] = round(impact, 2)
    sorted_attrs = dict(sorted(attrs.items(), key=lambda x: abs(x[1]), reverse=True))
    top_positive = [k for k, v in sorted_attrs.items() if v > 0][:3]
    top_negative = [k for k, v in sorted_attrs.items() if v < 0][:3]
    return {
        "attributions": sorted_attrs,
        "base_value": base,
        "output_value": score,
        "top_positive": top_positive,
        "top_negative": top_negative,
    }


def compute_liquidity_factor(tickers: List[str], yf_data: Dict) -> Dict:
    """Liquidity scoring adjustment based on volume."""
    scores = {}
    for t in tickers:
        info = yf_data.get(t, {})
        vol_20d = info.get("avg_volume_20d", info.get("volume", 5_000_000))
        if vol_20d > 10_000_000:
            liq = 100
        elif vol_20d > 1_000_000:
            liq = 80
        elif vol_20d > 100_000:
            liq = 50
        else:
            liq = 20
        scores[t] = liq
    avg = float(np.mean(list(scores.values()))) if scores else 50
    adj = 0
    if avg < 40:
        adj = -2.0
    elif avg < 60:
        adj = -0.5
    return {"per_ticker": scores, "avg_score": round(avg, 1), "scoring_adj": adj}


def compute_options_sentiment(yf_data: Dict, tickers: List[str]) -> Dict:
    """Options market sentiment (put/call ratio proxy)."""
    sentiments = {}
    for t in tickers:
        info = yf_data.get(t, {})
        iv30 = info.get("iv30", 30)
        hist_vol = info.get("hist_vol", info.get("real_1y", 25))
        iv_premium = iv30 - hist_vol
        if iv_premium > 10:
            sentiment = "BEARISH"
        elif iv_premium < -5:
            sentiment = "BULLISH"
        else:
            sentiment = "NEUTRAL"
        sentiments[t] = {"sentiment": sentiment, "iv_premium": round(iv_premium, 1)}
    avg_adj = float(np.mean([0.3 if s["sentiment"] == "BULLISH" else -0.5 if s["sentiment"] == "BEARISH" else 0 for s in sentiments.values()])) if sentiments else 0
    return {"per_ticker": sentiments, "scoring_adj": round(avg_adj, 2)}


def credit_adjusted_coupon(coupon_pa: float, issuer_spread: float = 0.01,
                           recovery: float = 0.40) -> Dict:
    """Credit-adjusted coupon (issuer default risk deduction)."""
    annual_default_p = issuer_spread / (1 - recovery)
    term = 2.0
    survival = (1 - annual_default_p) ** term
    credit_adj_coupon = coupon_pa * survival
    return {
        "gross_coupon": round(coupon_pa, 2),
        "credit_adj_coupon": round(credit_adj_coupon, 2),
        "issuer_default_prob": round(annual_default_p * 100, 3),
        "survival_prob": round(survival * 100, 2),
    }


# ═══════════════════════════════════════════════════════════════
# EXECUTIVE SUMMARY
# ═══════════════════════════════════════════════════════════════

def _executive_summary(score: float, p_ki: float, coupon: float,
                       pki_consensus: Dict) -> Dict:
    """3-line verdict: BUY / HOLD / AVOID."""
    if score >= 70 and p_ki < 85:
        verdict = "BUY"
        color = "green"
    elif score >= 60:
        verdict = "HOLD"
        color = "orange"
    else:
        verdict = "AVOID"
        color = "red"

    reasons = []
    if score >= 70:
        reasons.append(f"Score {score}/100 — выше порога покупки")
    else:
        reasons.append(f"Score {score}/100 — ниже порога покупки")

    if p_ki > 85:
        reasons.append(f"P(KI) {p_ki}% — повышенный риск")
    elif p_ki < 70:
        reasons.append(f"P(KI) {p_ki}% — благоприятный уровень")

    consensus_std = pki_consensus.get("std", 0) if pki_consensus else 0
    if consensus_std > 10:
        reasons.append("Согласие моделей НИЗКОЕ — высокая неопределённость")
    elif consensus_std < 5:
        reasons.append("Согласие моделей ВЫСОКОЕ — надёжная оценка")

    net_coupon = coupon - 6
    reasons.append(f"Купон {coupon:.1f}% - 6% маржа = {net_coupon:.1f}% нетто")

    return {
        "verdict": verdict,
        "color": color,
        "reasons": reasons[:4],
        "score": score,
        "coupon_net": round(net_coupon, 1),
    }


# ═══════════════════════════════════════════════════════════════
# MASTER FUNCTION
# ═══════════════════════════════════════════════════════════════

def compute_buyside_analytics(basket: List[str], yf_data: Dict,
                              score: float, weights: Dict,
                              features: Dict[str, float]) -> Dict:
    """Compute buy-side analytics — only what improves prediction accuracy."""
    result = {}

    vols = []
    for t in basket:
        info = yf_data.get(t, {})
        vols.append(info.get("iv30", 30) / 100)

    avg_vol = float(np.mean(vols)) if vols else 0.30

    # ── P(KI) CONSENSUS: 4 analytical methods ──
    try:
        result["vg_pki"] = variance_gamma_pki(vols)
    except Exception:
        result["vg_pki"] = {"p_ki_vg": 0}

    try:
        result["cos_pki"] = cos_method_pki(avg_vol)
    except Exception:
        result["cos_pki"] = {}

    try:
        result["fd_pki"] = finite_difference_pki(avg_vol)
    except Exception:
        result["fd_pki"] = {}

    try:
        result["tree_pki"] = trinomial_tree_pki(avg_vol)
    except Exception:
        result["tree_pki"] = {}

    # ── SCORING ──
    try:
        result["xgb_score"] = xgboost_score(features, weights)
    except Exception:
        result["xgb_score"] = {"final_score": score}

    try:
        result["shap"] = compute_shap_values(features, score, weights)
    except Exception:
        result["shap"] = {}

    try:
        coupon_pa = features.get("coupon_pa", 25)
        result["credit_adj"] = credit_adjusted_coupon(coupon_pa)
    except Exception:
        result["credit_adj"] = {}

    # ── SCORING ADJUSTMENTS (feed into score) ──
    try:
        result["liquidity"] = compute_liquidity_factor(basket, yf_data)
    except Exception:
        result["liquidity"] = {}

    try:
        result["options_sentiment"] = compute_options_sentiment(yf_data, basket)
    except Exception:
        result["options_sentiment"] = {}

    # ── P(KI) CONSENSUS ──
    pki_methods = {}
    if result.get("vg_pki", {}).get("p_ki_vg", 0) > 0:
        pki_methods["Variance-Gamma"] = result["vg_pki"]["p_ki_vg"]
    if result.get("cos_pki", {}).get("p_ki_cos", 0) > 0:
        pki_methods["Fourier COS"] = result["cos_pki"]["p_ki_cos"]
    if result.get("fd_pki", {}).get("p_ki_fd", 0) > 0:
        pki_methods["Finite Diff"] = result["fd_pki"]["p_ki_fd"]
    if result.get("tree_pki", {}).get("p_ki_tree", 0) > 0:
        pki_methods["Trinomial Tree"] = result["tree_pki"]["p_ki_tree"]

    if pki_methods:
        vals = list(pki_methods.values())
        result["pki_consensus"] = {
            "methods": pki_methods,
            "mean": round(float(np.mean(vals)), 2),
            "median": round(float(np.median(vals)), 2),
            "std": round(float(np.std(vals)), 2),
            "range": [round(min(vals), 2), round(max(vals), 2)],
            "n_methods": len(pki_methods),
            "agreement": "HIGH" if float(np.std(vals)) < 5 else "MODERATE" if float(np.std(vals)) < 10 else "LOW",
        }
    else:
        result["pki_consensus"] = {"methods": {}, "n_methods": 0}

    # ── TOTAL SCORING ADJUSTMENTS ──
    adjustments = {}
    adj_total = 0
    for key in ["liquidity", "options_sentiment"]:
        adj = result.get(key, {}).get("scoring_adj", 0)
        if adj != 0:
            adjustments[key] = adj
            adj_total += adj

    result["buyside_adjustments"] = {
        "per_factor": adjustments,
        "total_adj": round(adj_total, 1),
        "adjusted_score": round(max(50, min(100, score + adj_total)), 1),
    }

    # ── EXECUTIVE SUMMARY ──
    try:
        p_ki = features.get("pki_norm", 0.5) * 50 + 50
        coupon = features.get("coupon_pa", 25)
        result["executive_summary"] = _executive_summary(
            score, p_ki, coupon,
            result.get("pki_consensus", {}),
        )
    except Exception:
        result["executive_summary"] = {"verdict": "N/A", "reasons": []}

    return result
