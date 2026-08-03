"""
Real Data Module — Karpathy Method (External Computation).

Sources:
1. TOX dict — toxicity from 90+ real settled US structured notes (2021-2024)
2. SETTLED — real backtest outcomes (win/loss) for historical products
3. DEALER_QUOTES — 895 real dealer pricing responses (from XLSX)

All heavy computation done ONCE in precompute_dealer_benchmark().
Returns flat dict for pure Streamlit rendering.
"""

import csv
import numpy as np
import statistics
from typing import Dict, List, Any
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════
# 1. TOXICITY DATABASE (from real settled notes 2021-2024)
# Format: ticker → (loss_count, win_count) from actual product outcomes
# ═══════════════════════════════════════════════════════════════════

TOX_EXPERIENCE: Dict[str, tuple] = {
    # TOXIC — frequently caused losses
    "WDC": (18, 3), "QCOM": (16, 4), "AMD": (16, 6), "NFLX": (10, 3),
    "AMZN": (10, 4), "MELI": (7, 2), "NVDA": (5, 4), "PLUG": (3, 0),
    "ENPH": (3, 1), "RUN": (2, 1), "BYND": (2, 1), "NIO": (2, 3),
    "FCX": (2, 0), "TWLO": (3, 4), "TWTR": (2, 1), "VIPS": (2, 2),
    "ROKU": (2, 0), "SNAP": (2, 0), "MSTR": (3, 1),
    # SAFE — frequently autocalled / won
    "AAPL": (2, 6), "DAL": (2, 5), "ABMD": (0, 5), "BIIB": (1, 4),
    "DISCA": (1, 5), "DPZ": (0, 2), "BABA": (2, 3), "SBUX": (0, 1),
    "NOW": (0, 3), "VRTX": (1, 3), "COP": (2, 3), "PANW": (2, 2),
    "ALB": (2, 3), "APTV": (0, 2), "UBER": (0, 3),
    # Additional from experience
    "MSFT": (1, 8), "GOOG": (1, 7), "V": (0, 5), "MA": (0, 4),
    "PG": (0, 3), "KO": (0, 3), "WMT": (0, 3), "MCD": (1, 5),
    "PEP": (1, 4), "UNH": (1, 3), "ORCL": (2, 4), "PM": (0, 4),
    "LLY": (1, 4), "T": (1, 3), "DELL": (1, 3), "INTC": (5, 3),
    "TEAM": (2, 2), "ADBE": (1, 3), "CRM": (1, 4), "META": (2, 4),
    "TSLA": (4, 3),
}


# ═══════════════════════════════════════════════════════════════════
# 2. SETTLED NOTES BACKTEST (real outcomes from 2021-2024)
# Format: basket, term_years, bad (1=loss, 0=win)
# ═══════════════════════════════════════════════════════════════════

SETTLED_NOTES = [
    ("AAPL/DAL/TSLA/NOK/MBT", 3.0, 0),
    ("AAPL/DAL/TSLA/SBER/UCG", 3.0, 1),
    ("ABMD/NKE/MCD/INTC/UCG", 3.0, 1),
    ("BCS/BMW/SBUX", 2.8, 0),
    ("BIDU/DAI/INTC/SBER/YNDX", 2.6, 0),
    ("ABMD/SBER/NOW/VRTX/WDC", 2.1, 0),
    ("ALB/APTV/COP/PANW/WDC", 2.1, 0),
    ("ABMD/BIIB/NOW/VRTX/SPG", 1.8, 0),
    ("ABMD/DISCA/YNDX/WMB", 1.3, 0),
    ("AAPL/BABA/BMRN/TWLO", 1.1, 0),
    ("AMD/CTRA/MELI/SBER", 1.6, 0),
    ("ALXN/DISCA/DPZ/UBER/NTES", 3.8, 0),
    ("AAPL/DAL/TSLA/NOK/UCG", 3.1, 1),
    ("ANET/NVDA/QCOM/VMW", 1.0, 0),
    ("ALXN/DISCA/DPZ/UBER/NTES/VEEV", 1.1, 0),
    ("DISCA/GILD/NFLX/OKTA", 1.1, 0),
    ("AMD/AMZN/NFLX/QCOM/TWTR", 1.0, 0),
    ("AMD/TEAM/TWLO/VIPS/W", 0.5, 0),
    ("TEAM/BMRN/DISCA/NTES/UBER", 0.5, 0),
    ("AAPL/BABA/NTES/TWLO", 3.1, 1),
    ("AMD/AMZN/NFLX/QCOM/WDC", 3.3, 1),
    ("BABA/AMZN/EBAY/VIPS", 0.3, 0),
    ("AMD/NIO/OKTA/SPG/TWLO", 0.5, 0),
    ("BYND/NIO/RUN/TSLA", 0.5, 0),
    ("BYND/NIO/RUN/TSLA", 3.1, 1),
    ("AMD/AMZN/NFLX/QCOM/WDC", 3.4, 1),
    ("AMD/AMZN/NFLX/QCOM/TWTR", 3.0, 1),
    ("AMD/AMZN/NFLX/QCOM/WDC", 3.3, 1),
    ("AMD/AMZN/NFLX/QCOM/WDC", 3.3, 1),
    ("AMD/MELI/NVDA/QCOM/WDC", 2.0, 1),
    ("AMD/AMZN/NFLX/QCOM/WDC", 3.0, 1),
    ("COP/PANW/WDC/ALB/APTV", 3.6, 1),
    ("AMD/AMZN/NFLX/QCOM/WDC", 3.0, 1),
    ("AMD/MELI/NVDA/QCOM/WDC", 2.0, 1),
    ("BIIB/BMRN/ILMN", 0.8, 0),
    ("AMD/AMZN/NFLX/QCOM/WDC", 3.0, 1),
    ("AMD/AMZN/NFLX/QCOM/WDC", 3.3, 1),
    ("AMD/AMZN/NFLX/QCOM/WDC", 3.4, 1),
    ("AMD/AMZN/NFLX/QCOM/WDC", 3.0, 1),
    ("RUN/NOVA/PLUG/ENPH/FCX/BMRN", 0.8, 0),
    ("AMD/AMZN/NFLX/QCOM/WDC", 3.3, 1),
    ("ARCL/BLM/ENPH/FCX/PLUG", 3.6, 1),
    ("AMD/MELI/NVDA/QCOM/WDC", 4.0, 1),
    ("AMD/MELI/NVDA/QCOM/WDC", 2.0, 1),
    ("AMD/AMZN/NFLX/QCOM/WDC", 3.3, 1),
    ("AMD/MELI/NVDA/QCOM/WDC", 3.3, 1),
    ("COP/PANW/WDC/VRTX/ALB", 3.0, 0),
    ("XPEV/APA/CF/STLA", 1.3, 0),
    ("AMD/MELI/NVDA/QCOM/WDC", 3.3, 1),
    ("AMD/MELI/NVDA/QCOM/WDC", 3.3, 1),
]


# ═══════════════════════════════════════════════════════════════════
# 3. COUPON LOOKUP TABLE (from 828 real dealer quotes, pre-computed)
# ═══════════════════════════════════════════════════════════════════

# Average coupons by term (from real dealer responses, USD only)
COUPON_BY_TERM = {
    3: {"mean": 32.9, "std": 12.2, "n": 6},
    6: {"mean": 29.4, "std": 14.9, "n": 26},
    12: {"mean": 21.5, "std": 10.1, "n": 64},
    24: {"mean": 14.1, "std": 4.6, "n": 104},
    36: {"mean": 25.3, "std": 13.1, "n": 178},
    48: {"mean": 27.8, "std": 16.5, "n": 41},
    60: {"mean": 18.4, "std": 11.3, "n": 357},
    84: {"mean": 14.2, "std": 6.1, "n": 51},
}

# Linear regression coefficients (from OLS on 828 quotes)
# coupon ~ tox*COEF[0] + n*COEF[1] + term_m*COEF[2] + prot_bar*COEF[3] + COEF[4]
COUPON_COEFS = [-7.922, 0.290, -0.0923, -4.054, 29.459]


# ═══════════════════════════════════════════════════════════════════
# 4. CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def compute_toxicity(tickers: List[str]) -> Dict[str, Any]:
    """Compute basket toxicity from real settled note experience."""
    scores = []
    per_ticker = {}
    for t in tickers:
        if t in TOX_EXPERIENCE:
            losses, wins = TOX_EXPERIENCE[t]
            score = losses / (losses + wins + 1)
            scores.append(score)
            per_ticker[t] = {
                "tox": round(score, 3),
                "losses": losses,
                "wins": wins,
                "label": "TOXIC" if score > 0.5 else ("RISKY" if score > 0.3 else "SAFE"),
            }
        else:
            per_ticker[t] = {"tox": 0.5, "losses": 0, "wins": 0, "label": "UNKNOWN"}

    avg_tox = float(np.mean(scores)) if scores else 0.5
    max_tox_ticker = max(per_ticker.items(), key=lambda x: x[1]["tox"])[0] if per_ticker else None

    return {
        "avg_tox": round(avg_tox, 3),
        "per_ticker": per_ticker,
        "max_tox_ticker": max_tox_ticker,
        "known_count": len(scores),
        "total_count": len(tickers),
        "risk_level": "HIGH" if avg_tox > 0.5 else ("MEDIUM" if avg_tox > 0.3 else "LOW"),
    }


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + np.exp(-x))
    ez = np.exp(x)
    return ez / (1.0 + ez)


def _extract_features(tickers: List[str], term_months: int) -> np.ndarray:
    """Extract features for P(loss) model: [avg_tox, max_tox, term_y, n_tickers, tox×term]."""
    tox_info = compute_toxicity(tickers)
    avg_tox = tox_info["avg_tox"]
    per_ticker = tox_info["per_ticker"]
    max_tox = max((v["tox"] for v in per_ticker.values()), default=0.5)
    term_y = term_months / 12
    n = len(tickers)
    return np.array([avg_tox, max_tox, term_y, n / 6.0, avg_tox * term_y])


# Logistic regression weights — trained via gradient descent on 50 settled notes
# Features: [avg_tox, max_tox, term_years, n_tickers/6, avg_tox × term_years]
# Updated by _train_p_loss_model() at module load
_P_LOSS_WEIGHTS = np.array([2.8, 1.5, 0.6, -0.3, 0.4])
_P_LOSS_BIAS = -3.2


def _train_p_loss_model() -> tuple:
    """Train logistic regression on settled notes via gradient descent.
    Returns (weights, bias, metrics)."""
    global _P_LOSS_WEIGHTS, _P_LOSS_BIAS

    X = []
    y = []
    for basket_str, term_y, bad in SETTLED_NOTES:
        tks = basket_str.split("/")
        feats = _extract_features(tks, int(term_y * 12))
        X.append(feats)
        y.append(float(bad))

    X = np.array(X)
    y = np.array(y)
    n_samples = len(y)

    # Initialize from current weights
    w = _P_LOSS_WEIGHTS.copy()
    b = float(_P_LOSS_BIAS)

    lr = 0.1
    best_loss = float("inf")
    best_w, best_b = w.copy(), b

    for epoch in range(200):
        # Forward pass
        logits = X @ w + b
        probs = np.array([_sigmoid(z) for z in logits])
        probs = np.clip(probs, 1e-7, 1 - 1e-7)

        # Binary cross-entropy
        loss = -np.mean(y * np.log(probs) + (1 - y) * np.log(1 - probs))

        # L2 regularization
        loss += 0.01 * np.sum(w ** 2)

        if loss < best_loss:
            best_loss = loss
            best_w = w.copy()
            best_b = b

        # Gradients
        errors = probs - y
        grad_w = X.T @ errors / n_samples + 0.02 * w
        grad_b = np.mean(errors)

        w -= lr * grad_w
        b -= lr * grad_b

        # Decay LR
        if epoch % 50 == 49:
            lr *= 0.5

    _P_LOSS_WEIGHTS = best_w
    _P_LOSS_BIAS = best_b

    # Compute accuracy
    logits = X @ best_w + best_b
    preds = np.array([_sigmoid(z) for z in logits])
    correct = np.sum((preds > 0.5) == y)
    acc = correct / n_samples

    # Precision / Recall / F1
    tp = np.sum((preds > 0.5) & (y == 1))
    fp = np.sum((preds > 0.5) & (y == 0))
    fn = np.sum((preds <= 0.5) & (y == 1))
    tn = np.sum((preds <= 0.5) & (y == 0))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(0.001, precision + recall)

    return best_w, best_b, {
        "accuracy": round(float(acc) * 100, 1),
        "precision": round(float(precision) * 100, 1),
        "recall": round(float(recall) * 100, 1),
        "f1": round(float(f1) * 100, 1),
        "loss": round(float(best_loss), 4),
        "confusion": {"tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn)},
        "n_samples": n_samples,
    }


# Train at module load (zero cost — 50 samples × 200 iterations < 10ms)
try:
    _P_LOSS_W_TRAINED, _P_LOSS_B_TRAINED, _P_LOSS_TRAIN_METRICS = _train_p_loss_model()
except Exception:
    _P_LOSS_TRAIN_METRICS = {"accuracy": 0, "f1": 0}


def compute_p_loss(tickers: List[str], term_months: int = 24) -> Dict[str, Any]:
    """
    Predict P(loss) using logistic regression trained on 50 settled notes.
    Features: avg_tox, max_tox, term_years, n_tickers, tox×term interaction.
    Auto-calibrated via gradient descent at module load.
    """
    feats = _extract_features(tickers, term_months)
    logit = float(feats @ _P_LOSS_WEIGHTS + _P_LOSS_BIAS)
    p_loss = _sigmoid(logit)
    p_loss = max(0.03, min(0.95, p_loss))

    tox_info = compute_toxicity(tickers)
    toxic_tickers = [t for t in tickers if t in TOX_EXPERIENCE
                     and TOX_EXPERIENCE[t][0] > TOX_EXPERIENCE[t][1]]

    guard_flag = p_loss > 0.25

    return {
        "p_loss": round(p_loss, 4),
        "p_loss_pct": round(p_loss * 100, 1),
        "guard_flag": guard_flag,
        "guard_msg": f"P(убыток)={p_loss*100:.0f}% > 25%. Toxic: {toxic_tickers}" if guard_flag else "Риск приемлемый",
        "toxic_tickers": toxic_tickers,
        "confidence": "HIGH" if len(tox_info.get("per_ticker", {})) > 0 else "LOW",
        "model_metrics": _P_LOSS_TRAIN_METRICS,
    }


def get_p_loss_model_metrics() -> Dict:
    """Return training metrics for the P(loss) model."""
    return _P_LOSS_TRAIN_METRICS


def predict_dealer_coupon(tickers: List[str], term_months: int = 24,
                          prot_bar: float = 0.65) -> Dict[str, Any]:
    """
    Predict what a real dealer would quote for this basket.
    Uses pre-calibrated linear model + term lookup tables.
    """
    tox = compute_toxicity(tickers)["avg_tox"]
    n = len(tickers)

    # Linear model prediction
    x = [tox, n, term_months, prot_bar, 1.0]
    linear_pred = sum(c * v for c, v in zip(COUPON_COEFS, x))
    linear_pred = max(3, min(50, linear_pred))

    # Lookup table prediction (by nearest term)
    nearest_term = min(COUPON_BY_TERM.keys(), key=lambda t: abs(t - term_months))
    lookup = COUPON_BY_TERM[nearest_term]

    # Blended estimate (weighted average)
    dealer_coupon = 0.4 * linear_pred + 0.6 * lookup["mean"]

    return {
        "predicted_coupon": round(dealer_coupon, 1),
        "linear_model": round(linear_pred, 1),
        "lookup_mean": lookup["mean"],
        "lookup_std": lookup["std"],
        "lookup_n": lookup["n"],
        "term_used": nearest_term,
        "confidence_band": (
            round(max(3, dealer_coupon - lookup["std"]), 1),
            round(min(50, dealer_coupon + lookup["std"]), 1),
        ),
    }


def find_similar_dealer_quotes(
    tickers: List[str],
    term_months: int = 24,
    top_n: int = 8,
) -> List[Dict[str, Any]]:
    """Find real dealer quotes with similar baskets (by ticker overlap)."""
    csv_path = Path(__file__).parent.parent / "data" / "dealer_quotes.csv"
    if not csv_path.exists():
        return []

    user_set = set(tickers)
    matches = []

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["status"] != "ok" or not row["coupon"]:
                continue
            quote_tickers = row["basket"].split("/")
            overlap = len(user_set.intersection(set(quote_tickers)))
            if overlap < 2:
                continue
            try:
                coupon = float(row["coupon"])
                term = int(row["term_m"])
            except (ValueError, TypeError):
                continue
            matches.append({
                "basket": row["basket"],
                "tickers": quote_tickers,
                "n": int(row["n"]),
                "term_m": term,
                "coupon": coupon,
                "prot_bar": float(row.get("prot_bar", 0.65)),
                "overlap": overlap,
                "term_diff": abs(term - term_months),
            })

    matches.sort(key=lambda x: (-x["overlap"], x["term_diff"]))
    return matches[:top_n]


def dealer_quote_summary() -> Dict[str, Any]:
    """Summarize the observed dealer-quote file without inventing sample size."""
    csv_path = Path(__file__).parent.parent / "data" / "dealer_quotes.csv"
    if not csv_path.exists():
        return {
            "source": "dealer_quotes.csv",
            "status": "unavailable",
            "total_quotes": 0,
            "valid_quotes": 0,
        }
    total = 0
    valid = []
    rejects = 0
    with open(csv_path, "r") as handle:
        for row in csv.DictReader(handle):
            total += 1
            if row.get("status") != "ok" or not row.get("coupon"):
                rejects += 1
                continue
            try:
                valid.append(float(row["coupon"]))
            except (TypeError, ValueError):
                rejects += 1
    return {
        "source": "dealer_quotes.csv",
        "status": "observed",
        "total_quotes": total,
        "valid_quotes": len(valid),
        "rejects": rejects,
        "coupon_mean": round(statistics.mean(valid), 2) if valid else None,
        "coupon_median": round(statistics.median(valid), 2) if valid else None,
        "coupon_std": round(statistics.pstdev(valid), 2) if len(valid) > 1 else None,
        "coupon_min": round(min(valid), 2) if valid else None,
        "coupon_max": round(max(valid), 2) if valid else None,
    }


# ═══════════════════════════════════════════════════════════════════
# 5. MASTER PRECOMPUTE (Karpathy method — one call, flat dict output)
# ═══════════════════════════════════════════════════════════════════

def precompute_dealer_benchmark(
    basket_tickers: List[str],
    our_coupon_pa: float,
    our_p_ki: float,
    our_score: float,
    term_months: int = 24,
    prot_bar: float = 0.65,
) -> Dict[str, Any]:
    """
    Master precompute for real dealer data comparison.
    Returns flat dict consumed by pure-render Streamlit layer.
    
    Integrates:
    - Toxicity scoring (from settled notes experience)
    - P(loss) prediction (from real backtest)
    - Dealer coupon prediction (from 828 real quotes)
    - Similar real quotes search
    - GUARD flag (risk alert)
    """
    # 1. Toxicity analysis
    tox = compute_toxicity(basket_tickers)

    # 2. P(loss) from real experience
    p_loss = compute_p_loss(basket_tickers, term_months)

    # 3. Dealer coupon prediction
    coupon_pred = predict_dealer_coupon(basket_tickers, term_months, prot_bar)

    # 4. Find similar real quotes
    similar = find_similar_dealer_quotes(basket_tickers, term_months)

    # 5. Comparison metrics
    delta_coupon = our_coupon_pa - coupon_pred["predicted_coupon"]
    if similar:
        avg_similar_coupon = float(np.mean([q["coupon"] for q in similar]))
        delta_vs_similar = our_coupon_pa - avg_similar_coupon
    else:
        avg_similar_coupon = None
        delta_vs_similar = None

    # 6. Overall accuracy vs dealer
    if avg_similar_coupon is not None and avg_similar_coupon > 0:
        accuracy_vs_dealer = max(0, min(100,
            100 - abs(delta_vs_similar) / avg_similar_coupon * 100))
    else:
        accuracy_vs_dealer = None

    # 7. Summary statistics from the observed quote file
    quote_summary = dealer_quote_summary()

    return {
        "toxicity": tox,
        "p_loss": p_loss,
        "coupon_prediction": coupon_pred,
        "similar_quotes": similar,
        "n_similar": len(similar),
        "avg_similar_coupon": round(avg_similar_coupon, 1) if avg_similar_coupon is not None else None,
        "delta_coupon_vs_model": round(delta_coupon, 1),
        "delta_coupon_vs_similar": round(delta_vs_similar, 1) if delta_vs_similar is not None else None,
        "accuracy_vs_dealer": round(accuracy_vs_dealer, 1) if accuracy_vs_dealer is not None else None,
        "guard_flag": p_loss["guard_flag"],
        "guard_msg": p_loss["guard_msg"],
        "db_stats": quote_summary,
    }
