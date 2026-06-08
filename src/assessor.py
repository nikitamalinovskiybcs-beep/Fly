"""StrategyRiskAssessor — главный класс фреймворка v2.3 с улучшениями."""

import json
import datetime as dt
from dataclasses import asdict
from typing import Optional, List, Dict, Any

import pandas as pd

from src.data_module import fetch_prices, fetch_ohlcv, DEFAULT_TICKERS
from src.core_metrics import (
    returns_from_prices,
    performance_summary,
    monte_carlo_permutation_test,
    walk_forward_analysis,
    stability_by_periods,
    sharpe_ratio,
)
from src.risk_metrics import risk_summary, stress_test, drawdown_distribution
from src.overfitting import permutation_test_vs_random, out_of_sample_degradation
from src.portfolio import (
    correlation_matrix,
    apply_slippage,
    slippage_impact_analysis,
)


class StrategyRiskAssessor:
    """Trading Strategy Risk Assessment Framework v2.3.

    Принципы:
    - Slavishly follow the models — строгое следование правилам без эмоций.
    - Моделируем состояние рынка, а не предсказываем.
    - Максимальная защита от overfitting.
    - Математика и rigor > красивые графики.

    Example:
        >>> assessor = StrategyRiskAssessor(
        ...     tickers=['AAPL', 'MSFT'],
        ...     rf_rate=0.05,
        ... )
        >>> assessor.update_market_data(period='5y')
        >>> report = assessor.generate_report('AAPL')
    """

    def __init__(
        self,
        tickers: Optional[List[str]] = None,
        benchmark: str = "SPY",
        rf_rate: float = 0.05,
        n_permutations: int = 2000,
        slippage_bps: float = 5.0,
        commission_bps: float = 2.0,
        trades_per_day: float = 1.0,
    ) -> None:
        """Инициализация ассесора.

        Args:
            tickers: Список тикеров для анализа
            benchmark: Бенчмарк для сравнения (по умолчанию SPY)
            rf_rate: Risk-free rate (по умолчанию 5%)
            n_permutations: Количество перестановок для Monte Carlo (макс 2000)
            slippage_bps: Слипейдж в basis points
            commission_bps: Комиссия в basis points
            trades_per_day: Средне количество сделок в день

        Raises:
            ValueError: Если n_permutations > 2000
        """
        if n_permutations > 2000:
            raise ValueError("n_permutations not exceed 2000 (DoS protection)")

        self.tickers: List[str] = tickers or DEFAULT_TICKERS
        self.benchmark: str = benchmark
        self.rf_rate: float = rf_rate
        self.n_permutations: int = min(n_permutations, 2000)
        self.slippage_bps: float = slippage_bps
        self.commission_bps: float = commission_bps
        self.trades_per_day: float = trades_per_day

        self.prices: Optional[pd.DataFrame] = None
        self.returns: Optional[pd.DataFrame] = None
        self._last_update: Optional[dt.datetime] = None

    def update_market_data(self, period: str = "5y") -> pd.DataFrame:
        """Загружает свежие рыночные данные.

        Args:
            period: Период загрузки (1y, 2y, 5y, 10y, max)

        Returns:
            DataFrame с ценами закрытия

        Raises:
            ValueError: Если не удалось загрузить данные
        """
        try:
            self.prices = fetch_prices(self.tickers, period=period)
            if self.prices.empty:
                raise ValueError("No price data loaded")
            self.returns = self.prices.pct_change().dropna()
            self._last_update = dt.datetime.now(dt.timezone.utc)
            return self.prices
        except Exception as e:
            raise ValueError(f"Failed to load market data: {str(e)}")

    def _ensure_data(self) -> None:
        """Проверка наличия данных, загрузка при необходимости."""
        if self.returns is None:
            self.update_market_data()

    def get_performance(self, ticker: str) -> Dict[str, Any]:
        """Полная сводка метрик для тикера.

        Args:
            ticker: Тикер актива

        Returns:
            Словарь с метриками производительности

        Raises:
            ValueError: Если тикер не найден
        """
        self._ensure_data()
        if ticker not in self.returns.columns:
            raise ValueError(
                f"Ticker {ticker} not found. Available: {list(self.returns.columns)}"
            )
        rets = self.returns[ticker].dropna()
        if len(rets) < 20:
            raise ValueError(f"Not enough data for {ticker}")
        perf = performance_summary(rets, self.rf_rate)
        return asdict(perf)

    def get_all_performance(self) -> pd.DataFrame:
        """Метрики для всех тикеров.

        Returns:
            DataFrame с метриками всех тикеров
        """
        self._ensure_data()
        rows: Dict[str, Dict[str, Any]] = {}
        for ticker in self.returns.columns:
            rets = self.returns[ticker].dropna()
            if len(rets) < 20:
                continue
            perf = performance_summary(rets, self.rf_rate)
            rows[ticker] = asdict(perf)
        return pd.DataFrame(rows).T

    def run_monte_carlo_test(self, ticker: str) -> Dict[str, Any]:
        """Monte Carlo Permutation Test для тикера.

        Args:
            ticker: Тикер актива

        Returns:
            Результаты Monte Carlo теста
        """
        self._ensure_data()
        rets = self.returns[ticker].dropna()
        return monte_carlo_permutation_test(rets, n_permutations=self.n_permutations)

    def run_walk_forward(self, ticker: str, n_splits: int = 5) -> List[Dict[str, Any]]:
        """Walk-Forward анализ.

        Args:
            ticker: Тикер актива
            n_splits: Количество фолдов

        Returns:
            Список результатов по каждому фолду
        """
        self._ensure_data()
        rets = self.returns[ticker].dropna()
        return walk_forward_analysis(rets, n_splits=n_splits)

    def get_stability(self, ticker: str) -> Dict[str, float]:
        """Стабильность Sharpe по периодам.

        Args:
            ticker: Тикер актива

        Returns:
            Словарь с Sharpe по разным периодам
        """
        self._ensure_data()
        rets = self.returns[ticker].dropna()
        return stability_by_periods(rets)

    def get_risk(self, ticker: str) -> Dict[str, float]:
        """VaR / CVaR сводка.

        Args:
            ticker: Тикер актива

        Returns:
            Словарь с риск-метриками
        """
        self._ensure_data()
        rets = self.returns[ticker].dropna()
        return risk_summary(rets)

    def get_stress_tests(self, ticker: str) -> List[Dict[str, Any]]:
        """Stress-тесты по кризисным периодам.

        Args:
            ticker: Тикер актива

        Returns:
            Список результатов stress-тестов
        """
        self._ensure_data()
        rets = self.returns[ticker].dropna()
        return stress_test(rets)

    def get_drawdown_distribution(self, ticker: str) -> Dict[str, Any]:
        """Распределение drawdown.

        Args:
            ticker: Тикер актива

        Returns:
            Статистика drawdown распределения
        """
        self._ensure_data()
        rets = self.returns[ticker].dropna()
        result = drawdown_distribution(rets)
        result.pop("series", None)
        return result

    def check_overfitting(self, ticker: str) -> Dict[str, Any]:
        """Permutation test + OOS degradation.

        Args:
            ticker: Тикер актива

        Returns:
            Результаты проверки на overfitting
        """
        self._ensure_data()
        rets = self.returns[ticker].dropna()
        perm = permutation_test_vs_random(rets, self.n_permutations)
        perm.pop("distribution", None)
        oos = out_of_sample_degradation(rets)
        return {"permutation_test": perm, "oos_degradation": oos}

    def get_correlations(self) -> pd.DataFrame:
        """Матрица корреляций.

        Returns:
            DataFrame с матрицей корреляций
        """
        self._ensure_data()
        if self.prices is None:
            raise ValueError("Prices not loaded")
        return correlation_matrix(self.prices)

    def get_slippage_impact(self, ticker: str) -> pd.DataFrame:
        """Анализ влияния slippage.

        Args:
            ticker: Тикер актива

        Returns:
            DataFrame с анализом slippage impact
        """
        self._ensure_data()
        rets = self.returns[ticker].dropna()
        return slippage_impact_analysis(
            rets,
            commission_bps=self.commission_bps,
            trades_per_day=self.trades_per_day,
        )

    def generate_report(self, ticker: str) -> Dict[str, Any]:
        """Полный отчёт по тикеру.

        Args:
            ticker: Тикер актива

        Returns:
            Полный аналитический отчёт
        """
        self._ensure_data()
        report: Dict[str, Any] = {
            "ticker": ticker,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "framework_version": "2.3",
            "performance": self.get_performance(ticker),
            "risk": self.get_risk(ticker),
            "stress_tests": self.get_stress_tests(ticker),
            "drawdown_dist": self.get_drawdown_distribution(ticker),
            "stability": self.get_stability(ticker),
            "overfitting": self.check_overfitting(ticker),
        }

        # Предупреждения
        warnings: List[str] = []
        perf = report["performance"]
        if perf["sharpe"] < 0.5:
            warnings.append(
                f"Sharpe ({perf['sharpe']:.2f}) < 0.5 — слабая стратегия"
            )
        if perf["max_drawdown"] < -0.3:
            warnings.append(f"Max DD ({perf['max_drawdown']:.1%}) > 30% — высокий риск")
        if not report["overfitting"]["permutation_test"]["significant"]:
            warnings.append(
                "Результат НЕ прошёл permutation test — возможен overfitting"
            )

        oos = report["overfitting"]["oos_degradation"]
        warnings.extend(oos.get("warnings", []))

        report["warnings"] = warnings
        report["risk_score"] = self._compute_risk_score(report)

        return report

    def _compute_risk_score(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Риск-скор от 0 (безопасно) до 100 (критично).

        Args:
            report: Полный отчёт

        Returns:
            Словарь с риск-скором и уровнем
        """
        score: float = 50
        perf = report["performance"]

        if perf["sharpe"] > 1.5:
            score -= 15
        elif perf["sharpe"] > 1.0:
            score -= 10
        elif perf["sharpe"] < 0:
            score += 20

        if perf["max_drawdown"] < -0.5:
            score += 20
        elif perf["max_drawdown"] < -0.3:
            score += 10
        elif perf["max_drawdown"] > -0.1:
            score -= 10

        if report["overfitting"]["permutation_test"]["significant"]:
            score -= 10
        else:
            score += 15

        oos_warnings = report["overfitting"]["oos_degradation"].get("warnings", [])
        score += len(oos_warnings) * 5

        score = max(0, min(100, score))

        if score <= 30:
            level = "LOW"
        elif score <= 60:
            level = "MEDIUM"
        else:
            level = "HIGH"

        return {"score": int(score), "level": level}

    @property
    def last_update(self) -> Optional[str]:
        """Время последнего обновления данных.

        Returns:
            ISO формат времени обновления или None
        """
        if self._last_update:
            return self._last_update.isoformat()
        return None
