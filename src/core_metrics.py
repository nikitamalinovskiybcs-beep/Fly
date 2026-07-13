"""Core Metrics — Sharpe, Sortino, Calmar, Max DD, Profit Factor, Monte Carlo, Walk-Forward."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import logging

from src.logger import get_logger

logger = get_logger(__name__)

TRADING_DAYS = 252


@dataclass
class PerformanceSummary:
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    max_drawdown_duration_days: int
    profit_factor: float
    win_rate: float


def returns_from_prices(prices: pd.Series) -> pd.Series:
    return prices.pct_change().dropna()


def total_return(returns: pd.Series) -> float:
    return float((1 + returns).prod() - 1)


def cagr(returns: pd.Series) -> float:
    n_years = len(returns) / TRADING_DAYS
    if n_years <= 0:
        return 0.0
    cum = (1 + returns).prod()
    return float(cum ** (1 / n_years) - 1)


def annualized_volatility(returns: pd.Series) -> float:
    return float(returns.std() * np.sqrt(TRADING_DAYS))


def sharpe_ratio(returns: pd.Series, rf: float = 0.0) -> float:
    excess = returns - rf / TRADING_DAYS
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(TRADING_DAYS))


def sortino_ratio(returns: pd.Series, rf: float = 0.0) -> float:
    excess = returns - rf / TRADING_DAYS
    downside = excess[excess < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float(excess.mean() / downside.std() * np.sqrt(TRADING_DAYS))


def max_drawdown(returns: pd.Series) -> float:
    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return float(dd.min())


def max_drawdown_duration(returns: pd.Series) -> int:
    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    underwater = cum < peak
    if not underwater.any():
        return 0
    groups = (~underwater).cumsum()
    durations = underwater.groupby(groups).sum()
    return int(durations.max()) if len(durations) > 0 else 0


def profit_factor(returns: pd.Series) -> float:
    gains = returns[returns > 0].sum()
    losses = abs(returns[returns < 0].sum())
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def win_rate(returns: pd.Series) -> float:
    if len(returns) == 0:
        return 0.0
    return float((returns > 0).sum() / len(returns))


def performance_summary(returns: pd.Series, rf: float = 0.0) -> PerformanceSummary:
    mdd = max_drawdown(returns)
    c = cagr(returns)
    return PerformanceSummary(
        total_return=total_return(returns),
        cagr=c,
        volatility=annualized_volatility(returns),
        sharpe=sharpe_ratio(returns, rf),
        sortino=sortino_ratio(returns, rf),
        calmar=float(c / abs(mdd)) if mdd != 0 else 0.0,
        max_drawdown=mdd,
        max_drawdown_duration_days=max_drawdown_duration(returns),
        profit_factor=profit_factor(returns),
        win_rate=win_rate(returns),
    )


# --------------- Monte Carlo Permutation Test (Optimized) ---------------

def monte_carlo_permutation_test(
    returns: pd.Series,
    metric_fn=sharpe_ratio,
    n_permutations: int = 2000,
    seed: int = 42,
) -> dict:
    """Тест значимости: сравниваем метрику стратегии с перестановками.
    
    Оптимизирована с использованием NumPy для быстрых вычислений.

    Returns
    -------
    dict с ключами: observed, p_value, permuted_distribution
    """
    n_permutations = min(n_permutations, 2000)
    rng = np.random.default_rng(seed)

    observed = metric_fn(returns)
    arr = returns.values.copy()
    permuted_values = np.empty(n_permutations)

    logger.info(f"Запуск Monte Carlo с {n_permutations} перестановок")
    
    for i in range(n_permutations):
        rng.shuffle(arr)
        permuted_values[i] = metric_fn(pd.Series(arr))
        
        if (i + 1) % max(1, n_permutations // 10) == 0:
            logger.debug(f"MC прогресс: {(i+1)/n_permutations*100:.0f}%")

    p_value = float((permuted_values >= observed).sum() / n_permutations)
    logger.info(f"MC завершён: observed={observed:.4f}, p-value={p_value:.4f}")

    return {
        "observed": observed,
        "p_value": p_value,
        "permuted_distribution": permuted_values,
    }


# --------------- Walk-Forward Analysis (Optimized) ---------------

def walk_forward_analysis(
    returns: pd.Series,
    n_splits: int = 5,
    metric_fn=sharpe_ratio,
) -> list[dict]:
    """Простая Walk-Forward: разбиваем на n_splits периодов,
    тренируем на первых (n-1), тестируем на последнем, сдвигаем.
    
    Оптимизирована с логированием и валидацией.
    """
    n = len(returns)
    fold_size = n // n_splits
    results = []

    logger.info(f"Walk-Forward анализ: {n_splits} фолдов, размер={fold_size}")
    
    for i in range(1, n_splits):
        train_end = i * fold_size
        test_end = min(train_end + fold_size, n)
        train = returns.iloc[:train_end]
        test = returns.iloc[train_end:test_end]

        if len(test) < 5:
            logger.warning(f"Фолд {i}: слишком мало тестовых данных ({len(test)}), пропускаем")
            continue

        train_metric = metric_fn(train)
        test_metric = metric_fn(test)
        degradation = train_metric - test_metric
        
        logger.debug(f"Фолд {i}: train={train_metric:.2f}, test={test_metric:.2f}, deg={degradation:.2f}")
        
        results.append({
            "fold": i,
            "train_start": str(train.index[0].date()) if hasattr(train.index[0], "date") else str(train.index[0]),
            "train_end": str(train.index[-1].date()) if hasattr(train.index[-1], "date") else str(train.index[-1]),
            "test_start": str(test.index[0].date()) if hasattr(test.index[0], "date") else str(test.index[0]),
            "test_end": str(test.index[-1].date()) if hasattr(test.index[-1], "date") else str(test.index[-1]),
            "train_metric": train_metric,
            "test_metric": test_metric,
            "degradation": degradation,
        })

    logger.info(f"Walk-Forward завершён: {len(results)} успешных фолдов")
    return results


# --------------- Stability by Period ---------------

def stability_by_periods(
    returns: pd.Series,
    periods: dict[str, tuple[str, str]] | None = None,
    metric_fn=sharpe_ratio,
) -> dict[str, float]:
    """Проверка стабильности метрики по разным периодам."""
    if periods is None:
        periods = {
            "2020": ("2020-01-01", "2020-12-31"),
            "2022": ("2022-01-01", "2022-12-31"),
            "Last 6M": (
                str((pd.Timestamp.now() - pd.DateOffset(months=6)).date()),
                str(pd.Timestamp.now().date()),
            ),
            "Last 1Y": (
                str((pd.Timestamp.now() - pd.DateOffset(years=1)).date()),
                str(pd.Timestamp.now().date()),
            ),
        }

    result = {}
    for name, (start, end) in periods.items():
        mask = (returns.index >= start) & (returns.index <= end)
        subset = returns.loc[mask]
        if len(subset) < 10:
            result[name] = float("nan")
        else:
            result[name] = metric_fn(subset)
    return result
