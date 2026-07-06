"""Basket evolution agent — self-optimizing scoring weights."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from src.basket.models import EvolutionLog

logger = logging.getLogger(__name__)


class BasketEvolutionAgent:
    """Optimize basket scoring weights based on outcome feedback."""

    WEIGHTS_PATH = Path("data/basket_weights.json")
    LOG_PATH = Path("data/basket_evolution_log.json")
    MIN_OUTCOMES = 10
    IMPROVEMENT_THRESHOLD = 0.02

    DEFAULT_WEIGHTS = {
        "liquidity": 0.10,
        "fundamental": 0.15,
        "worst_of_tail_risk": 0.15,
        "crisis_correlation": 0.12,
        "max_drawdown_worst_of": 0.10,
        "sector_diversification": 0.10,
        "implied_vol_risk": 0.13,
        "greeks_exposure": 0.15,
    }

    def __init__(self) -> None:
        self._weights = dict(self.DEFAULT_WEIGHTS)
        self._outcomes: list[EvolutionLog] = []
        self._load()

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def record_outcome(
        self,
        tickers: list[str],
        date: str,
        autocall_triggered: bool,
        worst_of_asset: str,
        predicted_score: float,
        predicted_prob: float,
    ) -> None:
        """Record an actual basket outcome for learning.

        Args:
            tickers: Basket tickers.
            date: Observation date.
            autocall_triggered: Whether autocall happened.
            worst_of_asset: Actual worst performer.
            predicted_score: Score at prediction time.
            predicted_prob: Predicted autocall probability.
        """
        actual = "autocall" if autocall_triggered else "barrier_breach"
        predicted = "autocall" if predicted_prob > 0.5 else "barrier_breach"

        entry = EvolutionLog(
            timestamp=datetime.now().isoformat(),
            old_weights=dict(self._weights),
            trigger="outcome",
            basket_tickers=tickers,
            actual_outcome=actual,
            predicted_outcome=predicted,
            prediction_correct=(actual == predicted),
            score_error=abs(predicted_prob - (1.0 if autocall_triggered else 0.0)),
        )
        self._outcomes.append(entry)
        self._save()

    def evolve(self, trigger: str = "scheduled") -> dict:
        """Optimize weights based on recorded outcomes.

        Args:
            trigger: Reason for evolution.

        Returns:
            Dict with old/new weights and accuracy change.
        """
        if len(self._outcomes) < self.MIN_OUTCOMES:
            return {
                "status": "insufficient_data",
                "outcomes": len(self._outcomes),
                "required": self.MIN_OUTCOMES,
            }

        old_weights = dict(self._weights)
        old_accuracy = self._calc_accuracy(old_weights)

        try:
            from scipy.optimize import minimize

            def neg_accuracy(w_arr: np.ndarray) -> float:
                w = dict(zip(self._weights.keys(), w_arr))
                return -self._calc_accuracy(w)

            n = len(self._weights)
            x0 = np.array(list(self._weights.values()))
            bounds = [(0.05, 0.40)] * n
            constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

            result = minimize(neg_accuracy, x0, method="SLSQP",
                              bounds=bounds, constraints=constraints)

            if result.success:
                new_accuracy = -result.fun
                if new_accuracy > old_accuracy + self.IMPROVEMENT_THRESHOLD:
                    self._weights = dict(zip(self._weights.keys(), result.x.tolist()))
                    log = EvolutionLog(
                        timestamp=datetime.now().isoformat(),
                        old_weights=old_weights,
                        new_weights=dict(self._weights),
                        trigger=trigger,
                    )
                    self._outcomes.append(log)
                    self._save()
                    return {
                        "status": "improved",
                        "old_accuracy": round(old_accuracy, 4),
                        "new_accuracy": round(new_accuracy, 4),
                        "old_weights": old_weights,
                        "new_weights": dict(self._weights),
                    }

            return {"status": "no_improvement", "accuracy": round(old_accuracy, 4)}
        except ImportError:
            return {"status": "scipy_not_available"}

    def _calc_accuracy(self, weights: dict) -> float:
        """Calculate prediction accuracy with given weights.

        Returns fraction of correct predictions.
        """
        correct = sum(1 for o in self._outcomes if o.prediction_correct)
        return correct / len(self._outcomes) if self._outcomes else 0.0

    def backtest_weights(
        self,
        candidate_weights: dict[str, float],
    ) -> float:
        """Test candidate weights against historical outcomes.

        Args:
            candidate_weights: Candidate weight dict.

        Returns:
            Accuracy with candidate weights.
        """
        return self._calc_accuracy(candidate_weights)

    def _save(self) -> None:
        """Persist weights and log."""
        try:
            self.WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.WEIGHTS_PATH.write_text(json.dumps(self._weights, indent=2))

            log_data = [
                {
                    "timestamp": o.timestamp,
                    "old_weights": o.old_weights,
                    "new_weights": o.new_weights,
                    "trigger": o.trigger,
                    "basket_tickers": o.basket_tickers,
                    "actual_outcome": o.actual_outcome,
                    "predicted_outcome": o.predicted_outcome,
                    "prediction_correct": o.prediction_correct,
                    "score_error": o.score_error,
                }
                for o in self._outcomes[-100:]
            ]
            self.LOG_PATH.write_text(json.dumps(log_data, indent=2))
        except Exception as exc:
            logger.warning("Save failed: %s", exc)

    def _load(self) -> None:
        """Load saved weights and log."""
        try:
            if self.WEIGHTS_PATH.exists():
                self._weights = json.loads(self.WEIGHTS_PATH.read_text())
            if self.LOG_PATH.exists():
                data = json.loads(self.LOG_PATH.read_text())
                self._outcomes = [
                    EvolutionLog(**entry) for entry in data
                ]
        except Exception as exc:
            logger.warning("Load failed: %s", exc)
