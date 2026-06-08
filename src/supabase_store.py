"""
Supabase Store — Persistent storage for Phoenix pipeline (Karpathy method).

Stores:
1. Calibrated model parameters (versioned)
2. Backtest history (timeseries)
3. Pipeline runs (audit log)
4. User preferences / basket history

Free tier: 500MB database, 1GB file storage, 2GB bandwidth.
Graceful fallback: if Supabase unavailable, skip storage (no crash).
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    from supabase import create_client, Client
    SUPABASE_LIB = True
except ImportError:
    SUPABASE_LIB = False

# ── Config from env ──
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_client: Optional[Any] = None


def _get_client() -> Optional[Any]:
    """Lazy singleton Supabase client."""
    global _client
    if _client is not None:
        return _client
    if not SUPABASE_LIB or not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return _client
    except Exception:
        return None


def get_status() -> Dict[str, Any]:
    """Check Supabase connection status."""
    client = _get_client()
    connected = client is not None
    return {
        "available": connected,
        "url_set": bool(SUPABASE_URL),
        "key_set": bool(SUPABASE_KEY),
        "label": "Supabase PostgreSQL" if connected else "Supabase не подключен",
        "description": "Persistent storage для параметров, бэктестов, истории",
    }


# ═══════════════════════════════════════════════════════════════
# Calibrated Parameters
# ═══════════════════════════════════════════════════════════════

def save_calibrated_params(
    params: Dict[str, float],
    metrics: Dict[str, Any],
    basket: Optional[List[str]] = None,
) -> bool:
    """Save calibrated params to Supabase (versioned)."""
    client = _get_client()
    if client is None:
        return False
    try:
        row = {
            "params": json.dumps(params),
            "train_acc": metrics.get("train_acc", 0),
            "test_acc": metrics.get("test_acc", 0),
            "coupon_mae": metrics.get("coupon_mae", 0),
            "basket": ",".join(basket) if basket else "",
            "created_at": datetime.now().isoformat(),
        }
        client.table("calibrated_params").insert(row).execute()
        return True
    except Exception:
        return False


def load_latest_params() -> Optional[Dict[str, float]]:
    """Load most recent calibrated params from Supabase."""
    client = _get_client()
    if client is None:
        return None
    try:
        result = (client.table("calibrated_params")
                  .select("params")
                  .order("created_at", desc=True)
                  .limit(1)
                  .execute())
        if result.data:
            return json.loads(result.data[0]["params"])
    except Exception:
        pass
    return None


def get_params_history(limit: int = 20) -> List[Dict]:
    """Get history of calibrated params (for convergence tracking)."""
    client = _get_client()
    if client is None:
        return []
    try:
        result = (client.table("calibrated_params")
                  .select("train_acc, test_acc, coupon_mae, created_at")
                  .order("created_at", desc=True)
                  .limit(limit)
                  .execute())
        return result.data if result.data else []
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
    client = _get_client()
    if client is None:
        return False
    try:
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
        client.table("backtest_history").insert(row).execute()
        return True
    except Exception:
        return False


def get_backtest_history(limit: int = 30) -> List[Dict]:
    """Get backtest accuracy trend over time."""
    client = _get_client()
    if client is None:
        return []
    try:
        result = (client.table("backtest_history")
                  .select("loss_accuracy, coupon_mae, f1, coupon_r2, created_at")
                  .order("created_at", desc=True)
                  .limit(limit)
                  .execute())
        return result.data if result.data else []
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
    client = _get_client()
    if client is None:
        return False
    try:
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
        client.table("pipeline_runs").insert(row).execute()
        return True
    except Exception:
        return False


def get_pipeline_runs(limit: int = 10) -> List[Dict]:
    """Get recent pipeline runs."""
    client = _get_client()
    if client is None:
        return []
    try:
        result = (client.table("pipeline_runs")
                  .select("*")
                  .order("created_at", desc=True)
                  .limit(limit)
                  .execute())
        return result.data if result.data else []
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
# SQL for table creation (run once in Supabase SQL editor)
# ═══════════════════════════════════════════════════════════════

SETUP_SQL = """
-- Calibrated parameters (versioned)
CREATE TABLE IF NOT EXISTS calibrated_params (
    id SERIAL PRIMARY KEY,
    params JSONB NOT NULL,
    train_acc REAL DEFAULT 0,
    test_acc REAL DEFAULT 0,
    coupon_mae REAL DEFAULT 0,
    basket TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Backtest history
CREATE TABLE IF NOT EXISTS backtest_history (
    id SERIAL PRIMARY KEY,
    loss_accuracy REAL DEFAULT 0,
    coupon_mae REAL DEFAULT 0,
    coupon_mape REAL DEFAULT 0,
    f1 REAL DEFAULT 0,
    precision_val REAL DEFAULT 0,
    recall_val REAL DEFAULT 0,
    coupon_r2 REAL DEFAULT 0,
    basket TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pipeline runs (audit log)
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    basket TEXT NOT NULL,
    accuracy_before REAL DEFAULT 0,
    accuracy_after REAL DEFAULT 0,
    confidence REAL DEFAULT 0,
    coupon_mae REAL DEFAULT 0,
    n_params_changed INT DEFAULT 0,
    early_stopped BOOLEAN DEFAULT FALSE,
    ensemble_size INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""
