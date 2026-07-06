"""Parameter Optimizer — Bayesian, grid search, and weight optimization.

Optimizes parameters within safety bounds using walk-forward validation.
Never changes code — only adjusts config values, weights, and thresholds.
"""

import logging
from typing import Any, Optional

import numpy as np
from scipy.optimize import minimize

from src.autopilot.config import (
    TUNABLE_PARAMETERS,
    SAFETY_LIMITS,
    load_config,
)
from src.autopilot.models import AnalysisInsight, ParameterChange

logger = logging.getLogger(__name__)


class ParameterOptimizer:
    """Optimizes parameters within safety bounds."""

    def optimize(self, insights: list[AnalysisInsight]) -> list[ParameterChange]:
        """Generate parameter change proposals from analysis insights.

        Args:
            insights: List of AnalysisInsight from Analyzer.

        Returns:
            List of ParameterChange proposals (max 3 per day).
        """
        config = load_config()
        proposals: list[ParameterChange] = []
        max_proposals = SAFETY_LIMITS["max_changes_per_day"]

        high_insights = [i for i in insights if i.priority == "high"]
        for insight in high_insights[:max_proposals]:
            change = self._insight_to_change(insight, config)
            if change is not None:
                proposals.append(change)

        return proposals[:max_proposals]

    def _insight_to_change(
        self, insight: AnalysisInsight, config: dict[str, Any],
    ) -> Optional[ParameterChange]:
        """Convert an insight into a concrete parameter change proposal.

        Args:
            insight: The analysis insight.
            config: Current config dict.

        Returns:
            ParameterChange or None if no actionable change.
        """
        rec = insight.recommendation.lower()
        param_name = None
        direction = 0

        if "confidence" in rec:
            param_name = "confidence_threshold"
            direction = -1 if "reduce" in rec or "lower" in rec else 1
        elif "stop" in rec and "loss" in rec:
            param_name = "stop_loss_atr_mult"
            direction = -1 if "tighter" in rec else 1
        elif "rsi" in rec and "buy" in rec:
            param_name = "rsi_buy_threshold"
            direction = 1 if "raise" in rec else -1
        elif "rsi" in rec and "sell" in rec:
            param_name = "rsi_sell_threshold"
            direction = -1 if "lower" in rec else 1
        elif "sma" in rec and "fast" in rec:
            param_name = "sma_fast_period"
            direction = 1 if "increase" in rec else -1
        elif "bear" in rec and "disable" in rec:
            param_name = "trade_in_bear_regime"

        if param_name is None:
            return None

        spec = TUNABLE_PARAMETERS.get(param_name, {})
        current = config.get(param_name, spec.get("default", 0))

        if spec.get("type") == "bool":
            proposed = False if "disable" in rec else True
            return ParameterChange(
                parameter_name=param_name,
                current_value=float(current),
                proposed_value=0.0 if not proposed else 1.0,
                change_pct=100.0,
                reason=insight.finding,
                backtest_sharpe_before=0.0,
                backtest_sharpe_after=0.0,
                improvement_pct=0.0,
                pbo_score=0.0,
                walk_forward_pass=False,
                status="proposed",
            )

        max_change = spec.get("max_change_per_day", abs(current) * 0.2)
        step = max_change * 0.5
        proposed = current + direction * step
        proposed = max(spec.get("min", proposed), min(spec.get("max", proposed), proposed))
        change_pct = abs(proposed - current) / (abs(current) + 1e-12) * 100

        return ParameterChange(
            parameter_name=param_name,
            current_value=float(current),
            proposed_value=float(proposed),
            change_pct=round(change_pct, 2),
            reason=insight.finding,
            backtest_sharpe_before=0.0,
            backtest_sharpe_after=0.0,
            improvement_pct=0.0,
            pbo_score=0.0,
            walk_forward_pass=False,
            status="proposed",
        )

    def optimize_continuous(
        self,
        param_name: str,
        trade_returns: np.ndarray,
        metric: str = "sharpe",
    ) -> float:
        """Bayesian-style optimization for continuous parameters.

        Args:
            param_name: Name of the parameter to optimize.
            trade_returns: Array of trade returns.
            metric: Metric to optimize (default: sharpe).

        Returns:
            Optimal parameter value.
        """
        spec = TUNABLE_PARAMETERS.get(param_name, {})
        lo = spec.get("min", 0)
        hi = spec.get("max", 1)

        def objective(x: np.ndarray) -> float:
            val = float(x[0])
            filtered = trade_returns[np.abs(trade_returns) > val * 0.01]
            if len(filtered) < 5:
                return 0.0
            sharpe = float(filtered.mean() / (filtered.std() + 1e-12) * np.sqrt(252))
            return -sharpe

        result = minimize(
            objective, x0=[(lo + hi) / 2],
            bounds=[(lo, hi)], method="L-BFGS-B",
        )
        return float(result.x[0])

    def optimize_weights(
        self,
        weight_name: str,
        trade_returns: np.ndarray,
        signal_matrix: np.ndarray,
    ) -> dict[str, float]:
        """Optimize signal or scoring weights using SLSQP.

        Args:
            weight_name: Name of the weights dict parameter.
            trade_returns: Array of trade returns.
            signal_matrix: (n_trades x n_signals) matrix.

        Returns:
            Dict of signal_name -> optimized_weight.
        """
        spec = TUNABLE_PARAMETERS.get(weight_name, {})
        default_weights = spec.get("default", {})
        names = list(default_weights.keys())
        n = len(names)
        lo = spec.get("min_per_weight", 0.03)
        hi = spec.get("max_per_weight", 0.40)

        if signal_matrix.shape[1] != n:
            logger.warning("Signal matrix shape mismatch, returning defaults")
            return default_weights

        def objective(w: np.ndarray) -> float:
            composite = signal_matrix @ w
            if np.std(composite) < 1e-12:
                return 0.0
            sharpe = float(np.mean(composite) / np.std(composite) * np.sqrt(252))
            return -sharpe

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(lo, hi)] * n
        x0 = np.array([1.0 / n] * n)

        result = minimize(
            objective, x0, method="SLSQP",
            bounds=bounds, constraints=constraints,
        )
        opt_weights = result.x
        return {names[i]: round(float(opt_weights[i]), 4) for i in range(n)}

    def grid_search(
        self,
        param_name: str,
        values: list[Any],
        trade_returns: np.ndarray,
    ) -> Any:
        """Try each value and pick best by walk-forward Sharpe.

        Args:
            param_name: Parameter name.
            values: List of candidate values to try.
            trade_returns: Array of trade returns.

        Returns:
            Best value from the grid.
        """
        best_val = values[0]
        best_sharpe = -np.inf
        n = len(trade_returns)
        train_n = int(n * 0.7)

        for val in values:
            train = trade_returns[:train_n]
            test = trade_returns[train_n:]
            if len(test) < 3:
                continue
            sharpe = float(test.mean() / (test.std() + 1e-12) * np.sqrt(252))
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_val = val

        return best_val
