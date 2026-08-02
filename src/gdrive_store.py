"""
Google Drive Store — Persistent storage for Phoenix pipeline (Karpathy method).

Stores calibrated params, backtest history, pipeline runs as JSON files.
When running in Google Colab, files sync to Google Drive automatically.
On Streamlit Cloud / local: uses ~/phoenix_data/ directory.

Zero dependencies beyond stdlib. Graceful fallback on any error.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

# ── Storage path ──
# Reuse the same path as phoenix_engine.py for consistency
try:
    from google.colab import drive  # type: ignore
    drive.mount('/content/drive', force_remount=False)
    STORE_PATH = '/content/drive/MyDrive/phoenix_data/'
    GDRIVE_SYNCED = True
except Exception:
    STORE_PATH = os.path.join(os.path.expanduser("~"), "phoenix_data")
    GDRIVE_SYNCED = False

os.makedirs(STORE_PATH, exist_ok=True)

# Individual store files
_PARAMS_FILE = os.path.join(STORE_PATH, "calibrated_params.json")
_BACKTEST_FILE = os.path.join(STORE_PATH, "backtest_history.json")
_PIPELINE_FILE = os.path.join(STORE_PATH, "pipeline_runs.json")


def _load_json(path: str) -> List[Dict]:
    """Load JSON array from file, return [] on error."""
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _save_json(path: str, data: List[Dict]):
    """Save JSON array to file."""
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception:
        pass


def get_status() -> Dict[str, Any]:
    """Check Google Drive store status."""
    writable = False
    try:
        test_path = os.path.join(STORE_PATH, ".test_write")
        with open(test_path, "w") as f:
            f.write("ok")
        os.remove(test_path)
        writable = True
    except Exception:
        pass
    return {
        "available": writable,
        "synced": GDRIVE_SYNCED,
        "path": STORE_PATH,
        "label": "Google Drive" if GDRIVE_SYNCED else "Local Storage",
        "description": "Persistent storage для параметров, бэктестов, истории"
            + (" (синхронизация с Google Drive)" if GDRIVE_SYNCED else " (локальные файлы)"),
    }


# ═══════════════════════════════════════════════════════════════
# Calibrated Parameters
# ═══════════════════════════════════════════════════════════════

def save_calibrated_params(
    params: Dict[str, float],
    metrics: Dict[str, Any],
    basket: Optional[List[str]] = None,
) -> bool:
    """Save calibrated params (versioned, appends to history)."""
    try:
        history = _load_json(_PARAMS_FILE)
        row = {
            "params": params,
            "train_acc": metrics.get("train_acc", 0),
            "test_acc": metrics.get("test_acc", 0),
            "coupon_mae": metrics.get("coupon_mae", 0),
            "basket": ",".join(basket) if basket else "",
            "created_at": datetime.now().isoformat(),
        }
        history.append(row)
        # Keep last 100 entries
        history = history[-100:]
        _save_json(_PARAMS_FILE, history)
        return True
    except Exception:
        return False


def load_latest_params() -> Optional[Dict[str, float]]:
    """Load most recent calibrated params."""
    try:
        history = _load_json(_PARAMS_FILE)
        if history:
            return history[-1].get("params")
    except Exception:
        pass
    return None


def get_params_history(limit: int = 20) -> List[Dict]:
    """Get history of calibrated params (for convergence tracking)."""
    try:
        history = _load_json(_PARAMS_FILE)
        return history[-limit:]
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
# Backtest History
# ═══════════════════════════════════════════════════════════════

def save_backtest_result(
    result: Dict[str, Any],
    basket: Optional[List[str]] = None,
) -> bool:
    """Save backtest result for tracking model accuracy over time."""
    try:
        history = _load_json(_BACKTEST_FILE)
        row = {
            "loss_accuracy": result.get("loss_accuracy", 0),
            "coupon_mae": result.get("coupon_mae", 0),
            "coupon_mape": result.get("coupon_mape", 0),
            "f1": result.get("f1", 0),
            "precision_val": result.get("precision", 0),
            "recall_val": result.get("recall", 0),
            "coupon_r2": result.get("coupon_r2", 0),
            "basket": ",".join(basket) if basket else "",
            "created_at": datetime.now().isoformat(),
        }
        history.append(row)
        history = history[-200:]
        _save_json(_BACKTEST_FILE, history)
        return True
    except Exception:
        return False


def get_backtest_history(limit: int = 30) -> List[Dict]:
    """Get backtest accuracy trend over time."""
    try:
        history = _load_json(_BACKTEST_FILE)
        return history[-limit:]
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
# Pipeline Runs (audit log)
# ═══════════════════════════════════════════════════════════════

def save_pipeline_run(
    pipeline_result: Dict[str, Any],
    basket: List[str],
) -> bool:
    """Log a complete pipeline run for auditing."""
    try:
        history = _load_json(_PIPELINE_FILE)
        bt = pipeline_result.get("backtest", {})
        cal = pipeline_result.get("calibration", {})
        fc = pipeline_result.get("forecast", {})
        row = {
            "basket": ",".join(basket),
            "accuracy_before": cal.get("before", {}).get("test_acc", 0),
            "accuracy_after": cal.get("after", {}).get("test_acc", 0),
            "confidence": fc.get("model_confidence", 0),
            "coupon_mae": bt.get("coupon_mae", 0),
            "n_params_changed": cal.get("n_params_changed", 0),
            "early_stopped": cal.get("early_stopped", False),
            "ensemble_size": fc.get("ensemble_size", 1),
            "created_at": datetime.now().isoformat(),
        }
        history.append(row)
        history = history[-100:]
        _save_json(_PIPELINE_FILE, history)
        return True
    except Exception:
        return False


def get_pipeline_runs(limit: int = 10) -> List[Dict]:
    """Get recent pipeline runs."""
    try:
        history = _load_json(_PIPELINE_FILE)
        return history[-limit:]
    except Exception:
        return []
