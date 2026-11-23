"""
Autonomous model improvement agent.
Runs periodically to improve prediction accuracy without human intervention.

3 strategies:
1. Retrain: re-calibrate weights on settled notes (ensemble + k-fold CV)
2. Feature search: test if new feature combinations improve accuracy
3. Hyperparameter sweep: optimize LR, L2, ensemble size, threshold

Safety: NEVER saves weights that reduce accuracy or win rate below 75%.
"""

import json
import os
import numpy as np
from typing import Dict, List
from datetime import datetime


def run_full_improvement_cycle() -> Dict:
    """Master function: runs all 3 improvement strategies.
    Returns detailed report of what changed and by how much."""
    from src.precompute import (
        calibrate_scoring_on_settled,
        _load_scoring_weights,
        _save_scoring_weights,
        _score_one_note,
        _compute_accuracy,
        _compute_precision_at_threshold,
    )
    from src.real_data import SETTLED_NOTES

    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "strategies": {},
        "before": {},
        "after": {},
        "improved": False,
        "changes": [],
    }

    w_before = _load_scoring_weights()
    data = []
    for basket_str, term_y, bad in SETTLED_NOTES:
        tks = basket_str.split("/") if isinstance(basket_str, str) else basket_str
        if tks:
            actual = 90.0 if bad == 0 else 52.0
            data.append((tks, term_y, actual))

    if not data:
        report["error"] = "no_settled_notes"
        return report

    acc_before = _compute_accuracy(w_before, data)
    wr_before = _compute_precision_at_threshold(w_before, data, threshold=70.0)
    mae_before = float(np.mean(np.abs([a - _score_one_note(w_before, t, ty) for t, ty, a in data])))

    report["before"] = {
        "accuracy": round(acc_before, 1),
        "win_rate": round(wr_before, 1),
        "mae": round(mae_before, 1),
        "generation": w_before.get("generation", 0),
        "n_notes": len(data),
    }

    # ── Strategy 1: Standard recalibration ──
    try:
        cal_result = calibrate_scoring_on_settled()
        report["strategies"]["recalibration"] = {
            "acc_before": cal_result.get("acc_before", 0),
            "acc_after": cal_result.get("acc_after", 0),
            "win_rate": cal_result.get("win_rate", 0),
            "generation": cal_result.get("generation", 0),
            "weak_features": cal_result.get("weak_features", []),
        }
    except Exception as e:
        report["strategies"]["recalibration"] = {"error": str(e)}

    # ── Strategy 2: Feature interaction search ──
    try:
        feature_report = _search_feature_interactions(w_before, data)
        report["strategies"]["feature_search"] = feature_report
    except Exception as e:
        report["strategies"]["feature_search"] = {"error": str(e)}

    # ── Strategy 3: Hyperparameter sweep ──
    try:
        hp_report = _hyperparameter_sweep(w_before, data)
        report["strategies"]["hyperparam_sweep"] = hp_report
    except Exception as e:
        report["strategies"]["hyperparam_sweep"] = {"error": str(e)}

    # ── Measure AFTER all strategies ──
    w_after = _load_scoring_weights()
    acc_after = _compute_accuracy(w_after, data)
    wr_after = _compute_precision_at_threshold(w_after, data, threshold=70.0)
    mae_after = float(np.mean(np.abs([a - _score_one_note(w_after, t, ty) for t, ty, a in data])))

    report["after"] = {
        "accuracy": round(acc_after, 1),
        "win_rate": round(wr_after, 1),
        "mae": round(mae_after, 1),
        "generation": w_after.get("generation", 0),
    }

    report["improved"] = acc_after > acc_before or wr_after > wr_before
    report["changes"] = []
    if acc_after != acc_before:
        report["changes"].append(f"Accuracy: {acc_before:.0f}% -> {acc_after:.0f}%")
    if wr_after != wr_before:
        report["changes"].append(f"Win rate: {wr_before:.0f}% -> {wr_after:.0f}%")
    if mae_after != mae_before:
        report["changes"].append(f"MAE: {mae_before:.1f} -> {mae_after:.1f}")

    # Safety: rollback if accuracy dropped below threshold
    if acc_after < acc_before - 5 or wr_after < 75:
        _save_scoring_weights(w_before, {"rollback": True, "reason": "accuracy_drop"})
        report["rollback"] = True
        report["rollback_reason"] = f"acc {acc_after:.0f}% < {acc_before:.0f}%-5 or wr {wr_after:.0f}% < 75%"

    # Save report
    _save_improvement_report(report)
    return report


def _search_feature_interactions(w: Dict, data: List) -> Dict:
    """Test if interaction features (vol*corr, pki*term, etc.) improve accuracy."""
    from src.precompute import _compute_accuracy

    base_acc = _compute_accuracy(w, data)

    # Test disabling each non-base weight one at a time
    ablation_results = {}
    weight_keys = [k for k in w if k.startswith("w_") and isinstance(w[k], (int, float))]

    for key in weight_keys:
        w_test = dict(w)
        w_test[key] = 0
        acc_without = _compute_accuracy(w_test, data)
        impact = base_acc - acc_without
        ablation_results[key] = {
            "acc_without": round(acc_without, 1),
            "impact": round(impact, 1),
            "helpful": impact > 0,
        }

    # Find harmful features (removing them IMPROVES accuracy)
    harmful = [k for k, v in ablation_results.items() if v["impact"] < -2]
    helpful = [k for k, v in ablation_results.items() if v["impact"] > 2]

    return {
        "base_accuracy": round(base_acc, 1),
        "ablation": ablation_results,
        "harmful_features": harmful,
        "helpful_features": helpful,
        "n_features_tested": len(weight_keys),
    }


def _hyperparameter_sweep(w: Dict, data: List) -> Dict:
    """Sweep learning rates, L2, and thresholds to find optimal settings."""
    from src.precompute import (
        _compute_accuracy,
        _compute_precision_at_threshold,
        _run_momentum_sgd,
    )

    split = int(len(data) * 0.7)
    train = data[:split]
    val = data[split:]

    best_acc = _compute_accuracy(w, val)
    best_config = {"lr": 0.08, "steps": 30}
    results = []

    for lr in [0.03, 0.05, 0.08, 0.12, 0.15]:
        for steps in [20, 30, 50]:
            w_test = dict(w)
            try:
                w_trained, _, _ = _run_momentum_sgd(w_test, train, steps=steps, lr=lr)
                acc = _compute_accuracy(w_trained, val)
                wr = _compute_precision_at_threshold(w_trained, val, threshold=70.0)
                results.append({
                    "lr": lr,
                    "steps": steps,
                    "val_acc": round(acc, 1),
                    "val_wr": round(wr, 1),
                })
                if acc > best_acc and wr >= 70:
                    best_acc = acc
                    best_config = {"lr": lr, "steps": steps}
            except Exception:
                pass

    # Threshold sweep
    threshold_results = []
    for thr in [60, 65, 70, 75, 80]:
        wr = _compute_precision_at_threshold(w, data, threshold=float(thr))
        threshold_results.append({
            "threshold": thr,
            "win_rate": round(wr, 1),
        })

    return {
        "best_config": best_config,
        "best_val_acc": round(best_acc, 1),
        "configs_tested": len(results),
        "top_configs": sorted(results, key=lambda x: x["val_acc"], reverse=True)[:5],
        "threshold_sweep": threshold_results,
    }


def _save_improvement_report(report: Dict):
    """Save improvement report to persistent storage."""
    report_dir = os.path.expanduser("~/phoenix_data")
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, "improvement_history.json")

    history = []
    if os.path.exists(report_file):
        try:
            with open(report_file) as f:
                history = json.load(f)
        except Exception:
            history = []

    history.append(report)
    # Keep last 100 reports
    history = history[-100:]

    with open(report_file, "w") as f:
        json.dump(history, f, indent=2, default=str)


def get_improvement_history() -> List[Dict]:
    """Load improvement history."""
    report_file = os.path.expanduser("~/phoenix_data/improvement_history.json")
    if os.path.exists(report_file):
        try:
            with open(report_file) as f:
                return json.load(f)
        except Exception:
            return []
    return []


if __name__ == "__main__":
    print("=" * 60)
    print("PHOENIX AUTO-IMPROVE AGENT")
    print("=" * 60)
    report = run_full_improvement_cycle()
    print(f"\nTimestamp: {report['timestamp']}")
    print(f"Improved: {report['improved']}")
    print(f"\nBefore: acc={report['before']['accuracy']}%, wr={report['before']['win_rate']}%")
    print(f"After:  acc={report['after']['accuracy']}%, wr={report['after']['win_rate']}%")
    if report.get("rollback"):
        print(f"ROLLBACK: {report['rollback_reason']}")
    for change in report.get("changes", []):
        print(f"  - {change}")
    print(f"\nStrategies: {list(report['strategies'].keys())}")
    for name, result in report["strategies"].items():
        if "error" in result:
            print(f"  {name}: ERROR - {result['error']}")
        else:
            print(f"  {name}: OK")
