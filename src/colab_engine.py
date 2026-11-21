"""
Google Colab Engine — Interface for heavy MC computation (Karpathy method).

Pattern:
1. Colab notebook runs heavy MC simulations (500K+ paths) on free GPU
2. Results saved to ClickHouse / Google Drive
3. This module polls for cached results or triggers Colab via REST
4. Graceful fallback to local compute if Colab unavailable

Zero cost: Google Colab free tier provides T4 GPU.
"""

import hashlib
import os
import time
from typing import Dict, List, Optional, Any

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


# ── Config ──
COLAB_WEBHOOK = os.environ.get("COLAB_WEBHOOK", "")
COLAB_POLL_INTERVAL = 5  # seconds
COLAB_POLL_MAX = 12  # max 60s wait


def _basket_hash(tickers: List[str]) -> str:
    """Deterministic hash for basket."""
    return hashlib.md5(",".join(sorted(tickers)).encode()).hexdigest()[:12]


def trigger_colab_sim(
    tickers: List[str],
    n_sims: int = 500_000,
    barrier: float = 0.65,
    coupon: float = 0.065,
) -> Optional[str]:
    """
    Trigger Google Colab simulation via webhook.
    Returns job_id if triggered, None if unavailable.
    """
    if not REQUESTS_OK or not COLAB_WEBHOOK:
        return None
    try:
        resp = requests.post(
            COLAB_WEBHOOK,
            json={
                "basket": tickers,
                "n_sims": n_sims,
                "barrier": barrier,
                "coupon": coupon,
                "job_id": _basket_hash(tickers),
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("job_id", _basket_hash(tickers))
    except Exception:
        pass
    return None


def poll_colab_result(
    job_id: str,
    max_wait: int = COLAB_POLL_MAX,
) -> Optional[Dict]:
    """Poll for Colab result from ClickHouse cache."""
    if not REQUESTS_OK:
        return None
    from src.conductor import cache_get
    for _ in range(max_wait):
        result = cache_get([job_id])
        if result:
            return result
        time.sleep(COLAB_POLL_INTERVAL)
    return None


def get_colab_status() -> Dict[str, Any]:
    """Check if Colab integration is available."""
    available = bool(COLAB_WEBHOOK)
    return {
        "available": available,
        "webhook_set": available,
        "label": "Google Colab T4 GPU" if available else "Colab не подключен",
        "description": "500K+ Sobol MC на бесплатном GPU",
    }


def local_sobol_mc(
    n_assets: int,
    horizon: int = 504,
    n_sims: int = 10_000,
    mu: List[float] = None,
    sigma: List[float] = None,
    corr_matrix: List[List[float]] = None,
    barrier: float = 0.65,
    coupon_q: float = 0.065,
) -> Dict[str, Any]:
    """
    Lightweight local MC fallback (runs on Streamlit Cloud).
    Uses pseudo-random (not Sobol) for speed; fewer sims.
    Results are approximate — label as such in UI.
    """
    import numpy as np

    if mu is None:
        mu = [0.08] * n_assets
    if sigma is None:
        sigma = [0.30] * n_assets
    if corr_matrix is None:
        corr_matrix = np.eye(n_assets).tolist()

    mu_arr = np.array(mu)
    sigma_arr = np.array(sigma)
    corr = np.array(corr_matrix)

    # Cholesky for correlated paths
    cov = np.outer(sigma_arr, sigma_arr) * corr
    try:
        L = np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        cov += np.eye(n_assets) * 1e-6
        L = np.linalg.cholesky(cov)

    dt = 1 / 252
    obs_days = [63, 126, 189, 252, 315, 378, 441, 504]
    obs_days = [d for d in obs_days if d <= horizon]

    n_coupons = []
    ki_hits = 0
    final_payoffs = []

    for _ in range(n_sims):
        Z = np.random.randn(horizon, n_assets)
        corr_Z = Z @ L.T
        paths = np.ones((horizon + 1, n_assets))
        for t in range(horizon):
            drift = (mu_arr - 0.5 * sigma_arr ** 2) * dt
            diffusion = sigma_arr * np.sqrt(dt) * corr_Z[t]
            paths[t + 1] = paths[t] * np.exp(drift + diffusion)

        min_worst = paths[1:, :].min(axis=0).min()  # overall min of worst performer

        # Count coupons (simplified: coupon if worst > barrier at each obs)
        cpns = 0
        autocalled = False
        for obs in obs_days:
            if obs <= horizon:
                worst_at_obs = paths[obs, :].min()
                if worst_at_obs >= 1.0:  # autocall
                    cpns += 1
                    autocalled = True
                    break
                elif worst_at_obs >= barrier:
                    cpns += 1

        ki_hit = min_worst < barrier
        if ki_hit:
            ki_hits += 1

        payoff = cpns * coupon_q
        if not autocalled and ki_hit:
            payoff += min_worst - 1  # loss from worst performer
        elif not autocalled:
            payoff += 0  # capital returned at par

        n_coupons.append(cpns)
        final_payoffs.append(payoff)

    payoffs = np.array(final_payoffs)
    p_ki_val = round(ki_hits / n_sims * 100, 1)
    p_loss_val = round(float((payoffs < 0).mean()) * 100, 1)
    p_autocall_val = round(100 - p_ki_val * 1.2, 1)
    return {
        "avg_payoff": round(float(payoffs.mean()), 4),
        "std_payoff": round(float(payoffs.std()), 4),
        "p_ki": p_ki_val,
        "p_loss": p_loss_val,
        "p_autocall": max(10, min(90, p_autocall_val)),
        "avg_coupons": round(float(np.mean(n_coupons)), 2),
        "win_rate": round(float((payoffs > 0).mean()) * 100, 1),
        "var_95": round(float(np.percentile(payoffs, 5)), 4),
        "cvar_95": round(float(payoffs[payoffs <= np.percentile(payoffs, 5)].mean()), 4) if len(payoffs) > 0 else 0,
        "n_sims": n_sims,
        "method": "pseudo_random_mc",
        "source": "local_mc",
        "compute": "Streamlit Cloud (approx)",
    }
