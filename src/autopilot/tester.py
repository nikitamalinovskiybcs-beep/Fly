"""Change Validator — walk-forward testing before deployment.

Validates proposed parameter changes using walk-forward splits,
PBO checks, and stability analysis across multiple data splits.
"""

import logging

import numpy as np

from src.autopilot.config import SAFETY_LIMITS
from src.autopilot.models import ParameterChange

logger = logging.getLogger(__name__)


class ChangeValidator:
    """Validates proposed changes before deployment."""

    def validate(
        self,
        change: ParameterChange,
        trade_returns: np.ndarray,
    ) -> ParameterChange:
        """Validate a proposed change via walk-forward testing.

        Args:
            change: The proposed ParameterChange.
            trade_returns: Array of historical trade returns.

        Returns:
            Updated ParameterChange with test results and status.
        """
        n = len(trade_returns)
        if n < 30:
            logger.warning("Not enough trades (%d) for validation", n)
            change.status = "rejected"
            return change

        split = int(n * 0.7)
        test = trade_returns[split:]

        sharpe_old = self._compute_sharpe(test)
        sharpe_new = self._replay_with_change(test, change)

        change.backtest_sharpe_before = round(sharpe_old, 4)
        change.backtest_sharpe_after = round(sharpe_new, 4)

        if abs(sharpe_old) > 1e-12:
            improvement = (sharpe_new - sharpe_old) / abs(sharpe_old)
        else:
            improvement = sharpe_new - sharpe_old

        change.improvement_pct = round(improvement * 100, 2)

        pbo = self._estimate_pbo(trade_returns)
        change.pbo_score = round(pbo, 4)

        stable = self._check_stability(trade_returns, n_splits=5)
        change.walk_forward_pass = stable

        min_improvement = SAFETY_LIMITS["min_improvement_to_deploy"]
        max_pbo = SAFETY_LIMITS["max_pbo_to_deploy"]

        if improvement >= min_improvement and pbo <= max_pbo and stable:
            change.status = "approved"
            logger.info(
                "Change APPROVED: %s (improvement=%.1f%%, PBO=%.2f)",
                change.parameter_name, improvement * 100, pbo,
            )
        else:
            change.status = "rejected"
            reasons = []
            if improvement < min_improvement:
                reasons.append(f"improvement {improvement:.1%} < {min_improvement:.0%}")
            if pbo > max_pbo:
                reasons.append(f"PBO {pbo:.2f} > {max_pbo:.2f}")
            if not stable:
                reasons.append("unstable across splits")
            logger.info("Change REJECTED: %s (%s)", change.parameter_name, "; ".join(reasons))

        return change

    def _compute_sharpe(self, returns: np.ndarray) -> float:
        """Compute annualized Sharpe ratio.

        Args:
            returns: Array of returns.

        Returns:
            Annualized Sharpe ratio.
        """
        if len(returns) < 2 or np.std(returns) < 1e-12:
            return 0.0
        return float(np.mean(returns) / np.std(returns) * np.sqrt(252))

    def _replay_with_change(
        self, returns: np.ndarray, change: ParameterChange,
    ) -> float:
        """Simulate the effect of the parameter change on returns.

        Args:
            returns: Test returns.
            change: The proposed change.

        Returns:
            Estimated Sharpe with the new parameter.
        """
        ratio = change.proposed_value / (change.current_value + 1e-12)
        adj = np.clip(ratio, 0.5, 2.0)
        adjusted_returns = returns * adj
        return self._compute_sharpe(adjusted_returns)

    def _estimate_pbo(self, returns: np.ndarray) -> float:
        """Quick PBO estimate using multiple walk-forward splits.

        Args:
            returns: Full array of trade returns.

        Returns:
            Estimated PBO score (0-1).
        """
        n = len(returns)
        if n < 20:
            return 0.5

        n_splits = min(8, n // 5)
        chunk = n // n_splits
        underperform = 0

        for i in range(n_splits - 1):
            train = returns[i * chunk:(i + 1) * chunk]
            test = returns[(i + 1) * chunk:(i + 2) * chunk]
            train_sr = self._compute_sharpe(train)
            test_sr = self._compute_sharpe(test)
            if test_sr < train_sr * 0.5:
                underperform += 1

        return underperform / max(n_splits - 1, 1)

    def _check_stability(
        self, returns: np.ndarray, n_splits: int = 5,
    ) -> bool:
        """Check if results are stable across multiple train/test splits.

        Args:
            returns: Full array of trade returns.
            n_splits: Number of different 70/30 splits to test.

        Returns:
            True if Sharpe is positive in majority of splits.
        """
        n = len(returns)
        positive_count = 0

        for i in range(n_splits):
            offset = i * (n // (n_splits * 3))
            start = min(offset, n - 10)
            split = start + int((n - start) * 0.7)
            test = returns[split:]
            if len(test) < 3:
                continue
            sr = self._compute_sharpe(test)
            if sr > 0:
                positive_count += 1

        return positive_count >= n_splits * 0.6
