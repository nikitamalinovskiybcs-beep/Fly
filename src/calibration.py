"""
Calibration Engine — 3-Component Pipeline (Karpathy method).

Pipeline: БЭКТЕСТ → КАЛИБРОВКА → ПРОГНОЗ
1. Backtest: measure model accuracy on current data (settled notes + dealer quotes)
2. Calibrate: find multipliers to minimize error vs real market
3. Forecast: calibrated forward predictions targeting ~74% accuracy

All computation external — returns flat dict for Streamlit rendering.
"""

import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional


# ═══════════════════════════════════════════════════════════════════
# 1. БЭКТЕСТ — measure model accuracy on current data
# ═══════════════════════════════════════════════════════════════════

def run_accuracy_backtest(
    settled_notes: List[Tuple],
    dealer_quotes: List[Dict],
    tox_func,
    predict_p_loss_func,
    predict_coupon_func,
) -> Dict[str, Any]:
    """
    Measure model accuracy on ALL available data.
    Returns: accuracy %, error distribution, per-bucket breakdown.
    """
    # P(loss) accuracy on settled notes
    loss_results = []
    for basket_str, term_y, bad in settled_notes:
        tickers = basket_str.split("/")
        tox_info = tox_func(tickers)
        avg_tox = tox_info["avg_tox"]
        pred_p = predict_p_loss_func(avg_tox, term_y, len(tickers))
        predicted_bad = 1 if pred_p > 0.5 else 0
        loss_results.append({
            "basket": basket_str,
            "actual": bad,
            "predicted_p": round(pred_p, 3),
            "predicted_class": predicted_bad,
            "correct": predicted_bad == bad,
            "error": abs(bad - pred_p),
        })

    loss_accuracy = sum(r["correct"] for r in loss_results) / max(1, len(loss_results)) * 100
    loss_errors = [r["error"] for r in loss_results]

    # Coupon accuracy on dealer quotes
    coupon_results = []
    for q in dealer_quotes:
        tickers = q["basket"].split("/")
        tox_info = tox_func(tickers)
        avg_tox = tox_info["avg_tox"]
        pred_cpn = predict_coupon_func(
            avg_tox, q["term_m"], q["n"], q.get("prot_bar", 0.65))
        actual_cpn = q["coupon"]
        error = pred_cpn - actual_cpn
        coupon_results.append({
            "basket": q["basket"],
            "term_m": q["term_m"],
            "actual_coupon": actual_cpn,
            "predicted_coupon": round(pred_cpn, 1),
            "error": round(error, 1),
            "abs_error": round(abs(error), 1),
            "pct_error": round(abs(error) / max(0.1, actual_cpn) * 100, 1),
        })

    coupon_mae = float(np.mean([r["abs_error"] for r in coupon_results])) if coupon_results else 0
    coupon_mape = float(np.mean([r["pct_error"] for r in coupon_results])) if coupon_results else 0

    # Error by bucket (for calibration)
    error_by_term = {}
    for r in coupon_results:
        term = r["term_m"]
        bucket = (term // 12) * 12  # round to nearest year
        if bucket not in error_by_term:
            error_by_term[bucket] = []
        error_by_term[bucket].append(r["error"])

    error_by_tox = {"low": [], "mid": [], "high": []}
    for r in coupon_results:
        tickers = r["basket"].split("/")
        tox_info = tox_func(tickers)
        avg_tox = tox_info["avg_tox"]
        if avg_tox < 0.3:
            error_by_tox["low"].append(r["error"])
        elif avg_tox < 0.5:
            error_by_tox["mid"].append(r["error"])
        else:
            error_by_tox["high"].append(r["error"])

    return {
        "loss_accuracy": round(loss_accuracy, 1),
        "loss_n": len(loss_results),
        "loss_mae": round(float(np.mean(loss_errors)), 3) if loss_errors else 0,
        "coupon_mae": round(coupon_mae, 1),
        "coupon_mape": round(coupon_mape, 1),
        "coupon_n": len(coupon_results),
        "error_by_term": {
            k: {"mean": round(float(np.mean(v)), 1), "std": round(float(np.std(v)), 1), "n": len(v)}
            for k, v in sorted(error_by_term.items())
        },
        "error_by_tox": {
            k: {"mean": round(float(np.mean(v)), 1), "n": len(v)}
            for k, v in error_by_tox.items() if v
        },
        "worst_predictions": sorted(coupon_results, key=lambda x: x["abs_error"], reverse=True)[:5],
        "best_predictions": sorted(coupon_results, key=lambda x: x["abs_error"])[:5],
    }


# ═══════════════════════════════════════════════════════════════════
# 2. КАЛИБРОВКА — find multipliers to reduce model error
# ═══════════════════════════════════════════════════════════════════

def calibrate_model(
    backtest_result: Dict[str, Any],
    current_params: Dict[str, float],
    settled_notes: List[Tuple],
    dealer_quotes: List[Dict],
    tox_func,
    param_bounds: Dict[str, Tuple[float, float]],
    n_iterations: int = 15,
) -> Dict[str, Any]:
    """
    Calibration: find multipliers/corrections that minimize total error.

    Strategy:
    1. Analyze systematic biases from backtest errors
    2. Apply correction multipliers per error bucket
    3. Fine-tune via coordinate descent
    4. Report multipliers found + new expected accuracy
    """
    from src.backtest import PhoenixAGI

    # Analyze systematic biases
    error_by_term = backtest_result.get("error_by_term", {})
    error_by_tox = backtest_result.get("error_by_tox", {})

    # Term multipliers: if we systematically overshoot for long-term, adjust
    term_corrections = {}
    for term, stats in error_by_term.items():
        mean_err = stats["mean"]
        if abs(mean_err) > 1.0:  # significant bias
            term_corrections[term] = round(-mean_err * 0.7, 2)  # partial correction

    # Toxicity multipliers
    tox_corrections = {}
    for bucket, stats in error_by_tox.items():
        mean_err = stats["mean"]
        if abs(mean_err) > 1.5:
            tox_corrections[bucket] = round(-mean_err * 0.6, 2)

    # Fine-tune parameters via coordinate descent
    agi = PhoenixAGI(params=dict(current_params))

    # Split data
    n_test = max(5, int(len(settled_notes) * 0.3))
    test_notes = settled_notes[:n_test]
    train_notes = settled_notes[n_test:]
    n_q_test = max(20, int(len(dealer_quotes) * 0.3))
    test_quotes = dealer_quotes[:n_q_test]
    train_quotes = dealer_quotes[n_q_test:]

    pre_train_loss = agi._total_loss(train_notes, train_quotes, tox_func)
    pre_test_loss = agi._total_loss(test_notes, test_quotes, tox_func)
    pre_train_acc = agi._compute_accuracy(train_notes, tox_func)
    pre_test_acc = agi._compute_accuracy(test_notes, tox_func)

    trainable = [k for k in param_bounds if k != "learning_rate"]
    lr = agi.params.get("learning_rate", 0.05)

    calibration_log = []
    for iteration in range(n_iterations):
        improved_any = False
        for param_name in trainable:
            current_val = agi.params[param_name]
            lo, hi = param_bounds.get(param_name, (current_val - 1, current_val + 1))
            step = lr * abs(current_val) if current_val != 0 else lr * 0.1
            step = max(step, 0.001)

            candidates = [
                max(lo, min(hi, current_val + step)),
                max(lo, min(hi, current_val - step)),
                max(lo, min(hi, current_val + step * 2)),
                max(lo, min(hi, current_val - step * 2)),
            ]

            best_loss = agi._total_loss(train_notes, train_quotes, tox_func)
            best_val = current_val

            for candidate in candidates:
                agi.params[param_name] = candidate
                loss = agi._total_loss(train_notes, train_quotes, tox_func)
                if loss < best_loss:
                    best_loss = loss
                    best_val = candidate
                    improved_any = True

            agi.params[param_name] = best_val

        train_acc = agi._compute_accuracy(train_notes, tox_func)
        test_acc = agi._compute_accuracy(test_notes, tox_func)
        train_loss = agi._total_loss(train_notes, train_quotes, tox_func)
        test_loss = agi._total_loss(test_notes, test_quotes, tox_func)
        coupon_mae = agi._compute_coupon_mae(test_quotes, tox_func)

        calibration_log.append({
            "iteration": iteration + 1,
            "train_acc": round(train_acc, 1),
            "test_acc": round(test_acc, 1),
            "train_loss": round(train_loss, 4),
            "test_loss": round(test_loss, 4),
            "coupon_mae": round(coupon_mae, 1),
            "improved": improved_any,
        })

        if not improved_any:
            break

    post_train_acc = agi._compute_accuracy(train_notes, tox_func)
    post_test_acc = agi._compute_accuracy(test_notes, tox_func)
    post_train_loss = agi._total_loss(train_notes, train_quotes, tox_func)
    post_test_loss = agi._total_loss(test_notes, test_quotes, tox_func)
    post_coupon_mae = agi._compute_coupon_mae(test_quotes, tox_func)

    # Find which params changed the most
    param_deltas = {}
    for k in trainable:
        old_v = current_params.get(k, 0)
        new_v = agi.params.get(k, 0)
        if abs(new_v - old_v) > 0.001:
            param_deltas[k] = {
                "old": round(old_v, 4),
                "new": round(new_v, 4),
                "delta": round(new_v - old_v, 4),
            }

    return {
        "calibrated_params": agi.get_params(),
        "term_corrections": term_corrections,
        "tox_corrections": tox_corrections,
        "param_deltas": param_deltas,
        "n_params_changed": len(param_deltas),
        "before": {
            "train_acc": round(pre_train_acc, 1),
            "test_acc": round(pre_test_acc, 1),
            "train_loss": round(pre_train_loss, 4),
            "test_loss": round(pre_test_loss, 4),
        },
        "after": {
            "train_acc": round(post_train_acc, 1),
            "test_acc": round(post_test_acc, 1),
            "train_loss": round(post_train_loss, 4),
            "test_loss": round(post_test_loss, 4),
            "coupon_mae": round(post_coupon_mae, 1),
        },
        "improvement": {
            "accuracy_delta": round(post_test_acc - pre_test_acc, 1),
            "loss_delta": round(post_test_loss - pre_test_loss, 4),
        },
        "calibration_log": calibration_log,
        "n_iterations": len(calibration_log),
    }


# ═══════════════════════════════════════════════════════════════════
# 3. ПРОГНОЗ — forward prediction with calibrated model
# ═══════════════════════════════════════════════════════════════════

def generate_forecast(
    calibrated_params: Dict[str, float],
    basket_tickers: List[str],
    tox_func,
    p_ki: float,
    avg_vol: float,
    avg_corr: float,
    test_accuracy: float,
    term_months: int = 24,
) -> Dict[str, Any]:
    """
    Forward prediction using calibrated model.
    Returns: predicted outcomes + confidence intervals + probability.
    """
    from src.backtest import PhoenixAGI

    agi = PhoenixAGI(params=dict(calibrated_params))
    tox_info = tox_func(basket_tickers)
    avg_tox = tox_info["avg_tox"]
    n = len(basket_tickers)

    # Base predictions
    pred = agi.predict(
        p_ki=p_ki, avg_vol=avg_vol, avg_corr=avg_corr,
        n_tickers=n, avg_tox=avg_tox,
    )
    pred_coupon = agi.predict_coupon(avg_tox, term_months, n)
    pred_p_loss = agi.predict_p_loss(avg_tox, term_months / 12, n)

    # Confidence based on calibration accuracy
    model_confidence = min(95, max(30, test_accuracy))

    # Monte Carlo confidence intervals (parametric bootstrap)
    n_sims = 500
    scores = []
    coupons = []
    p_losses = []
    for _ in range(n_sims):
        noise_vol = avg_vol * (1 + np.random.normal(0, 0.1))
        noise_corr = max(0, min(1, avg_corr + np.random.normal(0, 0.05)))
        noise_tox = max(0, min(1, avg_tox + np.random.normal(0, 0.05)))
        sim_pred = agi.predict(
            p_ki=p_ki * (1 + np.random.normal(0, 0.15)),
            avg_vol=noise_vol, avg_corr=noise_corr,
            n_tickers=n, avg_tox=noise_tox,
        )
        scores.append(sim_pred["score"])
        coupons.append(sim_pred["coupon_pa"])
        p_losses.append(sim_pred["p_loss"])

    # Scenario analysis
    scenarios = {
        "base": {
            "label": "Базовый",
            "score": pred["score"],
            "coupon": round(pred_coupon, 1),
            "p_loss": round(pred_p_loss * 100, 1),
            "probability": round(model_confidence, 0),
        },
        "optimistic": {
            "label": "Оптимистичный",
            "score": round(float(np.percentile(scores, 75)), 1),
            "coupon": round(float(np.percentile(coupons, 75)), 1),
            "p_loss": round(float(np.percentile(p_losses, 25)), 1),
            "probability": round(model_confidence * 0.65, 0),
        },
        "pessimistic": {
            "label": "Пессимистичный",
            "score": round(float(np.percentile(scores, 25)), 1),
            "coupon": round(float(np.percentile(coupons, 25)), 1),
            "p_loss": round(float(np.percentile(p_losses, 75)), 1),
            "probability": round(model_confidence * 0.65, 0),
        },
    }

    return {
        "prediction": pred,
        "coupon_forecast": round(pred_coupon, 1),
        "p_loss_forecast": round(pred_p_loss * 100, 1),
        "model_confidence": round(model_confidence, 1),
        "confidence_intervals": {
            "score": {
                "p10": round(float(np.percentile(scores, 10)), 1),
                "p50": round(float(np.percentile(scores, 50)), 1),
                "p90": round(float(np.percentile(scores, 90)), 1),
            },
            "coupon": {
                "p10": round(float(np.percentile(coupons, 10)), 1),
                "p50": round(float(np.percentile(coupons, 50)), 1),
                "p90": round(float(np.percentile(coupons, 90)), 1),
            },
            "p_loss": {
                "p10": round(float(np.percentile(p_losses, 10)), 1),
                "p50": round(float(np.percentile(p_losses, 50)), 1),
                "p90": round(float(np.percentile(p_losses, 90)), 1),
            },
        },
        "scenarios": scenarios,
        "n_simulations": n_sims,
    }


# ═══════════════════════════════════════════════════════════════════
# 4. MASTER PIPELINE: backtest → calibrate → forecast
# ═══════════════════════════════════════════════════════════════════

def run_pipeline(
    basket_tickers: List[str],
    current_params: Dict[str, float],
    p_ki: float,
    avg_vol: float,
    avg_corr: float,
    term_months: int = 24,
) -> Dict[str, Any]:
    """
    Run full 3-component pipeline:
    1. БЭКТЕСТ — measure accuracy
    2. КАЛИБРОВКА — optimize multipliers
    3. ПРОГНОЗ — forward prediction

    All external compute — returns flat dict for rendering.
    """
    from src.real_data import SETTLED_NOTES, compute_toxicity
    from src.backtest import PhoenixAGI
    import csv
    from pathlib import Path

    # Load dealer quotes
    csv_path = Path(__file__).parent.parent / "data" / "dealer_quotes.csv"
    dealer_quotes = []
    if csv_path.exists():
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                if row["status"] == "ok" and row["coupon"]:
                    try:
                        dealer_quotes.append({
                            "basket": row["basket"],
                            "n": int(row["n"]),
                            "term_m": int(row["term_m"]),
                            "coupon": float(row["coupon"]),
                            "prot_bar": float(row.get("prot_bar", "0.65")),
                        })
                    except (ValueError, TypeError):
                        pass

    # Create model with current params
    agi = PhoenixAGI(params=dict(current_params))

    # ──── COMPONENT 1: БЭКТЕСТ ────
    backtest_result = run_accuracy_backtest(
        settled_notes=SETTLED_NOTES,
        dealer_quotes=dealer_quotes,
        tox_func=compute_toxicity,
        predict_p_loss_func=agi.predict_p_loss,
        predict_coupon_func=agi.predict_coupon,
    )

    # ──── COMPONENT 2: КАЛИБРОВКА ────
    calibration_result = calibrate_model(
        backtest_result=backtest_result,
        current_params=current_params,
        settled_notes=SETTLED_NOTES,
        dealer_quotes=dealer_quotes,
        tox_func=compute_toxicity,
        param_bounds=PhoenixAGI.PARAM_BOUNDS,
        n_iterations=15,
    )

    # ──── COMPONENT 3: ПРОГНОЗ ────
    forecast_result = generate_forecast(
        calibrated_params=calibration_result["calibrated_params"],
        basket_tickers=basket_tickers,
        tox_func=compute_toxicity,
        p_ki=p_ki,
        avg_vol=avg_vol,
        avg_corr=avg_corr,
        test_accuracy=calibration_result["after"]["test_acc"],
        term_months=term_months,
    )

    # Save calibrated params to ClickHouse
    calibrated_agi = PhoenixAGI(params=calibration_result["calibrated_params"])
    calibrated_agi.train_metrics = {
        "accuracy": calibration_result["after"]["train_acc"],
        "loss": calibration_result["after"]["train_loss"],
    }
    calibrated_agi.test_metrics = {
        "accuracy": calibration_result["after"]["test_acc"],
        "loss": calibration_result["after"]["test_loss"],
    }
    calibrated_agi.save_to_clickhouse()

    return {
        "backtest": backtest_result,
        "calibration": calibration_result,
        "forecast": forecast_result,
        "pipeline_ts": datetime.now().isoformat(),
    }
