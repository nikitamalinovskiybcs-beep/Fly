"""Risk Metrics — VaR, CVaR, Drawdown Distribution, Stress Tests."""

import numpy as np
import pandas as pd
from scipy import stats
import logging

from src.logger import get_logger

logger = get_logger(__name__)


def value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    """Историческая VaR (отрицательное значение = убыток)."""
    return float(np.percentile(returns, (1 - confidence) * 100))


def conditional_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """CVaR (Expected Shortfall) — среднее хвоста за VaR."""
    var = value_at_risk(returns, confidence)
    tail = returns[returns <= var]
    if len(tail) == 0:
        return var
    return float(tail.mean())


def parametric_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Параметрическая VaR (нормальное распределение)."""
    mu = returns.mean()
    sigma = returns.std()
    z = stats.norm.ppf(1 - confidence)
    return float(mu + z * sigma)


def drawdown_series(returns: pd.Series) -> pd.Series:
    """Серия drawdown (все значения <= 0)."""
    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    return (cum - peak) / peak


def drawdown_distribution(returns: pd.Series, n_bins: int = 50) -> dict:
    """Распределение drawdown: гистограмма + статистика."""
    dd = drawdown_series(returns)
    return {
        "mean": float(dd.mean()),
        "median": float(dd.median()),
        "worst": float(dd.min()),
        "std": float(dd.std()),
        "percentile_5": float(np.percentile(dd, 5)),
        "series": dd,
    }


# --------------- Stress Tests (Flexible) ---------------

DEFAULT_STRESS_SCENARIOS = {
    "GFC 2008": ("2008-09-01", "2009-03-31"),
    "COVID 2020": ("2020-02-15", "2020-04-15"),
    "Rate Hike 2022": ("2022-01-01", "2022-10-31"),
    "SVB Crisis 2023": ("2023-03-01", "2023-03-31"),
}


def stress_test(
    returns: pd.Series,
    scenarios: dict[str, tuple[str, str]] | None = None,
) -> list[dict]:
    """Рассчитывает кумулятивную доходность за каждый кризисный период.
    
    Поддерживает custom сценарии через параметр scenarios.
    """
    if scenarios is None:
        scenarios = DEFAULT_STRESS_SCENARIOS

    logger.info(f"Запуск stress-тестов: {len(scenarios)} сценариев")
    results = []
    
    for name, (start, end) in scenarios.items():
        mask = (returns.index >= start) & (returns.index <= end)
        subset = returns.loc[mask]
        
        if len(subset) < 2:
            logger.warning(f"Сценарий '{name}': нет данных за {start}—{end}")
            results.append({
                "scenario": name,
                "period": f"{start} → {end}",
                "cum_return": float("nan"),
                "max_dd": float("nan"),
                "n_days": 0,
                "warning": "Нет данных за период",
            })
            continue

        cum_ret = float((1 + subset).prod() - 1)
        dd = drawdown_series(subset)
        max_dd_val = float(dd.min())
        
        logger.debug(f"Сценарий '{name}': cum_ret={cum_ret:.2%}, max_dd={max_dd_val:.2%}")

        results.append({
            "scenario": name,
            "period": f"{start} → {end}",
            "cum_return": cum_ret,
            "max_dd": max_dd_val,
            "n_days": len(subset),
            "warning": None,
        })

    logger.info(f"Stress-тесты завершены: {len(results)} сценариев обработано")
    return results


def add_custom_stress_scenario(
    name: str,
    start_date: str,
    end_date: str,
) -> dict[str, tuple[str, str]]:
    """Помощник для добавления custom сценария stress-теста."""
    scenario = {**DEFAULT_STRESS_SCENARIOS, name: (start_date, end_date)}
    logger.info(f"Добавлен custom сценарий '{name}': {start_date}—{end_date}")
    return scenario


def risk_summary(returns: pd.Series) -> dict:
    """Сводка по VaR / CVaR для 95% и 99%."""
    return {
        "VaR_95": value_at_risk(returns, 0.95),
        "CVaR_95": conditional_var(returns, 0.95),
        "VaR_99": value_at_risk(returns, 0.99),
        "CVaR_99": conditional_var(returns, 0.99),
        "Parametric_VaR_95": parametric_var(returns, 0.95),
        "Parametric_VaR_99": parametric_var(returns, 0.99),
    }
