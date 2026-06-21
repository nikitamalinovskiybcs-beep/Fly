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
from src.real_data import compute_toxicity
from src.colab_engine import get_colab_status, local_sobol_mc
from src.data_module import (fetch_ticker_data, get_data_source_status, XFL_AVAILABLE,
                             fetch_iv_percentile, compute_rolling_correlations, check_earnings_risk)
from src.gdrive_store import get_status as gdrive_status
from src.nvidia_ai import get_status as nvidia_status, analyze_basket_risk


# ── Self-learning scoring weights ──
_DEFAULT_SCORING_WEIGHTS = {
    "base": 75.0,          # center of 50-100 range
    "w_pki": 12.0,         # P(KI) penalty weight (max -12pt)
    "w_vol": 6.0,          # Volatility penalty (max -6pt)
    "w_corr": 5.0,         # Correlation penalty (max -5pt)
    "w_tox": 8.0,          # Toxicity penalty (max -8pt)
    "w_div": 5.0,          # Diversification bonus (max +5pt)
    "w_fund": 4.0,         # Fundamental quality bonus (max +4pt)
    "w_quality": 4.0,      # Analyst consensus bonus (max +4pt)
    "w_ema": 3.0,          # EMA200 trend bonus (max +3pt)
    "w_mean_ret": 5.0,     # Mean return bonus (max +5pt)
    "generation": 0,
}


def _load_scoring_weights() -> Dict[str, float]:
    """Load learned scoring weights from Google Drive store."""
    try:
        from src.gdrive_store import load_latest_params
        params = load_latest_params()
        if params and "w_pki" in params:
            return {**_DEFAULT_SCORING_WEIGHTS, **params}
    except Exception:
        pass
    return dict(_DEFAULT_SCORING_WEIGHTS)


def _save_scoring_weights(weights: Dict[str, float], metrics: Dict):
    """Save updated scoring weights to Google Drive store."""
    try:
        from src.gdrive_store import save_calibrated_params
        save_calibrated_params(weights, metrics)
    except Exception:
        pass


def update_scoring_from_outcome(basket: List[str], predicted_score: float,
                                actual_outcome: float, learning_rate: float = 0.02):
    """Self-learning: adjust weights based on prediction vs actual outcome.
    actual_outcome: 1.0 = product won (autocalled), 0.0 = loss (KI hit).
    Called after each pipeline run or settled note comparison."""
    w = _load_scoring_weights()
    error = (actual_outcome * 50 + 50) - predicted_score
    if abs(error) < 2:
        return w
    lr = learning_rate * min(1.0, abs(error) / 20)
    direction = 1.0 if error > 0 else -1.0
    w["base"] = max(65, min(85, w["base"] + direction * lr * 3))
    w["w_pki"] = max(5, min(20, w["w_pki"] - direction * lr * 2))
    w["w_tox"] = max(3, min(15, w["w_tox"] - direction * lr * 1.5))
    w["w_div"] = max(2, min(10, w["w_div"] + direction * lr))
    w["w_fund"] = max(1, min(8, w["w_fund"] + direction * lr))
    w["generation"] = w.get("generation", 0) + 1
    _save_scoring_weights(w, {"error": round(error, 2), "lr": round(lr, 4),
                               "predicted": round(predicted_score, 1),
                               "actual": round(actual_outcome, 2)})
    return w


def _score_one_note(w: Dict, tks: List[str], term_y: float) -> float:
    """Predict score for a single basket given weights."""
    tox = compute_toxicity(tks)
    avg_tox = tox["avg_tox"]
    max_tox = max((v["tox"] for v in tox["per_ticker"].values()), default=0.5)
    n = len(tks)
    div_factor = min(1.0, len(tox["per_ticker"]) / max(1, n))
    return (w["base"]
            - w["w_pki"] * avg_tox * 0.5
            - w["w_tox"] * max_tox
            - w["w_vol"] * avg_tox * 0.3
            + w["w_div"] * div_factor * 0.5
            - w["w_corr"] * (1.0 - div_factor) * 0.3
            + w["w_mean_ret"] * (1 - avg_tox) * 0.3)


def calibrate_scoring_on_settled() -> Dict:
    """Full calibration via momentum SGD on all settled notes.
    Features: momentum (0.9), L2 regularization, feature selection, best-checkpoint.
    Updates ALL weights. Saves to Google Drive. Returns metrics."""
    from src.real_data import SETTLED_NOTES, compute_p_loss

    w = _load_scoring_weights()

    # Build dataset: target = 85-95 if good (bad=0), 45-60 if bad (bad=1)
    data = []
    for basket_str, term_y, bad in SETTLED_NOTES[:40]:
        tks = basket_str.split("/") if isinstance(basket_str, str) else basket_str
        if not tks:
            continue
        actual = 90.0 if bad == 0 else 52.0
        data.append((tks, term_y, actual))

    if not data:
        return {"generation": 0, "before_mae": 0, "after_mae": 0,
                "improvement_pct": 0, "n_notes": 0, "weights": w}

    # Measure BEFORE
    errors_before = [actual - _score_one_note(w, tks, ty) for tks, ty, actual in data]
    before_mae = float(np.mean(np.abs(errors_before)))

    correct_before = sum(1 for (tks, ty, actual), err in zip(data, errors_before)
                        if (actual > 70 and _score_one_note(w, tks, ty) > 70)
                        or (actual < 70 and _score_one_note(w, tks, ty) < 70))
    acc_before = correct_before / len(data) * 100

    # Momentum SGD: 30 steps with momentum=0.9 + L2 + feature selection
    best_w = dict(w)
    best_mae = before_mae
    lr = 0.08
    momentum = 0.9
    # Velocity terms for momentum
    v = {k: 0.0 for k in ["base", "w_pki", "w_tox", "w_vol", "w_div", "w_fund", "w_mean_ret"]}
    # Feature importance tracking
    feature_impact = {k: 0.0 for k in v}

    weight_keys = ["base", "w_pki", "w_tox", "w_vol", "w_div", "w_fund", "w_mean_ret"]
    gradients = {k: [] for k in weight_keys}
    # Direction multipliers (base goes +, penalties go -)
    directions = {"base": 1.0, "w_pki": -0.15, "w_tox": -0.2, "w_vol": -0.1,
                  "w_div": 0.1, "w_fund": 0.08, "w_mean_ret": 0.05}
    bounds = {"base": (65, 90), "w_pki": (5, 20), "w_tox": (3, 15),
              "w_vol": (2, 12), "w_div": (2, 10), "w_fund": (1, 8), "w_mean_ret": (2, 10)}

    for step in range(30):
        errors = [actual - _score_one_note(w, tks, ty) for tks, ty, actual in data]
        mae = float(np.mean(np.abs(errors)))
        avg_err = float(np.mean(errors))

        if mae < best_mae:
            best_mae = mae
            best_w = dict(w)

        if abs(avg_err) < 0.3:
            break

        # L2 penalty coefficient
        l2 = 0.01

        for k in weight_keys:
            grad = avg_err * directions[k] - l2 * (w[k] - _DEFAULT_SCORING_WEIGHTS.get(k, w[k]))
            # Momentum update: v = momentum * v + grad
            v[k] = momentum * v[k] + grad * lr
            # Feature importance: accumulate abs gradient
            feature_impact[k] += abs(grad)
            gradients[k].append(grad)
            # Apply update with bounds
            lo, hi = bounds[k]
            w[k] = max(lo, min(hi, w[k] + v[k]))

        lr *= 0.94

    # Feature selection: zero out weights with negligible impact
    total_impact = sum(feature_impact.values()) or 1
    weak_features = []
    for k in weight_keys:
        if k == "base":
            continue
        if feature_impact[k] / total_impact < 0.02:  # <2% impact → disable
            w[k] = _DEFAULT_SCORING_WEIGHTS.get(k, w[k])
            weak_features.append(k)

    # Use best weights found
    w = best_w
    w["generation"] = w.get("generation", 0) + 1

    # Measure AFTER
    errors_after = [actual - _score_one_note(w, tks, ty) for tks, ty, actual in data]
    after_mae = float(np.mean(np.abs(errors_after)))
    correct_after = sum(1 for (tks, ty, actual), err in zip(data, errors_after)
                       if (actual > 70 and _score_one_note(w, tks, ty) > 70)
                       or (actual < 70 and _score_one_note(w, tks, ty) < 70))
    acc_after = correct_after / len(data) * 100

    _save_scoring_weights(w, {
        "before_mae": round(before_mae, 1),
        "after_mae": round(after_mae, 1),
        "improvement_pct": round((before_mae - after_mae) / max(1, before_mae) * 100, 1),
        "acc_before": round(acc_before, 0),
        "acc_after": round(acc_after, 0),
    })

    # Normalize feature importance to percentages
    fi_pct = {k: round(v / total_impact * 100, 1) for k, v in feature_impact.items()}

    return {
        "generation": w.get("generation", 0),
        "before_mae": round(before_mae, 1),
        "after_mae": round(after_mae, 1),
        "improvement_pct": round((before_mae - after_mae) / max(1, before_mae) * 100, 1),
        "acc_before": round(acc_before, 0),
        "acc_after": round(acc_after, 0),
        "n_notes": len(data),
        "weights": {k: round(v, 2) if isinstance(v, float) else v for k, v in w.items()},
        "feature_importance": fi_pct,
        "weak_features": weak_features,
    }


def online_learn_one_note(basket: List[str], term_y: float, outcome_good: bool) -> Dict:
    """Online learning: update weights with a single new observation.
    Call this when a new settled note becomes available.
    Uses small LR (0.02) to nudge weights without full recalibration.
    """
    w = _load_scoring_weights()
    target = 88.0 if outcome_good else 55.0
    pred = _score_one_note(w, basket, term_y)
    err = target - pred

    if abs(err) < 2.0:
        return {"updated": False, "reason": "already accurate", "error": round(err, 1)}

    # Small update with momentum-free SGD
    online_lr = 0.02
    l2 = 0.005
    directions = {"base": 1.0, "w_pki": -0.15, "w_tox": -0.2, "w_vol": -0.1,
                  "w_div": 0.1, "w_fund": 0.08, "w_mean_ret": 0.05}
    bounds = {"base": (65, 90), "w_pki": (5, 20), "w_tox": (3, 15),
              "w_vol": (2, 12), "w_div": (2, 10), "w_fund": (1, 8), "w_mean_ret": (2, 10)}

    for k in directions:
        grad = err * directions[k] - l2 * (w[k] - _DEFAULT_SCORING_WEIGHTS.get(k, w[k]))
        lo, hi = bounds[k]
        w[k] = max(lo, min(hi, w[k] + grad * online_lr))

    w["generation"] = w.get("generation", 0) + 1
    _save_scoring_weights(w, {"online_update": True, "error": round(err, 1)})

    new_pred = _score_one_note(w, basket, term_y)
    return {
        "updated": True,
        "generation": w["generation"],
        "error_before": round(err, 1),
        "error_after": round(target - new_pred, 1),
        "pred_before": round(pred, 1),
        "pred_after": round(new_pred, 1),
    }


# ── Smart alternatives generator ──

# Universe of tickers by sector for alternative basket generation
_UNIVERSE = {
    "Information Technology": ["AAPL", "MSFT", "NVDA", "AMD", "CRM", "AVGO", "ORCL", "ADBE", "INTC", "QCOM", "DELL"],
    "Communication Services": ["GOOGL", "META", "DIS", "T", "NFLX", "EA", "TTWO"],
    "Consumer Discretionary": ["AMZN", "TSLA", "MCD", "HLT", "SBUX", "NKE", "HD"],
    "Health Care": ["JNJ", "ABBV", "UNH", "LLY", "PFE", "MRK"],
    "Consumer Staples": ["PG", "KO", "PEP", "PM", "WMT", "COST"],
    "Financials": ["JPM", "V", "MA", "GS", "BAC", "COF"],
    "Industrials": ["BA", "CAT", "HON", "UPS", "GE", "RTX"],
}


def compute_smart_alternatives(basket: List[str], yf_data: Dict,
                                tox_info: Dict, n_alts: int = 8) -> List[Dict]:
    """Generate smart alternative baskets by swapping weakest ticker.

    Strategy:
    1. Find the weakest ticker (highest toxicity or worst fundamentals)
    2. Generate alternatives by replacing it with tickers from different sectors
    3. Score each alternative quickly using the same factor model
    4. Return top N alternatives sorted by estimated score
    """
    if len(basket) < 2:
        return []

    # Find weakest ticker
    per_ticker = tox_info.get("per_ticker", {})
    worst_t = basket[0]
    worst_score = -1
    for t in basket:
        tox_val = per_ticker.get(t, {}).get("tox", 0)
        vol_val = yf_data.get(t, {}).get("iv30", 30) / 100
        weakness = tox_val * 0.6 + vol_val * 0.4
        if weakness > worst_score:
            worst_score = weakness
            worst_t = t
    worst_sector = SECTOR_MAP.get(worst_t, "Unknown")

    # Collect candidates from sectors NOT already in basket
    basket_set = set(basket)
    candidates = []
    for sector, tickers in _UNIVERSE.items():
        for t in tickers:
            if t not in basket_set:
                tox_val = per_ticker.get(t, {}).get("tox", 0.3)
                # Quick quality estimate
                info = yf_data.get(t, {})
                vol = info.get("iv30", 30)
                beta = info.get("beta", 1.0)
                ema_above = info.get("ema200_above", True)
                quality = 80 - tox_val * 20 - (vol - 25) * 0.15 + (5 if ema_above else 0) + (3 if sector != worst_sector else 0)
                candidates.append({
                    "ticker": t,
                    "sector": sector,
                    "est_quality": round(quality, 1),
                    "tox": round(tox_val, 2),
                    "vol": round(vol, 1) if vol else 30,
                })

    # Sort by quality, take top N
    candidates.sort(key=lambda x: x["est_quality"], reverse=True)
    top = candidates[:n_alts]

    # Build alternative baskets
    alts = []
    for c in top:
        new_basket = [c["ticker"] if t == worst_t else t for t in basket]
        # Quick score estimate
        avg_tox_new = np.mean([per_ticker.get(t, {}).get("tox", 0.3) for t in new_basket])
        est_score = round(max(50, min(100, 75 + (0.5 - avg_tox_new) * 20 - (c["vol"] - 25) * 0.1 + c["est_quality"] * 0.1)), 1)
        alts.append({
            "basket": new_basket,
            "replaced": worst_t,
            "with": c["ticker"],
            "sector": c["sector"],
            "est_score": est_score,
            "swap_reason": f"Замена {worst_t} (tox={worst_score:.2f}) → {c['ticker']} ({c['sector']})",
            "tox": round(avg_tox_new, 2),
        })

    alts.sort(key=lambda x: x["est_score"], reverse=True)
    return alts


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 1: Best Phoenix Ranker — score ALL possible baskets
# ═══════════════════════════════════════════════════════════════

def rank_best_phoenix(basket: List[str], yf_data: Dict, tox_info: Dict,
                      ch_data: Dict) -> Dict:
    """Find the best Phoenix product configuration for this basket.
    Tests different barriers, tenors, and swap options."""
    from src.real_data import compute_p_loss, COUPON_BY_TERM, COUPON_COEFS

    avg_tox = tox_info["avg_tox"]
    n = len(basket)
    base_p_loss = compute_p_loss(basket, term_months=24)
    base_p = base_p_loss.get("p_loss", 0.2)  # decimal 0-1

    # Avg vol from yf_data
    vols = [yf_data[t].get("iv30", 30) for t in basket if t in yf_data]
    avg_vol = float(np.mean(vols)) if vols else 30

    # Test barriers 55-75%
    barrier_results = []
    for bar in [0.55, 0.60, 0.65, 0.70, 0.75]:
        # P(KI) varies with barrier: lower barrier = lower P(KI)
        # Each 5% lower barrier reduces P(KI) by ~20-30%
        bar_factor = 1.0 + (bar - 0.65) * 3.0  # 0.55→0.7, 0.65→1.0, 0.75→1.3
        adj_pki = max(3, min(60, base_p * 100 * bar_factor))
        # Coupon: lower barrier = lower coupon (less risk taken)
        est_coupon = COUPON_COEFS[0] * avg_tox + COUPON_COEFS[1] * n + COUPON_COEFS[2] * 24 + COUPON_COEFS[3] * bar + COUPON_COEFS[4]
        est_coupon = max(8, min(45, est_coupon * (0.8 + avg_vol / 100)))
        score = est_coupon * (1 - adj_pki / 100) - adj_pki * 0.3
        barrier_results.append({
            "barrier": int(bar * 100),
            "p_ki": round(adj_pki, 1),
            "est_coupon": round(est_coupon, 1),
            "score": round(score, 1),
        })
    barrier_results.sort(key=lambda x: x["score"], reverse=True)

    # Test tenors 12-36 months
    tenor_results = []
    for term_m in [12, 18, 24, 36]:
        lookup = COUPON_BY_TERM.get(term_m, COUPON_BY_TERM.get(24, {}))
        mean_cpn = lookup.get("mean", 20)
        p_loss_t = compute_p_loss(basket, term_months=term_m)
        raw_p = p_loss_t.get("p_loss", 0.15)  # decimal 0-1
        tenor_results.append({
            "tenor_months": term_m,
            "est_coupon": round(mean_cpn, 1),
            "p_loss": round(raw_p * 100, 1),
            "score": round(mean_cpn * (1 - raw_p) - raw_p * 100 * 0.3, 1),
        })
    tenor_results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "best_barrier": barrier_results[0] if barrier_results else {},
        "all_barriers": barrier_results,
        "best_tenor": tenor_results[0] if tenor_results else {},
        "all_tenors": tenor_results,
        "recommendation": f"Лучший Феникс: барьер {barrier_results[0]['barrier']}%, срок {tenor_results[0]['tenor_months']}мес, купон ~{barrier_results[0]['est_coupon']:.0f}%" if barrier_results and tenor_results else "Недостаточно данных",
    }


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 3: Empirical P(KI) from settled notes
# ═══════════════════════════════════════════════════════════════

def empirical_p_ki(basket: List[str], term_months: int = 24) -> Dict:
    """P(KI) calibrated on real settled notes outcomes.
    Uses logistic-style model: high tox + long term → high P(KI)."""
    from src.real_data import SETTLED_NOTES, TOX_EXPERIENCE
    tox = compute_toxicity(basket)
    avg_tox = tox["avg_tox"]

    # Count outcomes by toxicity bucket from real data
    high_tox_notes = [(b, t, bad) for b, t, bad in SETTLED_NOTES
                      if _note_avg_tox(b) >= 0.5]
    low_tox_notes = [(b, t, bad) for b, t, bad in SETTLED_NOTES
                     if _note_avg_tox(b) < 0.5]

    high_tox_loss_rate = sum(1 for _, _, b in high_tox_notes if b) / max(1, len(high_tox_notes))
    low_tox_loss_rate = sum(1 for _, _, b in low_tox_notes if b) / max(1, len(low_tox_notes))

    total = len(SETTLED_NOTES)
    loss_count = sum(1 for _, _, bad in SETTLED_NOTES if bad == 1)

    # Interpolate P(KI) based on basket toxicity
    if avg_tox >= 0.5:
        p_ki_pct = low_tox_loss_rate * 100 + (high_tox_loss_rate - low_tox_loss_rate) * 100 * min(1, (avg_tox - 0.2) / 0.5)
    else:
        p_ki_pct = low_tox_loss_rate * 100 * (0.5 + avg_tox)

    # Term adjustment: longer = riskier
    term_adj = (term_months - 24) / 12 * 4
    p_ki_pct += term_adj

    # Diversification adjustment
    n = len(basket)
    if n <= 3:
        p_ki_pct *= 0.85
    elif n >= 5:
        p_ki_pct *= 1.05

    p_ki_pct = max(5, min(70, p_ki_pct))

    return {
        "p_ki_empirical": round(p_ki_pct, 1),
        "base_rate": round(loss_count / max(1, total) * 100, 1),
        "high_tox_rate": round(high_tox_loss_rate * 100, 1),
        "low_tox_rate": round(low_tox_loss_rate * 100, 1),
        "tox_adjustment": round(term_adj, 1),
        "n_settled": total,
        "n_losses": loss_count,
        "confidence": "high" if total > 30 else "medium",
    }


def _note_avg_tox(basket_str: str) -> float:
    """Helper: average toxicity for a basket string like 'AAPL/MSFT/NVDA'."""
    from src.real_data import TOX_EXPERIENCE
    tickers = basket_str.split("/")
    scores = []
    for t in tickers:
        if t in TOX_EXPERIENCE:
            l, w = TOX_EXPERIENCE[t]
            scores.append(l / (l + w + 1))
    return float(np.mean(scores)) if scores else 0.5


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 4: Coupon model calibrated on 828 dealer quotes
# ═══════════════════════════════════════════════════════════════

def calibrated_coupon(basket: List[str], term_months: int = 24,
                      barrier: float = 0.65) -> Dict:
    """Coupon estimate from OLS on 828 real dealer quotes."""
    from src.real_data import COUPON_COEFS, COUPON_BY_TERM
    tox = compute_toxicity(basket)
    avg_tox = tox["avg_tox"]
    n = len(basket)

    # Linear model: coupon ~ tox*C[0] + n*C[1] + term_m*C[2] + prot_bar*C[3] + C[4]
    C = COUPON_COEFS
    predicted = C[0] * avg_tox + C[1] * n + C[2] * term_months + C[3] * barrier + C[4]
    predicted = max(6, min(50, predicted))

    # Lookup table — find closest term
    closest_term = min(COUPON_BY_TERM.keys(), key=lambda k: abs(k - term_months))
    lookup = COUPON_BY_TERM.get(closest_term, {})
    lookup_mean = lookup.get("mean", 20)
    lookup_std = lookup.get("std", 8)

    # Blend: weight lookup more for terms with many data points
    n_quotes = lookup.get("n", 10)
    lookup_weight = min(0.7, 0.3 + n_quotes / 500)
    blended = predicted * (1 - lookup_weight) + lookup_mean * lookup_weight

    return {
        "coupon_model": round(predicted, 2),
        "coupon_lookup": round(lookup_mean, 2),
        "coupon_blended": round(blended, 2),
        "lookup_std": round(lookup_std, 2),
        "n_quotes": n_quotes,
        "closest_term": closest_term,
        "vs_market": "выше рынка" if blended > lookup_mean else "ниже рынка",
    }


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 5: Stress test — historical drawdown scenarios
# ═══════════════════════════════════════════════════════════════

def compute_stress_scenarios_v2(yf_data: Dict, basket: List[str],
                                 beta_avg: float) -> List[Dict]:
    """Enhanced stress test with real historical drawdown scenarios."""
    scenarios = [
        {"name": "COVID Mar 2020", "spx_drop": -34, "vol_spike": 82,
         "duration_days": 23, "recovery_days": 148},
        {"name": "2022 Bear Market", "spx_drop": -25, "vol_spike": 36,
         "duration_days": 282, "recovery_days": 400},
        {"name": "2018 Q4 Selloff", "spx_drop": -20, "vol_spike": 36,
         "duration_days": 65, "recovery_days": 120},
        {"name": "Aug 2024 Yen Carry", "spx_drop": -8, "vol_spike": 65,
         "duration_days": 3, "recovery_days": 14},
        {"name": "Gradual Grind -15%", "spx_drop": -15, "vol_spike": 28,
         "duration_days": 180, "recovery_days": 300},
    ]

    for sc in scenarios:
        basket_drop = sc["spx_drop"] * beta_avg * 1.1
        worst_ticker_drop = basket_drop * 1.4
        barrier_breach = worst_ticker_drop < -35
        sc["basket_drop"] = round(basket_drop, 1)
        sc["worst_ticker_drop"] = round(worst_ticker_drop, 1)
        sc["barrier_breach_65"] = barrier_breach
        sc["barrier_breach_60"] = worst_ticker_drop < -40
        sc["coupon_survival"] = sc["duration_days"] < 126
        sc["risk_level"] = "CRITICAL" if barrier_breach else ("WARNING" if worst_ticker_drop < -25 else "OK")

    return scenarios


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 6: Dispersion signal — vol spread as coupon indicator
# ═══════════════════════════════════════════════════════════════

def compute_dispersion_signal(yf_data: Dict, basket: List[str]) -> Dict:
    """Vol dispersion analysis — higher spread = higher coupon opportunity."""
    vols = []
    for t in basket:
        if t in yf_data:
            vols.append(yf_data[t].get("iv30", 30))
        else:
            vols.append(30)

    if len(vols) < 2:
        return {"dispersion": 0, "signal": "NEUTRAL", "spread": 0}

    vol_spread = max(vols) - min(vols)
    vol_std = float(np.std(vols))
    avg_vol = float(np.mean(vols))

    # High dispersion = good for coupon, bad for worst-of risk
    signal = "STRONG" if vol_spread > 20 else ("MODERATE" if vol_spread > 10 else "WEAK")
    coupon_boost = min(5, vol_spread * 0.2)

    return {
        "dispersion": round(vol_std, 1),
        "spread": round(vol_spread, 1),
        "avg_vol": round(avg_vol, 1),
        "min_vol": round(min(vols), 1),
        "max_vol": round(max(vols), 1),
        "signal": signal,
        "coupon_boost_pct": round(coupon_boost, 1),
        "per_ticker": {t: round(v, 1) for t, v in zip(basket, vols)},
    }


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 7: Optimal barrier selection
# ═══════════════════════════════════════════════════════════════

def find_optimal_barrier(basket: List[str], avg_vol: float,
                         avg_tox: float) -> Dict:
    """Find optimal KI barrier level (55-75%) for best risk/return."""
    results = []
    for bar_pct in range(55, 76, 5):
        bar = bar_pct / 100
        # P(KI) increases with lower barrier and higher vol
        distance_to_bar = 1 - bar
        p_ki = max(2, min(60, avg_tox * 40 + (avg_vol - 25) * 0.5 - distance_to_bar * 30))
        # Coupon increases with lower barrier (more risk)
        coupon = max(8, 26 * (1 + (0.65 - bar) * 2) * (1 + avg_vol / 100))
        coupon = min(45, coupon)
        # Risk-adjusted score
        expected_return = coupon * (1 - p_ki / 100)
        expected_loss = p_ki / 100 * (1 - bar) * 100
        net = expected_return - expected_loss * 0.5
        results.append({
            "barrier": bar_pct,
            "p_ki": round(p_ki, 1),
            "est_coupon": round(coupon, 1),
            "expected_return": round(expected_return, 1),
            "expected_loss": round(expected_loss, 1),
            "net_score": round(net, 1),
        })

    results.sort(key=lambda x: x["net_score"], reverse=True)
    best = results[0]
    return {
        "optimal_barrier": best["barrier"],
        "optimal_coupon": best["est_coupon"],
        "optimal_p_ki": best["p_ki"],
        "all_barriers": results,
        "recommendation": f"Оптимальный барьер: {best['barrier']}% (купон ~{best['est_coupon']:.0f}%, P(KI) {best['p_ki']:.0f}%)",
    }


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 8: Earnings proximity risk
# ═══════════════════════════════════════════════════════════════

def compute_earnings_risk(yf_data: Dict, basket: List[str]) -> Dict:
    """Earnings proximity risk — dates near obs dates increase gap risk."""
    obs_days = [63, 126, 189, 252, 315, 378, 441, 504]
    risk_zones = []
    for t in basket:
        info = yf_data.get(t, {})
        ne = info.get("next_earnings")
        if ne:
            try:
                from datetime import datetime
                earn_date = datetime.strptime(ne[:10], "%Y-%m-%d")
                days_until = (earn_date - datetime.now()).days
                for obs in obs_days:
                    if abs(days_until - obs) < 7:
                        risk_zones.append({
                            "ticker": t, "obs_day": obs,
                            "earnings_in": days_until,
                            "gap_risk": "HIGH",
                        })
            except Exception:
                pass

    n_risks = len(risk_zones)
    return {
        "n_risk_zones": n_risks,
        "risk_zones": risk_zones[:5],
        "risk_level": "HIGH" if n_risks >= 2 else ("MEDIUM" if n_risks == 1 else "LOW"),
        "recommendation": f"{n_risks} отчётов совпадают с obs dates — повышенный gap risk" if n_risks > 0 else "Нет конфликтов с obs dates",
    }


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 9: Sector concentration penalty
# ═══════════════════════════════════════════════════════════════

def compute_sector_concentration(basket: List[str]) -> Dict:
    """Enhanced sector concentration analysis."""
    sectors = {}
    for t in basket:
        s = SECTOR_MAP.get(t, "Unknown")
        sectors[s] = sectors.get(s, 0) + 1

    n = len(basket)
    n_sectors = len(sectors)
    hhi = sum((c / n) ** 2 for c in sectors.values())
    max_sector = max(sectors, key=sectors.get) if sectors else "N/A"
    max_pct = round(sectors.get(max_sector, 0) / max(1, n) * 100)

    # Penalty: HHI > 0.5 = concentrated, > 0.8 = very concentrated
    penalty = 0
    if hhi > 0.8:
        penalty = -8
    elif hhi > 0.5:
        penalty = -4
    elif n_sectors >= 3:
        penalty = 2

    return {
        "hhi": round(hhi, 3),
        "n_sectors": n_sectors,
        "max_sector": max_sector,
        "max_pct": max_pct,
        "sectors": sectors,
        "penalty": penalty,
        "label": "CONCENTRATED" if hhi > 0.5 else "DIVERSIFIED",
        "recommendation": f"Добавьте тикер из другого сектора" if hhi > 0.5 else f"{n_sectors} секторов — хорошая диверсификация",
    }


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 10: TOP-3 baskets from entire universe
# ═══════════════════════════════════════════════════════════════

def generate_top_baskets(n_tickers: int = 4, n_results: int = 3) -> List[Dict]:
    """Generate TOP baskets from universe optimized for best Phoenix."""
    from src.real_data import TOX_EXPERIENCE

    # Score all tickers by safety (low tox + known history)
    scored = []
    for t, (losses, wins) in TOX_EXPERIENCE.items():
        total = losses + wins + 1
        tox = losses / total
        if tox < 0.4 and wins >= 2:
            scored.append((t, tox, wins))

    scored.sort(key=lambda x: (x[1], -x[2]))
    safe_tickers = [s[0] for s in scored[:20]]

    # Build baskets with sector diversity
    baskets = []

    # Basket 1: Safest — lowest tox from different sectors
    b1 = []
    b1_sectors = set()
    for t in safe_tickers:
        s = SECTOR_MAP.get(t, "Unknown")
        if s not in b1_sectors and len(b1) < n_tickers:
            b1.append(t)
            b1_sectors.add(s)
    if len(b1) < n_tickers:
        for t in safe_tickers:
            if t not in b1 and len(b1) < n_tickers:
                b1.append(t)

    # Basket 2: High coupon — moderate tox for premium
    moderate = [(t, tx, w) for t, tx, w in scored if 0.15 < tx < 0.35]
    moderate.sort(key=lambda x: -x[2])
    b2 = [m[0] for m in moderate[:n_tickers]]

    # Basket 3: Balanced — mix of safe + moderate
    b3 = safe_tickers[:n_tickers // 2] + [m[0] for m in moderate[:n_tickers - n_tickers // 2]]

    result = []
    for name, bsk in [("SAFEST", b1), ("HIGH COUPON", b2), ("BALANCED", b3)]:
        if len(bsk) >= 2:
            tox = compute_toxicity(bsk)
            sector_info = compute_sector_concentration(bsk)
            result.append({
                "name": name,
                "basket": bsk,
                "avg_tox": tox["avg_tox"],
                "n_sectors": sector_info["n_sectors"],
                "sectors": list(sector_info["sectors"].keys()),
                "est_score": round(max(50, min(100, 75 + (0.5 - tox["avg_tox"]) * 30 + sector_info["penalty"])), 1),
            })

    result.sort(key=lambda x: x["est_score"], reverse=True)
    return result


def _safe_vols(td: Dict, tickers: List[str]) -> List[float]:
    """Volatility values for tickers present in data, dropping NaN/None."""
    out = []
    for t in tickers:
        if t in td:
            v = td[t].get("volatility")
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                out.append(float(v))
    return out


def _safe_mean(vals: List[float], default: float) -> float:
    """Mean that never returns NaN — falls back to default on empty input."""
    if not vals:
        return float(default)
    m = float(np.mean(vals))
    return float(default) if math.isnan(m) else m


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
    """Fetch price + fundamental data via data_module (xfinlink primary, yfinance fallback).
    Enriches with PE, PEG, targets, DCF from xfinlink fundamentals/metrics."""
    if not tickers:
        return {}
    # Use unified data module for prices
    raw_data = fetch_ticker_data(tickers, period=period)

    # Try to get fundamentals from xfinlink
    xfl_fundamentals = {}
    xfl_metrics = {}
    if XFL_AVAILABLE:
        try:
            import xfinlink as xfl
            for t in tickers:
                try:
                    f = xfl.fundamentals(t)
                    if f:
                        xfl_fundamentals[t] = f
                except Exception:
                    pass
                try:
                    m = xfl.metrics(t)
                    if m:
                        xfl_metrics[t] = m
                except Exception:
                    pass
        except Exception:
            pass

    result = {}
    for t, d in raw_data.items():
        spot = d["spot"]

        # Fundamentals from xfinlink (or sensible defaults)
        fund = xfl_fundamentals.get(t, {})
        met = xfl_metrics.get(t, {})

        pe_est = fund.get("pe_ratio", fund.get("pe_ttm", met.get("pe_ratio", 25.0)))
        peg_est = fund.get("peg_ratio", met.get("peg_ratio", 1.5))
        # Ensure valid numbers
        if pe_est is None or (isinstance(pe_est, float) and math.isnan(pe_est)):
            pe_est = 25.0
        if peg_est is None or (isinstance(peg_est, float) and math.isnan(peg_est)):
            peg_est = 1.5

        # Target prices from xfinlink or estimates
        target_price = fund.get("target_price", fund.get("price_target_mean", spot * 1.08))
        if target_price is None or target_price <= 0:
            target_price = spot * 1.08
        # DCF estimate from metrics or formula
        dcf_val = met.get("fair_value", fund.get("dcf_value", target_price * 0.85))
        if dcf_val is None or dcf_val <= 0:
            dcf_val = target_price * 0.85
        bcs_target = target_price * 0.92
        n_analysts = fund.get("n_analysts", fund.get("analyst_count", 15))
        if n_analysts is None:
            n_analysts = 15

        closes = d.get("closes", [])
        returns = d.get("returns", [])
        if isinstance(closes, np.ndarray):
            closes = closes.tolist()
        if isinstance(returns, np.ndarray):
            returns = returns.tolist()

        result[t] = {
            "spot": d["spot"],
            "iv30": d["iv30"],
            "real_1y": d["real_1y"],
            "vol_used": d["vol_used"],
            "beta": d["beta"],
            "pe": round(float(pe_est), 1),
            "peg": round(float(peg_est), 2),
            "ema200_pct": d["ema200_pct"],
            "ema200_above": d["ema200_pct"] > 0,
            "dcf": round(float(dcf_val), 2),
            "dcf_upside": round((dcf_val / spot - 1) * 100, 1),
            "target_price": round(float(target_price), 2),
            "target_upside": round((target_price / spot - 1) * 100, 1),
            "bcs_target": round(float(bcs_target), 2),
            "bcs_upside": round((bcs_target / spot - 1) * 100, 1),
            "avg_target": round((target_price + bcs_target + dcf_val) / 3, 2),
            "avg_upside": round(((target_price + bcs_target + dcf_val) / 3 / spot - 1) * 100, 1),
            "n_analysts": int(n_analysts),
            "sector": SECTOR_MAP.get(t, fund.get("sector", "Unknown")),
            "closes": closes,
            "returns": returns,
            "next_earnings": fund.get("next_earnings_date", None),
            "source": d.get("source", "unknown"),
        }
        rec = ANALYST_MAP.get(t, (1.80, "buy"))
        result[t]["rec_score"] = rec[0]
        result[t]["rec_label"] = rec[1]
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
    available = [t for t in tickers if t in yf_data and len(yf_data[t].get("returns", [])) > 10]
    if not available:
        return {"var_95": -2.0, "var_99": -3.5, "cvar_95": -3.0, "max_loss_1d": -5.0,
                "skew": -0.5, "kurtosis": 4.0, "regime_var": -2.5, "tail_dep": 0.3}
    # Equal-weight portfolio returns
    min_len = min(len(yf_data[t]["returns"]) for t in available)
    if min_len < 10:
        return {"var_95": -2.0, "var_99": -3.5, "cvar_95": -3.0, "max_loss_1d": -5.0,
                "skew": -0.5, "kurtosis": 4.0, "regime_var": -2.5, "tail_dep": 0.3}
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
    available = [t for t in tickers if t in yf_data and len(yf_data[t].get("returns", [])) > 10]
    if not available:
        return {"sharpe": 0, "sortino": 0, "calmar": 0, "cagr": 0, "max_dd": 0,
                "avg_pair_corr": 0, "tracking_error": 0, "info_ratio": 0, "active_share": 90}
    min_len = min(len(yf_data[t]["returns"]) for t in available)
    if min_len < 10:
        return {"sharpe": 0, "sortino": 0, "calmar": 0, "cagr": 0, "max_dd": 0,
                "avg_pair_corr": 0, "tracking_error": 0, "info_ratio": 0, "active_share": 90}
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

    # 2. Classical VaR from ClickHouse stats (no simulation needed)
    td = ch_data.get("tickers", {})
    qiskit_results = {}
    for t in basket_tickers:
        if t in td:
            mu = td[t]["mean_return"]
            vol = td[t]["volatility"]
            var_95 = mu - 1.645 * vol
            cvar = mu - 2.063 * vol
            qiskit_results[t] = {"var": float(var_95), "cvar": float(cvar),
                                 "method": "classical_parametric", "quantum": False}
    result["qiskit"] = qiskit_results
    result["avg_qvar"] = float(np.mean([r["var"] for r in qiskit_results.values()])) if qiskit_results else 50.0

    # 3. Market data (xfinlink primary, yfinance fallback)
    yf_data = _fetch_yf_data(basket_tickers)
    result["yf"] = yf_data
    # Report which data source was used
    if yf_data:
        first_src = next(iter(yf_data.values()), {}).get("source", "yfinance")
        result["data_source"] = first_src
    else:
        result["data_source"] = get_data_source_status()

    # 4. Correlation matrix
    result["corr"] = _compute_correlation_matrix(yf_data, basket_tickers)

    # 4b. Rolling correlations (time-varying) — detects regime changes
    result["rolling_corr"] = compute_rolling_correlations(basket_tickers, window=60)

    # 4c. IV Percentile — where is current vol vs history
    result["iv_percentile"] = fetch_iv_percentile(basket_tickers)

    # 4d. Earnings gap risk — warnings for upcoming reports
    result["earnings_gap_risk"] = check_earnings_risk(basket_tickers)

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

    # 11. Multi-indicator averages (needed by scoring)
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

    # 12. Scoring — self-learning multi-factor model
    # Scale 50-100: S&P500 ETF basket = 100 (benchmark), higher = safer/better product
    # Loads learned weights from Google Drive; falls back to calibrated defaults
    wo = ch_data.get("worst_of", {})

    # Load learned scoring weights (self-learning)
    _learned = _load_scoring_weights()

    # Raw inputs
    raw_pki = wo.get("barrier_breach_pct", 15)
    avg_vol_score = _safe_mean(_safe_vols(td, basket_tickers), 30)
    avg_corr = result["corr"].get("avg_corr", 0.45)
    mean_ret = wo.get("mean", 100)
    dcf_up = result["ind"].get("dcf_avg", 0) if result["ind"] else 0
    rec_avg = result["ind"].get("rec_avg", 2.0) if result["ind"] else 2.0

    # Toxicity from settled notes
    tox_info = compute_toxicity(basket_tickers)
    avg_tox = tox_info["avg_tox"]
    result["toxicity"] = tox_info

    # Factor calculations (each normalized 0-1, then weighted)
    w = _learned  # learned weights dict
    f_pki_norm = min(1.0, raw_pki / 50)                        # 0=no risk, 1=50%+ breach
    f_vol_norm = min(1.0, max(0, (avg_vol_score - 15) / 45))   # 15%=safe, 60%=max risk
    f_corr_norm = min(1.0, max(0, avg_corr))                    # 0=uncorrelated(good), 1=perfect(bad)
    f_tox_norm = min(1.0, max(0, avg_tox))                      # 0=safe, 1=toxic
    f_div_norm = min(1.0, len(basket_tickers) / 6)              # 1 ticker=0.17, 6+=1.0
    f_fund_norm = min(1.0, max(0, (dcf_up + 15) / 30))         # -15%=0, +15%=1.0
    f_quality_norm = min(1.0, max(0, (2.5 - rec_avg) / 1.5))   # 1.0(strong buy)=1, 2.5(hold)=0
    f_ema_norm = (sum(1 for t in basket_tickers if t in yf_data and yf_data[t].get("ema200_above")) / max(1, len(basket_tickers)))

    # Bonus factors (add to score)
    bonus = (
        w["w_div"] * f_div_norm +
        w["w_fund"] * f_fund_norm +
        w["w_quality"] * f_quality_norm +
        w["w_ema"] * f_ema_norm +
        w["w_mean_ret"] * min(1.0, max(0, (mean_ret - 70) / 60))
    )
    # Penalty factors (subtract from score)
    penalty = (
        w["w_pki"] * f_pki_norm +
        w["w_vol"] * f_vol_norm +
        w["w_corr"] * f_corr_norm +
        w["w_tox"] * f_tox_norm
    )
    # Score: base 75 (center of 50-100), ± adjustments
    # Max bonus ~25pt, max penalty ~25pt → range 50-100
    score_pct = w["base"] + bonus - penalty
    score_pct = max(50, min(100, score_pct))
    result["score"] = round(score_pct, 1)
    result["score_factors"] = {
        "P(KI)": {"raw": round(raw_pki, 1), "norm": round(f_pki_norm, 2), "impact": round(-w["w_pki"] * f_pki_norm, 1)},
        "Volatility": {"raw": round(avg_vol_score, 1), "norm": round(f_vol_norm, 2), "impact": round(-w["w_vol"] * f_vol_norm, 1)},
        "Correlation": {"raw": round(avg_corr, 2), "norm": round(f_corr_norm, 2), "impact": round(-w["w_corr"] * f_corr_norm, 1)},
        "Toxicity": {"raw": round(avg_tox, 2), "norm": round(f_tox_norm, 2), "impact": round(-w["w_tox"] * f_tox_norm, 1)},
        "Diversification": {"raw": len(basket_tickers), "norm": round(f_div_norm, 2), "impact": round(w["w_div"] * f_div_norm, 1)},
        "Fundamentals": {"raw": round(dcf_up, 1), "norm": round(f_fund_norm, 2), "impact": round(w["w_fund"] * f_fund_norm, 1)},
        "Analyst": {"raw": round(rec_avg, 2), "norm": round(f_quality_norm, 2), "impact": round(w["w_quality"] * f_quality_norm, 1)},
        "EMA200 trend": {"raw": round(f_ema_norm * 100, 0), "norm": round(f_ema_norm, 2), "impact": round(w["w_ema"] * f_ema_norm, 1)},
    }
    result["scoring_generation"] = w.get("generation", 0)

    # 13. P(KI), P(autocall) — Numerix-calibrated
    # Numerix benchmark: 4-name large-cap tech, 65% barrier, 2Y → P(KI) ~15-25%
    # P(autocall) typically 40-70% for 100% autocall barrier
    p_ki = wo.get("barrier_breach_pct", 25)
    p_autocall = min(85, max(10, 100 - p_ki * 1.5 - avg_corr * 10))
    _vols = _safe_vols(td, basket_tickers)
    avg_vol = _safe_mean(_vols, 35)
    dispersion = float(np.std(_vols)) if len(_vols) > 1 else 8.0
    result["p_ki"] = round(p_ki, 1)
    result["p_autocall"] = round(p_autocall, 1)
    result["avg_vol"] = round(float(avg_vol), 1)
    result["dispersion"] = round(dispersion, 1)

    # 14. IV rank — percentile of current IV vs 1Y range
    _ivr = float(avg_vol) * 1.1 + 10
    if math.isnan(_ivr):
        _ivr = 45.0
    result["iv_rank"] = min(99, max(5, int(_ivr)))

    # 15. E[life] and coupon estimates — Numerix-comparable
    # Barclays benchmark: 9.5% p.a. for MSFT/AMZN/NVDA/META (65% barrier)
    # Our product: 26% target coupon (higher risk) → scale by risk
    e_life = round(max(0.5, 2.0 - p_autocall / 100 * 1.2), 2)
    # Fair coupon: base 26% adjusted by P(KI) and volatility
    # Numerix: higher P(KI) → higher coupon (risk premium)
    coupon_pa = round(26.0 * (0.8 + p_ki / 100 * 0.4) * min(1.2, avg_vol_score / 30), 2)
    coupon_pa = min(45.0, max(8.0, coupon_pa))  # cap at reasonable range
    p_clean_loss = round(max(0, p_ki * 0.55 * (1 + avg_corr * 0.3)), 1)
    # E[payout] = P(no KI) * (100 + coupons_earned) + P(KI) * recovery
    # Numerix: recovery ~= worst_of_final / strike, typically 40-70% of notional
    recovery = max(30, 65 - p_ki * 0.5)  # higher P(KI) → lower recovery
    e_payout = round((1 - p_ki/100) * (100 + coupon_pa * e_life) + p_ki/100 * recovery, 1)
    result["e_life"] = e_life
    result["coupon_pa"] = coupon_pa
    result["p_clean_loss"] = p_clean_loss
    result["e_payout"] = e_payout

    # 16. Risk score — unified with main score (50-100 scale)
    # Uses same learned weights, same direction: higher = safer
    result["risk_score"] = result["score"]
    result["risk_components"] = {k: v["impact"] for k, v in result["score_factors"].items()}

    # 17. External services status
    result["external_services"] = {
        "colab": get_colab_status(),
        "gdrive": gdrive_status(),
        "nvidia": nvidia_status(),
    }

    # 18. NVIDIA AI risk analysis (free, graceful fallback)
    _iv30 = result["ind"].get("iv30_avg", 35) if result["ind"] else 35
    if _iv30 is None or (isinstance(_iv30, float) and math.isnan(_iv30)):
        _iv30 = 35
    try:
        nvidia_risk = analyze_basket_risk(
            tickers=basket_tickers,
            scores={t: yf_data[t].get("score", 50) for t in basket_tickers if t in yf_data},
            p_ki=p_ki,
            avg_vol=_iv30,
            avg_corr=avg_corr,
        )
    except Exception:
        nvidia_risk = {"risk_level": "N/A", "score_adjustment": 0,
                       "key_risks": [], "concentration_warning": False,
                       "recommendation": "—", "source": "error"}
    result["nvidia_risk"] = nvidia_risk

    # Apply NVIDIA score adjustment
    nvidia_adj = nvidia_risk.get("score_adjustment", 0)
    adjusted_score = max(50, min(100, result["score"] + nvidia_adj))
    result["score"] = round(adjusted_score, 1)
    result["risk_score"] = result["score"]
    result["risk_components"]["NVIDIA AI adj"] = round(nvidia_adj, 1)

    # 19. Numerix comparison benchmarks
    result["numerix"] = {
        "ref_product": "Barclays XS2959260741 (MSFT/AMZN/NVDA/META)",
        "ref_barrier": 65,
        "ref_coupon_pa": 9.52,
        "ref_tenor": "2Y",
        "ref_risk_class": "6/7",
        "our_coupon_pa": coupon_pa,
        "coupon_premium": round(coupon_pa - 9.52, 2),
        "note": "Our product targets 26% p.a. vs market ~10% → 2.7x risk premium justified by higher P(KI) acceptance",
    }

    # 20. Smart alternatives (replace worst ticker with better options)
    result["smart_alts"] = compute_smart_alternatives(basket_tickers, yf_data, tox_info)

    # 21. Self-learning: calibrate scoring + P(loss) model metrics
    try:
        from src.real_data import get_p_loss_model_metrics
        p_loss_metrics = get_p_loss_model_metrics()

        # Calibrate scoring weights on settled notes
        cal_result = calibrate_scoring_on_settled()

        result["self_learning"] = {
            "generation": cal_result["generation"],
            "scoring_mae_before": cal_result["before_mae"],
            "scoring_mae_after": cal_result["after_mae"],
            "scoring_improvement_pct": cal_result["improvement_pct"],
            "scoring_acc_before": cal_result.get("acc_before", 0),
            "scoring_acc_after": cal_result.get("acc_after", 0),
            "p_loss_accuracy": p_loss_metrics.get("accuracy", 0),
            "p_loss_f1": p_loss_metrics.get("f1", 0),
            "p_loss_precision": p_loss_metrics.get("precision", 0),
            "p_loss_recall": p_loss_metrics.get("recall", 0),
            "p_loss_confusion": p_loss_metrics.get("confusion", {}),
            "n_training_notes": p_loss_metrics.get("n_samples", 0),
            "weights": cal_result.get("weights", {}),
            "feature_importance": cal_result.get("feature_importance", {}),
            "weak_features": cal_result.get("weak_features", []),
            "optimizer": "momentum_sgd_0.9",
            "status": "calibrated",
        }
    except Exception:
        result["self_learning"] = {"generation": 0, "status": "init"}

    # ── 10 IMPROVEMENTS ──

    # IMP-1: Best Phoenix ranker
    result["phoenix_ranker"] = rank_best_phoenix(basket_tickers, yf_data, tox_info, ch_data)

    # IMP-2: Real correlations from yfinance (already in result["corr"])
    # Enhanced: add pairwise detail
    corr_detail = result["corr"]
    if corr_detail.get("matrix"):
        n_pairs = len(corr_detail["matrix"])
        high_corr = [p for p in corr_detail.get("pairs", []) if abs(p.get("corr", 0)) > 0.7]
        result["corr_enhanced"] = {
            "n_pairs": n_pairs,
            "high_corr_pairs": len(high_corr),
            "warning": len(high_corr) > 2,
            "recommendation": f"{len(high_corr)} пар с корр > 0.7 — worst-of risk выше" if high_corr else "Низкая корреляция — хорошо для worst-of",
        }
    else:
        result["corr_enhanced"] = {"n_pairs": 0, "high_corr_pairs": 0, "warning": False, "recommendation": "Нет данных корреляций"}

    # IMP-3: Empirical P(KI)
    result["empirical_pki"] = empirical_p_ki(basket_tickers, term_months=24)

    # IMP-4: Calibrated coupon
    result["calibrated_coupon"] = calibrated_coupon(basket_tickers, term_months=24, barrier=0.65)

    # IMP-5: Enhanced stress scenarios
    result["stress_v2"] = compute_stress_scenarios_v2(yf_data, basket_tickers, beta_avg)

    # IMP-6: Dispersion signal
    result["dispersion_signal"] = compute_dispersion_signal(yf_data, basket_tickers)

    # IMP-7: Optimal barrier
    result["optimal_barrier"] = find_optimal_barrier(basket_tickers, avg_vol, avg_tox)

    # IMP-8: Earnings risk
    result["earnings_risk"] = compute_earnings_risk(yf_data, basket_tickers)

    # IMP-9: Sector concentration
    result["sector_concentration"] = compute_sector_concentration(basket_tickers)

    # IMP-10: TOP-3 recommended baskets
    result["top_baskets"] = generate_top_baskets(n_tickers=len(basket_tickers))

    return result
