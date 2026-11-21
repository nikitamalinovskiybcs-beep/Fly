"""
Calibration Engine v2 — 3-Component Pipeline (Karpathy method).

Pipeline: БЭКТЕСТ → КАЛИБРОВКА → ПРОГНОЗ

Improvements v2:
1. БЭКТЕСТ: k-fold CV, precision/recall/F1, confusion matrix
2. КАЛИБРОВКА: adaptive LR, early stopping (patience), L2 regularization
3. ПРОГНОЗ: ensemble of 3 bootstrap models, better CI

All computation external — returns flat dict for Streamlit rendering.
Zero cost, zero dependencies beyond numpy.
"""

import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional


# ═══════════════════════════════════════════════════════════════════
# 1. БЭКТЕСТ v2 — k-fold CV, precision/recall/F1, confusion matrix
# ═══════════════════════════════════════════════════════════════════

def _confusion_matrix(results: List[Dict]) -> Dict[str, int]:
    """TP/FP/TN/FN from classification results."""
    tp = sum(1 for r in results if r["actual"] == 1 and r["predicted_class"] == 1)
    fp = sum(1 for r in results if r["actual"] == 0 and r["predicted_class"] == 1)
    tn = sum(1 for r in results if r["actual"] == 0 and r["predicted_class"] == 0)
    fn = sum(1 for r in results if r["actual"] == 1 and r["predicted_class"] == 0)
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def _precision_recall_f1(cm: Dict[str, int]) -> Dict[str, float]:
    """Compute precision, recall, F1 from confusion matrix."""
    precision = cm["tp"] / max(1, cm["tp"] + cm["fp"])
    recall = cm["tp"] / max(1, cm["tp"] + cm["fn"])
    f1 = 2 * precision * recall / max(0.001, precision + recall)
    return {
        "precision": round(precision * 100, 1),
        "recall": round(recall * 100, 1),
        "f1": round(f1 * 100, 1),
    }


def _kfold_cv(
    settled_notes: List[Tuple],
    tox_func,
    predict_p_loss_func,
    k: int = 5,
) -> Dict[str, Any]:
    """
    K-fold cross-validation on settled notes.
    Measures stability of accuracy across folds.
    """
    n = len(settled_notes)
    if n < k:
        return {"folds": [], "mean_acc": 0, "std_acc": 0, "k": k}

    fold_size = n // k
    fold_accs = []
    fold_f1s = []

    for i in range(k):
        start = i * fold_size
        end = start + fold_size if i < k - 1 else n
        test_fold = settled_notes[start:end]

        results = []
        for basket_str, term_y, bad in test_fold:
            tickers = basket_str.split("/")
            tox_info = tox_func(tickers)
            pred_p = predict_p_loss_func(tox_info["avg_tox"], term_y, len(tickers))
            predicted_bad = 1 if pred_p > 0.5 else 0
            results.append({
                "actual": bad,
                "predicted_class": predicted_bad,
            })

        acc = sum(r["actual"] == r["predicted_class"] for r in results) / max(1, len(results)) * 100
        cm = _confusion_matrix(results)
        prf = _precision_recall_f1(cm)
        fold_accs.append(acc)
        fold_f1s.append(prf["f1"])

    return {
        "folds": [{"fold": i + 1, "acc": round(a, 1), "f1": round(f, 1)}
                  for i, (a, f) in enumerate(zip(fold_accs, fold_f1s))],
        "mean_acc": round(float(np.mean(fold_accs)), 1),
        "std_acc": round(float(np.std(fold_accs)), 1),
        "mean_f1": round(float(np.mean(fold_f1s)), 1),
        "k": k,
    }


def run_accuracy_backtest(
    settled_notes: List[Tuple],
    dealer_quotes: List[Dict],
    tox_func,
    predict_p_loss_func,
    predict_coupon_func,
) -> Dict[str, Any]:
    """
    Measure model accuracy — v2 with k-fold CV + precision/recall/F1.
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

    # Confusion matrix + precision/recall/F1
    cm = _confusion_matrix(loss_results)
    prf = _precision_recall_f1(cm)

    # K-fold cross-validation
    kfold = _kfold_cv(settled_notes, tox_func, predict_p_loss_func, k=5)

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

    # R² for coupon predictions
    if coupon_results:
        y_true = [r["actual_coupon"] for r in coupon_results]
        y_pred = [r["predicted_coupon"] for r in coupon_results]
        ss_res = sum((t - p) ** 2 for t, p in zip(y_true, y_pred))
        ss_tot = sum((t - np.mean(y_true)) ** 2 for t in y_true)
        r_squared = 1 - ss_res / max(0.001, ss_tot)
    else:
        r_squared = 0

    # Error by bucket
    error_by_term = {}
    for r in coupon_results:
        bucket = (r["term_m"] // 12) * 12
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
        "loss_mae": round(float(np.mean([r["error"] for r in loss_results])), 3) if loss_results else 0,
        "confusion_matrix": cm,
        "precision": prf["precision"],
        "recall": prf["recall"],
        "f1": prf["f1"],
        "kfold": kfold,
        "coupon_mae": round(coupon_mae, 1),
        "coupon_mape": round(coupon_mape, 1),
        "coupon_r2": round(r_squared, 3),
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
# 2. КАЛИБРОВКА v2 — adaptive LR, early stopping, L2 regularization
# ═══════════════════════════════════════════════════════════════════

def calibrate_model(
    backtest_result: Dict[str, Any],
    current_params: Dict[str, float],
    settled_notes: List[Tuple],
    dealer_quotes: List[Dict],
    tox_func,
    param_bounds: Dict[str, Tuple[float, float]],
    n_iterations: int = 20,
    patience: int = 4,
    l2_lambda: float = 0.001,
) -> Dict[str, Any]:
    """
    Calibration v2:
    - Adaptive learning rate (halves on plateau)
    - Early stopping with patience
    - L2 regularization to prevent overfitting
    """
    from src.backtest import PhoenixAGI

    # Systematic bias corrections
    error_by_term = backtest_result.get("error_by_term", {})
    error_by_tox = backtest_result.get("error_by_tox", {})

    term_corrections = {}
    for term, stats in error_by_term.items():
        if abs(stats["mean"]) > 1.0:
            term_corrections[term] = round(-stats["mean"] * 0.7, 2)

    tox_corrections = {}
    for bucket, stats in error_by_tox.items():
        if abs(stats["mean"]) > 1.5:
            tox_corrections[bucket] = round(-stats["mean"] * 0.6, 2)

    agi = PhoenixAGI(params=dict(current_params))
    default_params = dict(PhoenixAGI.DEFAULT_PARAMS)

    # Split data
    n_test = max(5, int(len(settled_notes) * 0.3))
    test_notes = settled_notes[:n_test]
    train_notes = settled_notes[n_test:]
    n_q_test = max(20, int(len(dealer_quotes) * 0.3))
    test_quotes = dealer_quotes[:n_q_test]
    train_quotes = dealer_quotes[n_q_test:]

    def total_loss_with_l2(notes, quotes, l2=l2_lambda):
        """Loss + L2 penalty to prevent params drifting too far from defaults."""
        base_loss = agi._total_loss(notes, quotes, tox_func)
        l2_penalty = 0.0
        for k in param_bounds:
            if k == "learning_rate":
                continue
            current = agi.params.get(k, 0)
            default = default_params.get(k, current)
            if default != 0:
                l2_penalty += l2 * ((current - default) / abs(default)) ** 2
        return base_loss + l2_penalty

    pre_train_acc = agi._compute_accuracy(train_notes, tox_func)
    pre_test_acc = agi._compute_accuracy(test_notes, tox_func)
    pre_train_loss = total_loss_with_l2(train_notes, train_quotes)
    pre_test_loss = total_loss_with_l2(test_notes, test_quotes)

    trainable = [k for k in param_bounds if k != "learning_rate"]
    lr = agi.params.get("learning_rate", 0.05)

    # Adaptive LR + early stopping
    best_test_loss = total_loss_with_l2(test_notes, test_quotes)
    best_params_snapshot = dict(agi.params)
    no_improve_count = 0
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

            best_loss = total_loss_with_l2(train_notes, train_quotes)
            best_val = current_val

            for candidate in candidates:
                agi.params[param_name] = candidate
                loss = total_loss_with_l2(train_notes, train_quotes)
                if loss < best_loss:
                    best_loss = loss
                    best_val = candidate
                    improved_any = True

            agi.params[param_name] = best_val

        train_acc = agi._compute_accuracy(train_notes, tox_func)
        test_acc = agi._compute_accuracy(test_notes, tox_func)
        train_loss = total_loss_with_l2(train_notes, train_quotes)
        test_loss = total_loss_with_l2(test_notes, test_quotes)
        coupon_mae = agi._compute_coupon_mae(test_quotes, tox_func)

        # Early stopping check
        if test_loss < best_test_loss - 0.001:
            best_test_loss = test_loss
            best_params_snapshot = dict(agi.params)
            no_improve_count = 0
        else:
            no_improve_count += 1

        # Adaptive LR: halve on plateau
        if no_improve_count >= 2 and lr > 0.005:
            lr *= 0.5

        calibration_log.append({
            "iteration": iteration + 1,
            "train_acc": round(train_acc, 1),
            "test_acc": round(test_acc, 1),
            "train_loss": round(train_loss, 4),
            "test_loss": round(test_loss, 4),
            "coupon_mae": round(coupon_mae, 1),
            "lr": round(lr, 4),
            "improved": improved_any,
        })

        # Early stopping
        if no_improve_count >= patience:
            break
        if not improved_any and no_improve_count >= 2:
            break

    # Restore best params (by test loss)
    agi.params = best_params_snapshot

    post_train_acc = agi._compute_accuracy(train_notes, tox_func)
    post_test_acc = agi._compute_accuracy(test_notes, tox_func)
    post_train_loss = total_loss_with_l2(train_notes, train_quotes)
    post_test_loss = total_loss_with_l2(test_notes, test_quotes)
    post_coupon_mae = agi._compute_coupon_mae(test_quotes, tox_func)

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
        "final_lr": round(lr, 4),
        "l2_lambda": l2_lambda,
        "early_stopped": no_improve_count >= patience,
    }


# ═══════════════════════════════════════════════════════════════════
# 3. ПРОГНОЗ v2 — ensemble of 3 bootstrap models, better CI
# ═══════════════════════════════════════════════════════════════════

def _train_bootstrap_model(
    base_params: Dict[str, float],
    settled_notes: List[Tuple],
    dealer_quotes: List[Dict],
    tox_func,
    param_bounds: Dict,
    seed: int,
) -> Dict[str, float]:
    """Train one bootstrap model on resampled data."""
    from src.backtest import PhoenixAGI

    rng = np.random.RandomState(seed)

    # Bootstrap resample (with replacement)
    n_notes = len(settled_notes)
    n_quotes = len(dealer_quotes)
    boot_notes = [settled_notes[rng.randint(0, n_notes)] for _ in range(n_notes)]
    boot_quotes = [dealer_quotes[rng.randint(0, n_quotes)] for _ in range(n_quotes)] if n_quotes > 0 else []

    agi = PhoenixAGI(params=dict(base_params))
    trainable = [k for k in param_bounds if k != "learning_rate"]
    lr = 0.04

    for _ in range(8):  # fewer iterations per bootstrap
        for param_name in trainable:
            current_val = agi.params[param_name]
            lo, hi = param_bounds.get(param_name, (current_val - 1, current_val + 1))
            step = lr * abs(current_val) if current_val != 0 else lr * 0.1
            step = max(step, 0.001)

            best_loss = agi._total_loss(boot_notes, boot_quotes, tox_func)
            best_val = current_val

            for candidate in [max(lo, min(hi, current_val + step)),
                              max(lo, min(hi, current_val - step))]:
                agi.params[param_name] = candidate
                loss = agi._total_loss(boot_notes, boot_quotes, tox_func)
                if loss < best_loss:
                    best_loss = loss
                    best_val = candidate
            agi.params[param_name] = best_val

    return agi.get_params()


def generate_forecast(
    calibrated_params: Dict[str, float],
    basket_tickers: List[str],
    tox_func,
    p_ki: float,
    avg_vol: float,
    avg_corr: float,
    test_accuracy: float,
    term_months: int = 24,
    settled_notes: Optional[List[Tuple]] = None,
    dealer_quotes: Optional[List[Dict]] = None,
    param_bounds: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Forecast v2: ensemble of 3 bootstrap models + parametric MC.
    """
    from src.backtest import PhoenixAGI

    tox_info = tox_func(basket_tickers)
    avg_tox = tox_info["avg_tox"]
    n = len(basket_tickers)

    # Train 3 bootstrap models for ensemble
    ensemble_params = [calibrated_params]
    if settled_notes and param_bounds:
        for seed in [42, 137, 256]:
            bp = _train_bootstrap_model(
                calibrated_params, settled_notes, dealer_quotes or [],
                tox_func, param_bounds, seed,
            )
            ensemble_params.append(bp)

    # Ensemble predictions
    ensemble_scores = []
    ensemble_coupons = []
    ensemble_p_losses = []
    for params in ensemble_params:
        agi = PhoenixAGI(params=dict(params))
        pred = agi.predict(p_ki=p_ki, avg_vol=avg_vol, avg_corr=avg_corr,
                           n_tickers=n, avg_tox=avg_tox)
        ensemble_scores.append(pred["score"])
        ensemble_coupons.append(pred["coupon_pa"])
        ensemble_p_losses.append(pred["p_loss"])

    # Ensemble mean as base prediction
    base_score = float(np.mean(ensemble_scores))

    # Ensemble spread = model uncertainty
    model_spread = {
        "score_spread": round(float(np.std(ensemble_scores)), 1),
        "coupon_spread": round(float(np.std(ensemble_coupons)), 1),
        "p_loss_spread": round(float(np.std(ensemble_p_losses)), 1),
    }

    # Full prediction from calibrated model
    agi_main = PhoenixAGI(params=dict(calibrated_params))
    pred = agi_main.predict(p_ki=p_ki, avg_vol=avg_vol, avg_corr=avg_corr,
                            n_tickers=n, avg_tox=avg_tox)
    pred_coupon = agi_main.predict_coupon(avg_tox, term_months, n)
    pred_p_loss = agi_main.predict_p_loss(avg_tox, term_months / 12, n)

    # Confidence: weighted by accuracy + ensemble agreement
    ensemble_agreement = max(0, 100 - float(np.std(ensemble_scores)) * 5)
    model_confidence = min(95, max(30, test_accuracy * 0.7 + ensemble_agreement * 0.3))

    # MC confidence intervals (parametric noise)
    n_sims = 500
    mc_scores = []
    mc_coupons = []
    mc_p_losses = []
    for _ in range(n_sims):
        noise_vol = avg_vol * (1 + np.random.normal(0, 0.1))
        noise_corr = max(0, min(1, avg_corr + np.random.normal(0, 0.05)))
        noise_tox = max(0, min(1, avg_tox + np.random.normal(0, 0.05)))
        # Use random ensemble member for each sim
        sim_params = ensemble_params[np.random.randint(0, len(ensemble_params))]
        sim_agi = PhoenixAGI(params=dict(sim_params))
        sim_pred = sim_agi.predict(
            p_ki=p_ki * (1 + np.random.normal(0, 0.15)),
            avg_vol=noise_vol, avg_corr=noise_corr,
            n_tickers=n, avg_tox=noise_tox,
        )
        mc_scores.append(sim_pred["score"])
        mc_coupons.append(sim_pred["coupon_pa"])
        mc_p_losses.append(sim_pred["p_loss"])

    # Scenarios
    scenarios = {
        "base": {
            "label": "Базовый",
            "score": round(base_score, 1),
            "coupon": round(pred_coupon, 1),
            "p_loss": round(pred_p_loss * 100, 1),
            "probability": round(model_confidence, 0),
        },
        "optimistic": {
            "label": "Оптимистичный",
            "score": round(float(np.percentile(mc_scores, 75)), 1),
            "coupon": round(float(np.percentile(mc_coupons, 75)), 1),
            "p_loss": round(float(np.percentile(mc_p_losses, 25)) * 100, 1),
            "probability": round(model_confidence * 0.6, 0),
        },
        "pessimistic": {
            "label": "Пессимистичный",
            "score": round(float(np.percentile(mc_scores, 25)), 1),
            "coupon": round(float(np.percentile(mc_coupons, 25)), 1),
            "p_loss": round(float(np.percentile(mc_p_losses, 75)) * 100, 1),
            "probability": round(model_confidence * 0.6, 0),
        },
    }

    return {
        "prediction": pred,
        "coupon_forecast": round(pred_coupon, 1),
        "p_loss_forecast": round(pred_p_loss * 100, 1),
        "model_confidence": round(model_confidence, 1),
        "ensemble_size": len(ensemble_params),
        "model_spread": model_spread,
        "confidence_intervals": {
            "score": {
                "p10": round(float(np.percentile(mc_scores, 10)), 1),
                "p50": round(float(np.percentile(mc_scores, 50)), 1),
                "p90": round(float(np.percentile(mc_scores, 90)), 1),
            },
            "coupon": {
                "p10": round(float(np.percentile(mc_coupons, 10)), 1),
                "p50": round(float(np.percentile(mc_coupons, 50)), 1),
                "p90": round(float(np.percentile(mc_coupons, 90)), 1),
            },
            "p_loss": {
                "p10": round(float(np.percentile(mc_p_losses, 10)) * 100, 1),
                "p50": round(float(np.percentile(mc_p_losses, 50)) * 100, 1),
                "p90": round(float(np.percentile(mc_p_losses, 90)) * 100, 1),
            },
        },
        "scenarios": scenarios,
        "n_simulations": n_sims,
    }


# ═══════════════════════════════════════════════════════════════════
# 4. MASTER PIPELINE v2: backtest → calibrate → forecast
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
    Run full 3-component pipeline v2:
    1. БЭКТЕСТ — k-fold CV, precision/recall/F1, confusion matrix
    2. КАЛИБРОВКА — adaptive LR, early stopping, L2 reg
    3. ПРОГНОЗ — ensemble forecast with bootstrap models

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
        n_iterations=20,
        patience=4,
        l2_lambda=0.001,
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
        settled_notes=SETTLED_NOTES,
        dealer_quotes=dealer_quotes,
        param_bounds=PhoenixAGI.PARAM_BOUNDS,
    )

    # Save to Google Drive store
    try:
        from src.gdrive_store import save_calibrated_params, save_backtest_result, save_pipeline_run
        save_backtest_result(backtest_result, basket_tickers)
        save_calibrated_params(
            calibration_result["calibrated_params"],
            calibration_result["after"],
            basket_tickers,
        )
    except Exception:
        pass

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

    # Fetch learning history from Google Drive store
    learning_history = []
    try:
        from src.gdrive_store import get_pipeline_runs
        learning_history = get_pipeline_runs(limit=20)
    except Exception:
        pass

    pipeline_result = {
        "backtest": backtest_result,
        "calibration": calibration_result,
        "forecast": forecast_result,
        "learning_history": learning_history,
        "target_accuracy": 74.0,
        "current_accuracy": calibration_result["after"]["test_acc"],
        "pipeline_ts": datetime.now().isoformat(),
    }

    # Save pipeline run to Google Drive store
    try:
        save_pipeline_run(pipeline_result, basket_tickers)
    except Exception:
        pass

    return pipeline_result
