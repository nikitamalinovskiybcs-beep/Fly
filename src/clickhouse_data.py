"""Google Drive / local JSON data store for quantum risk statistics.

Replaces ClickHouse Cloud — data stored as JSON in ~/phoenix_data/.
When running in Google Colab, files sync to Google Drive automatically.
Zero external dependencies. Graceful fallback on any error.
"""

import json
import os
from typing import Dict, Optional

# ── Storage path (shared with gdrive_store.py) ──
try:
    from google.colab import drive  # type: ignore
    drive.mount('/content/drive', force_remount=False)
    STORE_PATH = '/content/drive/MyDrive/phoenix_data/'
except Exception:
    STORE_PATH = os.path.join(os.path.expanduser("~"), "phoenix_data")

os.makedirs(STORE_PATH, exist_ok=True)

_QUANTUM_FILE = os.path.join(STORE_PATH, "quantum_risk_stats.json")


def _get_client():
    """Compatibility stub — returns None (no external DB)."""
    return None


def fetch_quantum_risk_stats() -> dict:
    """Fetch quantum risk statistics from local JSON / Google Drive."""
    try:
        if os.path.exists(_QUANTUM_FILE):
            with open(_QUANTUM_FILE, "r") as f:
                data = json.load(f)
            data["source"] = "google_drive"
            return data
    except Exception:
        pass
    return _fallback_data()


def save_quantum_risk_stats(data: dict) -> bool:
    """Save quantum risk statistics to local JSON / Google Drive."""
    try:
        with open(_QUANTUM_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def _fallback_data() -> dict:
    """Hardcoded fallback from last successful query."""
    data = {
        "source": "fallback_cache",
        "table": "quantum_risk_stats",
        "tickers": {
            "AAPL": {"var_95": 86.27, "var_99": 80.06, "mean_return": 168.88,
                     "min_return": 77.83, "max_return": 316.40, "volatility": 64.28,
                     "num_simulations": 10000, "barrier_breach_count": 0,
                     "barrier_breach_pct": 0.0,
                     "percentiles": {"p5": 86.27, "p25": 111.99, "p50": 156.83, "p75": 218.43, "p95": 285.49}},
            "AMZN": {"var_95": 48.29, "var_99": 41.70, "mean_return": 100.40,
                     "min_return": 34.93, "max_return": 249.58, "volatility": 41.41,
                     "num_simulations": 10000, "barrier_breach_count": 2422,
                     "barrier_breach_pct": 24.22,
                     "percentiles": {"p5": 48.29, "p25": 66.18, "p50": 92.30, "p75": 129.96, "p95": 177.91}},
            "GOOGL": {"var_95": 100.07, "var_99": 80.34, "mean_return": 256.19,
                      "min_return": 60.04, "max_return": 790.69, "volatility": 129.74,
                      "num_simulations": 10000, "barrier_breach_count": 2,
                      "barrier_breach_pct": 0.02,
                      "percentiles": {"p5": 100.07, "p25": 153.54, "p50": 226.11, "p75": 333.37, "p95": 512.61}},
            "MSFT": {"var_95": 58.01, "var_99": 49.06, "mean_return": 148.93,
                     "min_return": 42.58, "max_return": 402.89, "volatility": 75.93,
                     "num_simulations": 10000, "barrier_breach_count": 975,
                     "barrier_breach_pct": 9.75,
                     "percentiles": {"p5": 58.01, "p25": 85.42, "p50": 129.74, "p75": 201.39, "p95": 296.62}},
        },
        "worst_of": {"var_95": 47.60, "var_99": 41.70, "mean": 87.44, "barrier_breach_pct": 30.04},
        "total_simulations": 40000,
        "barrier_level": 65.0,
    }
    save_quantum_risk_stats(data)
    return data
