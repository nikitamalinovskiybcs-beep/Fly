"""
PHOENIX HULK v41 — Conductor (Orchestration Layer).

Role: orchestration only. Heavy computations on external free tiers.
Chain: Local JSON cache → Railway API → GitHub Actions → local fallback.
"""

import hashlib
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ── Local / Google Drive cache ──
try:
    from google.colab import drive  # type: ignore
    drive.mount('/content/drive', force_remount=False)
    CACHE_PATH = '/content/drive/MyDrive/phoenix_data/conductor_cache/'
except Exception:
    CACHE_PATH = os.path.join(os.path.expanduser("~"), "phoenix_data", "conductor_cache")

os.makedirs(CACHE_PATH, exist_ok=True)

RAILWAY_API = os.environ.get("RAILWAY_API", "")
GITHUB_API = os.environ.get("GITHUB_API", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def get_cache_key(basket: List[str]) -> str:
    return hashlib.md5(",".join(sorted(basket)).encode()).hexdigest()


def cache_get(basket: List[str]) -> Optional[Dict]:
    """Read from local JSON cache."""
    key = get_cache_key(basket)
    fpath = os.path.join(CACHE_PATH, f"{key}.json")
    try:
        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def cache_set(basket: List[str], result: Dict):
    """Save to local JSON cache."""
    key = get_cache_key(basket)
    fpath = os.path.join(CACHE_PATH, f"{key}.json")
    try:
        with open(fpath, "w") as f:
            json.dump(result, f, indent=2, default=str)
    except Exception:
        pass


def call_railway(basket: List[str], n_sims: int = 50000) -> Optional[Dict]:
    """Primary compute: Railway (free tier)."""
    if not REQUESTS_AVAILABLE or not RAILWAY_API:
        return None
    try:
        resp = requests.post(
            RAILWAY_API,
            json={"basket": basket, "n_sims": n_sims, "model": "v41"},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def call_github_actions(basket: List[str]) -> Optional[Dict]:
    """Fallback compute: GitHub Actions (free tier)."""
    if not REQUESTS_AVAILABLE or not GITHUB_API or not GITHUB_TOKEN:
        return None
    try:
        resp = requests.post(
            GITHUB_API,
            headers={"Authorization": f"token {GITHUB_TOKEN}"},
            json={"ref": "main", "inputs": {"basket": json.dumps(basket)}},
        )
        if resp.status_code == 204:
            time.sleep(10)
            return cache_get(basket)
    except Exception:
        pass
    return None


def analyze(basket: List[str], n_sims: int = 50000) -> Dict:
    """
    Main conductor method:
    1. Check local JSON cache
    2. If miss → Railway API
    3. If Railway down → GitHub Actions
    4. If all down → return error (caller can use local fallback)
    """
    cached = cache_get(basket)
    if cached:
        cached["source"] = "local_cache"
        cached["from_cache"] = True
        return cached

    result = call_railway(basket, n_sims=n_sims)
    if result:
        result["source"] = "railway_api"
        result["from_cache"] = False
        cache_set(basket, result)
        return result

    result = call_github_actions(basket)
    if result:
        result["source"] = "github_actions"
        result["from_cache"] = False
        cache_set(basket, result)
        return result

    return {
        "error": "All external compute unavailable — use local MC fallback",
        "basket": basket,
        "source": "none",
        "timestamp": datetime.now().isoformat(),
    }
