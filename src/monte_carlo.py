"""Regime-conditional Monte Carlo simulation for portfolio returns.

Accepts a regime model (from self_learning_agents.RegimeAgent or standalone),
samples from regime-specific return distributions, and allows transitions
between regimes via a Markov transition matrix.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TRADING_DAYS = 252


# ═══════════════════════════════════════════════════════════════
# Regime Model
# ═══════════════════════════════════════════════════════════════


class RegimeModel:
    """Stores regime parameters and transition probabilities.

    Args:
        regime_params: Dict of regime_name -> {"mu": daily_mean, "sigma": daily_vol}.
        transition_matrix: (K x K) matrix of transition probabilities.
        regime_names: List of regime names matching matrix rows/cols.
    """

    def __init__(
        self,
        regime_params: Optional[dict[str, dict[str, float]]] = None,
        transition_matrix: Optional[np.ndarray] = None,
        regime_names: Optional[list[str]] = None,
    ) -> None:
        if regime_params is None:
            regime_params = {
                "BULL":     {"mu": 0.0008,  "sigma": 0.010},
                "SIDEWAYS": {"mu": 0.0001,  "sigma": 0.015},
                "BEAR":     {"mu": -0.0010, "sigma": 0.025},
            }
        if regime_names is None:
            regime_names = list(regime_params.keys())
        if transition_matrix is None:
            transition_matrix = np.array([
                [0.95, 0.04, 0.01],   # BULL -> BULL/SIDE/BEAR
                [0.05, 0.90, 0.05],   # SIDE -> BULL/SIDE/BEAR
                [0.02, 0.08, 0.90],   # BEAR -> BULL/SIDE/BEAR
            ])

        if len(regime_names) != len(regime_params):
            raise ValueError("regime_names must match regime_params keys")
        if transition_matrix.shape != (len(regime_names), len(regime_names)):
            raise ValueError("transition_matrix shape must be (K, K)")

        self.regime_params = regime_params
        self.transition_matrix = transition_matrix
        self.regime_names = regime_names
        self.n_regimes = len(regime_names)

    def regime_index(self, name: str) -> int:
        """Get index of regime by name.

        Args:
            name: Regime name.

        Returns:
            Integer index.

        Raises:
            ValueError: If regime name not found.
        """
        if name not in self.regime_names:
            raise ValueError(f"Unknown regime '{name}', valid: {self.regime_names}")
        return self.regime_names.index(name)


def fit_regime_model_from_returns(
    returns: pd.Series,
    n_regimes: int = 3,
) -> RegimeModel:
    """Estimate regime parameters from historical returns.

    Uses simple quantile-based classification: bottom 20% = BEAR,
    top 20% = BULL, middle = SIDEWAYS. Estimates mu/sigma per regime
    and transition matrix from observed sequences.

    Args:
        returns: Daily returns series (>= 50 observations).
        n_regimes: Number of regimes (only 3 supported).

    Returns:
        Fitted RegimeModel.

    Raises:
        ValueError: If returns too short or n_regimes != 3.
    """
    if len(returns) < 50:
        raise ValueError(f"Need >= 50 observations, got {len(returns)}")
    if n_regimes != 3:
        raise ValueError("Only 3 regimes supported currently")

    # Rolling 20-day return to classify regime
    roll = returns.rolling(20).sum().dropna()
    q20 = float(roll.quantile(0.20))
    q80 = float(roll.quantile(0.80))

    regimes = np.where(roll <= q20, 0, np.where(roll >= q80, 2, 1))
    regime_names = ["BEAR", "SIDEWAYS", "BULL"]

    # Estimate per-regime distribution
    params: dict[str, dict[str, float]] = {}
    aligned_returns = returns.iloc[-len(roll):]
    for idx, name in enumerate(regime_names):
        mask = regimes == idx
        if mask.sum() < 5:
            params[name] = {"mu": 0.0, "sigma": 0.015}
        else:
            subset = aligned_returns.values[mask]
            params[name] = {
                "mu": round(float(np.mean(subset)), 6),
                "sigma": round(float(np.std(subset)), 6),
            }

    # Estimate transition matrix
    trans = np.zeros((3, 3))
    for i in range(len(regimes) - 1):
        trans[regimes[i], regimes[i + 1]] += 1
    row_sums = trans.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    trans = trans / row_sums

    return RegimeModel(
        regime_params=params,
        transition_matrix=trans,
        regime_names=regime_names,
    )


# ═══════════════════════════════════════════════════════════════
# Regime-Conditional Monte Carlo
# ═══════════════════════════════════════════════════════════════


def regime_conditional_monte_carlo(
    regime_model: RegimeModel,
    n_paths: int = 10000,
    n_days: int = 504,
    initial_regime: str = "SIDEWAYS",
    seed: int = 42,
) -> dict:
    """Run Monte Carlo simulation with regime switching.

    At each step, the current regime determines the return distribution.
    Regime transitions follow the Markov transition matrix.

    Args:
        regime_model: RegimeModel with parameters and transitions.
        n_paths: Number of simulation paths.
        n_days: Simulation horizon in trading days.
        initial_regime: Starting regime name.
        seed: Random seed.

    Returns:
        Dict with path statistics, regime occupancy, and VaR/CVaR.

    Raises:
        ValueError: If initial_regime not in model.
    """
    if n_paths < 100:
        raise ValueError(f"n_paths must be >= 100, got {n_paths}")
    if n_days < 1:
        raise ValueError(f"n_days must be >= 1, got {n_days}")

    rng = np.random.default_rng(seed)
    start_idx = regime_model.regime_index(initial_regime)
    n_regimes = regime_model.n_regimes

    # Pre-extract regime parameters
    mus = np.array([regime_model.regime_params[r]["mu"] for r in regime_model.regime_names])
    sigmas = np.array([regime_model.regime_params[r]["sigma"] for r in regime_model.regime_names])
    trans = regime_model.transition_matrix

    # Cumulative transition probabilities for sampling
    cum_trans = np.cumsum(trans, axis=1)

    # Simulate
    cumulative_returns = np.ones((n_paths, n_days + 1))
    regime_counts = np.zeros((n_paths, n_regimes))
    current_regimes = np.full(n_paths, start_idx, dtype=int)

    for t in range(n_days):
        # Sample returns from current regime
        mu_t = mus[current_regimes]
        sigma_t = sigmas[current_regimes]
        daily_returns = rng.normal(mu_t, np.maximum(sigma_t, 1e-6))
        cumulative_returns[:, t + 1] = cumulative_returns[:, t] * (1 + daily_returns)

        # Count regime occupancy
        for r in range(n_regimes):
            regime_counts[:, r] += (current_regimes == r)

        # Transition to next regime
        u = rng.random(n_paths)
        for r in range(n_regimes):
            mask = current_regimes == r
            if mask.sum() == 0:
                continue
            ct = cum_trans[r]
            new_regimes = np.searchsorted(ct, u[mask])
            new_regimes = np.clip(new_regimes, 0, n_regimes - 1)
            current_regimes[mask] = new_regimes

    # Compute statistics
    final_values = cumulative_returns[:, -1]
    total_returns = final_values - 1

    # Drawdowns
    running_max = np.maximum.accumulate(cumulative_returns, axis=1)
    drawdowns = (cumulative_returns - running_max) / running_max
    max_drawdowns = drawdowns.min(axis=1)

    # VaR / CVaR from simulation
    var_95 = float(np.percentile(total_returns, 5))
    var_99 = float(np.percentile(total_returns, 1))
    cvar_95 = float(total_returns[total_returns <= var_95].mean()) if (total_returns <= var_95).sum() > 0 else var_95
    cvar_99 = float(total_returns[total_returns <= var_99].mean()) if (total_returns <= var_99).sum() > 0 else var_99

    # Regime occupancy
    avg_regime_pct = {}
    for r, name in enumerate(regime_model.regime_names):
        avg_regime_pct[name] = round(float(regime_counts[:, r].mean()) / n_days * 100, 1)

    return {
        "n_paths": n_paths,
        "n_days": n_days,
        "initial_regime": initial_regime,
        "mean_return": round(float(total_returns.mean()), 4),
        "median_return": round(float(np.median(total_returns)), 4),
        "std_return": round(float(total_returns.std()), 4),
        "percentile_5": round(float(np.percentile(total_returns, 5)), 4),
        "percentile_25": round(float(np.percentile(total_returns, 25)), 4),
        "percentile_75": round(float(np.percentile(total_returns, 75)), 4),
        "percentile_95": round(float(np.percentile(total_returns, 95)), 4),
        "prob_loss": round(float((total_returns < 0).mean()), 4),
        "prob_loss_10pct": round(float((total_returns < -0.10).mean()), 4),
        "mean_max_drawdown": round(float(max_drawdowns.mean()), 4),
        "worst_max_drawdown": round(float(max_drawdowns.min()), 4),
        "mc_var_95": round(var_95, 4),
        "mc_var_99": round(var_99, 4),
        "mc_cvar_95": round(cvar_95, 4),
        "mc_cvar_99": round(cvar_99, 4),
        "regime_occupancy_pct": avg_regime_pct,
    }


# ═══════════════════════════════════════════════════════════════
# Simple (non-regime) GBM Monte Carlo
# ═══════════════════════════════════════════════════════════════


def simple_gbm_monte_carlo(
    mu: float,
    sigma: float,
    n_paths: int = 10000,
    n_days: int = 504,
    seed: int = 42,
) -> dict:
    """Basic GBM Monte Carlo (no regime switching).

    Args:
        mu: Annualized expected return.
        sigma: Annualized volatility.
        n_paths: Number of simulation paths.
        n_days: Horizon in trading days.
        seed: Random seed.

    Returns:
        Dict with path statistics and VaR/CVaR.
    """
    if n_paths < 100:
        raise ValueError(f"n_paths must be >= 100, got {n_paths}")

    rng = np.random.default_rng(seed)
    daily_mu = mu / TRADING_DAYS
    daily_sigma = sigma / np.sqrt(TRADING_DAYS)

    daily_returns = rng.normal(daily_mu, daily_sigma, (n_paths, n_days))
    cum = np.cumprod(1 + daily_returns, axis=1)
    final = cum[:, -1]
    total_returns = final - 1

    var_95 = float(np.percentile(total_returns, 5))
    var_99 = float(np.percentile(total_returns, 1))

    return {
        "n_paths": n_paths,
        "n_days": n_days,
        "mean_return": round(float(total_returns.mean()), 4),
        "median_return": round(float(np.median(total_returns)), 4),
        "std_return": round(float(total_returns.std()), 4),
        "prob_loss": round(float((total_returns < 0).mean()), 4),
        "mc_var_95": round(var_95, 4),
        "mc_var_99": round(var_99, 4),
        "regime_aware": False,
    }
