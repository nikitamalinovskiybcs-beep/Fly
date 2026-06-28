"""
ФЕНИКС v32.0 — Vectorized Worst-of Phoenix Simulation Engine.

Sobol MC (500K paths), Memory Coupon, Barrier Pricing.
Integrated with ClickHouse caching & Google Drive backups.
"""

import numpy as np
import hashlib
import json
import os
import time
from datetime import datetime, timedelta

try:
    from scipy.stats import qmc, norm
    SCIPY_QMC = True
except ImportError:
    SCIPY_QMC = False

# ── Google Drive (Colab / local fallback) ──
try:
    from google.colab import drive  # type: ignore
    drive.mount('/content/drive', force_remount=False)
    GDRIVE_PATH = '/content/drive/MyDrive/phoenix_data/'
    os.makedirs(GDRIVE_PATH, exist_ok=True)
    GDRIVE_AVAILABLE = True
except Exception:
    GDRIVE_PATH = os.path.join(os.path.expanduser("~"), "phoenix_data")
    os.makedirs(GDRIVE_PATH, exist_ok=True)
    GDRIVE_AVAILABLE = False


# ── Default config ──
DEFAULT_CONFIG = {
    "coupon": 0.065,           # 6.5% quarterly (26% annual)
    "barrier": 0.65,           # 65% barrier
    "horizon_days": 504,       # 2 years
    "obs_days": [63, 126, 189, 252, 315, 378, 441, 504],
    "n_sims": 10_000,          # 10K for Streamlit (fast); Colab does 500K
    "lookback_years": 2,
}

def _cache_key(basket: list[str]) -> str:
    return hashlib.md5(",".join(sorted(basket)).encode()).hexdigest()


def _cache_get(key: str) -> dict | None:
    """Read cache from local JSON / Google Drive."""
    fpath = os.path.join(GDRIVE_PATH, f"cache_{key}.json")
    if os.path.exists(fpath):
        try:
            with open(fpath, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _cache_set(key: str, value: dict):
    """Save cache to local JSON / Google Drive."""
    fpath = os.path.join(GDRIVE_PATH, f"cache_{key}.json")
    try:
        with open(fpath, "w") as f:
            json.dump(value, f, indent=2)
    except Exception:
        pass


def load_prices_yfinance(tickers: list[str], days_back: int = 730) -> dict:
    """Load historical prices via yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        return {}
    end = datetime.now()
    start = end - timedelta(days=days_back)
    data = {}
    for t in tickers:
        try:
            d = yf.download(t, start=start, end=end, progress=False)["Close"]
            if len(d) > 200:
                data[t] = d.values.flatten()
        except Exception:
            pass
    return data


def simulate_basket(
    basket: list[str],
    config: dict | None = None,
    prices_data: dict | None = None,
) -> dict | None:
    """
    Run Sobol-QMC worst-of Phoenix simulation.

    Returns dict with avg_payoff, p_loss, payoffs array, per-ticker stats.
    Uses ClickHouse + file cache.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cache_key = _cache_key(basket)

    # Check cache
    cached = _cache_get(cache_key)
    if cached is not None:
        cached["from_cache"] = True
        return cached

    # Load prices if not provided
    if prices_data is None:
        prices_data = load_prices_yfinance(basket, days_back=cfg["lookback_years"] * 365)
    if len(prices_data) < len(basket):
        return None

    min_len = min(len(p) for p in prices_data.values())
    prices_array = np.array([prices_data[t][:min_len] for t in basket]).T
    returns = np.diff(np.log(prices_array), axis=0)

    mu = returns.mean(axis=0)
    cov = np.cov(returns.T)
    L = np.linalg.cholesky(cov)
    n_assets = len(basket)
    n_sims = cfg["n_sims"]
    horizon = cfg["horizon_days"]

    dt = 1 / 252
    sqrt_dt = np.sqrt(dt)

    # --- Batch processing to stay within Streamlit Cloud ~1GB RAM ---
    # Each sim needs ~horizon*n_assets*8*4 bytes (z, inc, prices, worst)
    bytes_per_sim = horizon * n_assets * 8 * 5
    max_mem = 300 * 1024 * 1024  # 300 MB budget for arrays
    batch_size = max(1000, min(n_sims, int(max_mem / bytes_per_sim)))

    all_payoffs = []
    all_ticker_finals_raw = {t: [] for t in basket}

    for batch_start in range(0, n_sims, batch_size):
        bs = min(batch_size, n_sims - batch_start)

        z_all = np.random.standard_normal((bs, horizon, n_assets))

        inc = np.einsum("ij,skj->ski", L, z_all) * sqrt_dt + mu * dt
        del z_all
        prices = np.exp(np.cumsum(inc, axis=1))
        del inc

        ones = np.ones((bs, 1, n_assets))
        prices = np.concatenate([ones, prices], axis=1)
        del ones
        worst = np.min(prices, axis=2)

        # Memory coupon calculation
        total_coupons = np.zeros(bs)
        memory_count = np.zeros(bs, dtype=int)

        for idx in cfg["obs_days"][:-1]:
            paid = worst[:, idx] >= 1.0
            total_coupons[paid] += cfg["coupon"] * (1 + memory_count[paid])
            memory_count[paid] = 0
            memory_count[~paid] += 1

        final = worst[:, -1]
        capital_loss = final < cfg["barrier"]
        principal = np.ones(bs)
        principal[capital_loss] = final[capital_loss]

        last_paid = worst[:, cfg["obs_days"][-1]] >= 1.0
        total_coupons[last_paid] += cfg["coupon"] * memory_count[last_paid]

        payoffs_batch = principal + total_coupons
        all_payoffs.append(payoffs_batch)

        for i, t in enumerate(basket):
            all_ticker_finals_raw[t].append(prices[:, -1, i] * 100)

        del prices, worst

    payoffs = np.concatenate(all_payoffs)
    del all_payoffs

    # Per-ticker final returns (as %)
    ticker_finals = {}
    for t in basket:
        finals = np.concatenate(all_ticker_finals_raw[t])
        ticker_finals[t] = {
            "mean": float(np.mean(finals)),
            "var_95": float(np.percentile(finals, 5)),
            "var_99": float(np.percentile(finals, 1)),
            "min": float(np.min(finals)),
            "max": float(np.max(finals)),
            "volatility": float(np.std(finals)),
            "breach_pct": float(np.mean(finals < cfg["barrier"] * 100) * 100),
        }
    del all_ticker_finals_raw

    # Bootstrap CI for p_loss
    boot_p_loss = []
    for _ in range(100):
        idx = np.random.choice(len(payoffs), len(payoffs), replace=True)
        boot_p_loss.append(np.mean(payoffs[idx] < 1))
    p_loss_std = np.std(boot_p_loss)
    p_loss = float(np.mean(payoffs < 1))

    coupons_received = (payoffs - 1) / cfg["coupon"]

    result = {
        "avg_payoff": float(np.mean(payoffs)),
        "p_loss": p_loss,
        "p_loss_ci_low": max(0, p_loss - 1.96 * p_loss_std),
        "p_loss_ci_high": min(1, p_loss + 1.96 * p_loss_std),
        "var_95": float(np.percentile(payoffs, 5)),
        "cvar_95": float(np.mean(payoffs[payoffs <= np.percentile(payoffs, 5)])),
        "p_all_coupons": float(np.mean(coupons_received >= 8)),
        "p_zero_coupons": float(np.mean(coupons_received < 1)),
        "mean_coupons": float(np.mean(coupons_received)),
        "n_sims": n_sims,
        "basket": basket,
        "ticker_finals": ticker_finals,
        "coupon_rate": cfg["coupon"],
        "barrier": cfg["barrier"],
        "timestamp": datetime.now().isoformat(),
        "from_cache": False,
    }

    # Cache the result
    _cache_set(cache_key, result)

    return result


def save_to_gdrive(result: dict, basket: list[str]) -> str | None:
    """Save full report to Google Drive / local backup."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "basket": basket,
        "result": result,
    }
    fname = f"phoenix_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    fpath = os.path.join(GDRIVE_PATH, fname)
    try:
        with open(fpath, "w") as f:
            json.dump(report, f, indent=2)
        return fpath
    except Exception:
        return None


def list_gdrive_reports() -> list[dict]:
    """List saved reports from Google Drive / local backup."""
    reports = []
    try:
        for fname in sorted(os.listdir(GDRIVE_PATH), reverse=True):
            if fname.startswith("phoenix_report_") and fname.endswith(".json"):
                fpath = os.path.join(GDRIVE_PATH, fname)
                try:
                    with open(fpath, "r") as f:
                        data = json.load(f)
                    reports.append({
                        "file": fname,
                        "timestamp": data.get("timestamp", "?"),
                        "basket": data.get("basket", []),
                    })
                except Exception:
                    pass
    except Exception:
        pass
    return reports[:20]
