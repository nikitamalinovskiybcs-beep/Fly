"""Overfitting Checks — Permutation Test + Out-of-Sample Degradation."""

import numpy as np
import pandas as pd

from src.core_metrics import sharpe_ratio, performance_summary


def permutation_test_vs_random(
    strategy_returns: pd.Series,
    n_permutations: int = 2000,
    seed: int = 42,
) -> dict:
    """Сравнение Sharpe стратегии с Sharpe перемешанных доходностей.

    Если p-value > 0.05 — результат стратегии статистически неотличим от случайного.
    """
    n_permutations = min(n_permutations, 2000)
    rng = np.random.default_rng(seed)

    observed_sharpe = sharpe_ratio(strategy_returns)
    arr = strategy_returns.values.copy()
    permuted_sharpes = np.empty(n_permutations)

    for i in range(n_permutations):
        rng.shuffle(arr)
        permuted_sharpes[i] = sharpe_ratio(pd.Series(arr, index=strategy_returns.index))

    p_value = float((permuted_sharpes >= observed_sharpe).sum() / n_permutations)

    return {
        "observed_sharpe": observed_sharpe,
        "mean_permuted_sharpe": float(permuted_sharpes.mean()),
        "std_permuted_sharpe": float(permuted_sharpes.std()),
        "p_value": p_value,
        "significant": p_value < 0.05,
        "distribution": permuted_sharpes,
        "verdict": (
            "Результат статистически значим (p < 0.05)"
            if p_value < 0.05
            else "ВНИМАНИЕ: результат НЕ значим — возможен overfitting"
        ),
    }


def out_of_sample_degradation(
    returns: pd.Series,
    train_ratio: float = 0.7,
) -> dict:
    """Проверяет деградацию метрик на out-of-sample части."""
    split_idx = int(len(returns) * train_ratio)
    train = returns.iloc[:split_idx]
    test = returns.iloc[split_idx:]

    train_perf = performance_summary(train)
    test_perf = performance_summary(test)

    sharpe_degradation = train_perf.sharpe - test_perf.sharpe
    return_degradation = train_perf.cagr - test_perf.cagr

    warnings = []
    if sharpe_degradation > 0.5:
        warnings.append(
            f"Sharpe деградация: {sharpe_degradation:.2f} — возможен overfitting"
        )
    if test_perf.sharpe < 0:
        warnings.append("Sharpe на OOS < 0 — стратегия убыточна на новых данных")
    if abs(return_degradation) > 0.1:
        warnings.append(
            f"CAGR деградация: {return_degradation:.1%}"
        )

    return {
        "train_sharpe": train_perf.sharpe,
        "test_sharpe": test_perf.sharpe,
        "sharpe_degradation": sharpe_degradation,
        "train_cagr": train_perf.cagr,
        "test_cagr": test_perf.cagr,
        "return_degradation": return_degradation,
        "train_max_dd": train_perf.max_drawdown,
        "test_max_dd": test_perf.max_drawdown,
        "warnings": warnings,
        "verdict": (
            "OOS результат стабилен"
            if len(warnings) == 0
            else f"ВНИМАНИЕ: {len(warnings)} проблем(а) обнаружено"
        ),
    }
