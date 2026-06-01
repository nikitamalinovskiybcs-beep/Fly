"""
PHOENIX HULK v41 — Conductor (Orchestration Layer).

Role: orchestration only. Heavy computations on external free tiers.
Chain: ClickHouse cache → Railway API → GitHub Actions → local fallback.
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

try:
    import clickhouse_connect
    CH_AVAILABLE = True
except ImportError:
    CH_AVAILABLE = False

# ── Config from env ──
CH_HOST = os.environ.get("CH_HOST", "mz5xp6056a.us-east1.gcp.clickhouse.cloud")
CH_PORT = int(os.environ.get("CH_PORT", "8443"))
CH_USER = os.environ.get("CH_USER", "default")
CH_PASS = os.environ.get("CH_PASS", "nSnvOjKP~2s53")

RAILWAY_API = os.environ.get("RAILWAY_API", "")
GITHUB_API = os.environ.get("GITHUB_API", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def _get_ch_client():
    if not CH_AVAILABLE:
        return None
    try:
        return clickhouse_connect.get_client(
            host=CH_HOST, port=CH_PORT,
            username=CH_USER, password=CH_PASS,
            secure=True,
        )
    except Exception:
        return None


def _init_cache_table():
    client = _get_ch_client()
    if client is None:
        return
    try:
        client.command("""
            CREATE TABLE IF NOT EXISTS phoenix_cache (
                basket_hash String,
                basket Array(String),
                result String,
                created_at DateTime DEFAULT now()
            ) ENGINE = MergeTree ORDER BY (basket_hash, created_at)
        """)
    except Exception:
        pass


def get_cache_key(basket: List[str]) -> str:
    return hashlib.md5(",".join(sorted(basket)).encode()).hexdigest()


def cache_get(basket: List[str]) -> Optional[Dict]:
    client = _get_ch_client()
    if client is None:
        return None
    key = get_cache_key(basket)
    try:
        result = client.query(
            f"SELECT result FROM phoenix_cache WHERE basket_hash = '{key}' "
            f"ORDER BY created_at DESC LIMIT 1"
        )
        if result.result_rows:
            return json.loads(result.result_rows[0][0])
    except Exception:
        pass
    return None


def cache_set(basket: List[str], result: Dict):
    client = _get_ch_client()
    if client is None:
        return
    key = get_cache_key(basket)
    try:
        basket_arr = "[" + ",".join(f"'{t}'" for t in basket) + "]"
        client.command(
            f"INSERT INTO phoenix_cache (basket_hash, basket, result) VALUES "
            f"('{key}', {basket_arr}, '{json.dumps(result)}')"
        )
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
    1. Check ClickHouse cache
    2. If miss → Railway API
    3. If Railway down → GitHub Actions
    4. If all down → return error (caller can use local fallback)
    """
    # 1. Cache
    _init_cache_table()
    cached = cache_get(basket)
    if cached:
        cached["source"] = "clickhouse_cache"
        cached["from_cache"] = True
        return cached

    # 2. Railway
    result = call_railway(basket, n_sims=n_sims)
    if result:
        result["source"] = "railway_api"
        result["from_cache"] = False
        cache_set(basket, result)
        return result

    # 3. GitHub Actions
    result = call_github_actions(basket)
    if result:
        result["source"] = "github_actions"
        result["from_cache"] = False
        cache_set(basket, result)
        return result

    # 4. All external compute unavailable
    return {
        "error": "All external compute unavailable — use local ФЕНИКС MC fallback",
        "basket": basket,
        "source": "none",
        "timestamp": datetime.now().isoformat(),
    }
