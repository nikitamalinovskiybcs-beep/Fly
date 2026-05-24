"""Portfolio & Practical Risk — корреляции, slippage, capacity."""

import numpy as np
import pandas as pd


def correlation_matrix(prices_df: pd.DataFrame) -> pd.DataFrame:
    """Матрица корреляций дневных доходностей."""
    returns = prices_df.pct_change().dropna()
    return returns.corr()


def rolling_correlation(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    window: int = 63,
) -> pd.Series:
    """Скользящая корреляция стратегии с бенчмарком (по умолчанию 63 дня ≈ 3 мес.)."""
    combined = pd.DataFrame({
        "strategy": strategy_returns,
        "benchmark": benchmark_returns,
    }).dropna()
    return combined["strategy"].rolling(window).corr(combined["benchmark"])


def apply_slippage(
    returns: pd.Series,
    slippage_bps: float = 5.0,
    commission_bps: float = 2.0,
    trades_per_day: float = 1.0,
) -> pd.Series:
    """Применяет slippage и комиссии к доходностям.

    Parameters
    ----------
    slippage_bps : float
        Проскальзывание в базисных пунктах за сделку.
    commission_bps : float
        Комиссия в базисных пунктах за сделку.
    trades_per_day : float
        Среднее количество сделок в день.
    """
    total_cost_per_trade = (slippage_bps + commission_bps) / 10_000
    daily_cost = total_cost_per_trade * trades_per_day
    return returns - daily_cost


def estimate_capacity(
    avg_daily_volume_usd: float,
    max_participation_rate: float = 0.01,
    trades_per_day: float = 1.0,
) -> dict:
    """Оценка максимального размера капитала для стратегии.

    Parameters
    ----------
    avg_daily_volume_usd : float
        Средний дневной объём торгов в USD.
    max_participation_rate : float
        Максимальная доля от объёма (по умолчанию 1%).
    """
    max_trade_size = avg_daily_volume_usd * max_participation_rate
    max_capital = max_trade_size / trades_per_day if trades_per_day > 0 else 0

    return {
        "avg_daily_volume": avg_daily_volume_usd,
        "max_participation_rate": max_participation_rate,
        "max_trade_size_usd": max_trade_size,
        "estimated_max_capital_usd": max_capital,
        "warning": (
            "Ёмкость < $1M — стратегия ограничена"
            if max_capital < 1_000_000
            else None
        ),
    }


def slippage_impact_analysis(
    returns: pd.Series,
    slippage_range_bps: list[float] | None = None,
    commission_bps: float = 2.0,
    trades_per_day: float = 1.0,
) -> pd.DataFrame:
    """Анализ влияния slippage на итоговую доходность."""
    if slippage_range_bps is None:
        slippage_range_bps = [0, 1, 2, 5, 10, 20, 50]

    from src.core_metrics import sharpe_ratio, total_return, cagr

    rows = []
    for slip in slippage_range_bps:
        adj = apply_slippage(returns, slip, commission_bps, trades_per_day)
        rows.append({
            "slippage_bps": slip,
            "total_return": total_return(adj),
            "cagr": cagr(adj),
            "sharpe": sharpe_ratio(adj),
        })

    return pd.DataFrame(rows)
