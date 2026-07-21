"""Basket feedback loop — connect real market outcomes to evolution agent.

Monitors scored baskets over time, records actual knock-in/autocall outcomes,
and feeds them back to BasketEvolutionAgent for weight optimization.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from src.basket.evolution import BasketEvolutionAgent
from src.basket.scorer import BasketScorer

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEEDBACK_PATH = PROJECT_ROOT / "data" / "basket_feedback.json"


class BasketFeedbackLoop:
    """Records basket predictions and checks outcomes for learning."""

    def __init__(self) -> None:
        self._scorer = BasketScorer()
        self._evolution = BasketEvolutionAgent()
        self._pending: list[dict] = []
        self._completed: list[dict] = []
        self._load()

    def score_and_track(
        self,
        tickers: list[str],
        barrier_pct: float = 0.60,
        term_years: float = 2.0,
    ) -> dict:
        """Score a basket and register it for outcome tracking.

        Args:
            tickers: Basket tickers.
            barrier_pct: Barrier level.
            term_years: Product term in years.

        Returns:
            Score report plus tracking ID.
        """
        report = self._scorer.score_basket(tickers, barrier_pct=barrier_pct)

        entry = {
            "id": f"{'_'.join(tickers)}_{datetime.now().strftime('%Y%m%d')}",
            "tickers": tickers,
            "date_scored": datetime.now().isoformat(),
            "date_check": (datetime.now() + timedelta(days=int(term_years * 365))).isoformat(),
            "barrier_pct": barrier_pct,
            "term_years": term_years,
            "predicted_score": report.total_score,
            "predicted_grade": report.grade.value,
            "worst_of_predicted": report.worst_of_asset,
            "outcome": None,
        }
        self._pending.append(entry)
        self._save()

        return {
            "tracking_id": entry["id"],
            "score": report.total_score,
            "grade": report.grade.value,
            "worst_of": report.worst_of_asset,
            "check_date": entry["date_check"],
        }

    def check_outcomes(self) -> list[dict]:
        """Check pending baskets for resolved outcomes using market data.

        Returns:
            List of newly resolved outcomes.
        """
        resolved: list[dict] = []
        still_pending: list[dict] = []

        for entry in self._pending:
            outcome = self._check_barrier(
                entry["tickers"],
                entry["date_scored"],
                entry["barrier_pct"],
            )

            if outcome is not None:
                entry["outcome"] = outcome
                entry["date_resolved"] = datetime.now().isoformat()
                self._completed.append(entry)
                resolved.append(entry)

                self._evolution.record_outcome(
                    tickers=entry["tickers"],
                    date=entry["date_scored"],
                    autocall_triggered=(outcome == "autocall"),
                    worst_of_asset=entry.get("worst_of_actual", entry["worst_of_predicted"]),
                    predicted_score=entry["predicted_score"],
                    predicted_prob=entry["predicted_score"] / 100.0,
                )
            else:
                still_pending.append(entry)

        self._pending = still_pending
        self._save()

        if len(self._completed) >= 10:
            evo_result = self._evolution.evolve(trigger="feedback_loop")
            logger.info("Evolution triggered: %s", evo_result.get("status"))

        return resolved

    def backfill_historical(self, n_baskets: int = 50) -> dict:
        """Generate historical basket outcomes for bootstrapping evolution.

        Creates synthetic scored baskets from past 2 years of data and
        checks whether they knocked in, providing real feedback data.

        Args:
            n_baskets: Number of historical baskets to generate.

        Returns:
            Dict with count of outcomes generated.
        """
        universe = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
            "JPM", "JNJ", "V", "PG", "UNH", "HD", "MA", "DIS",
            "NFLX", "AMD", "CRM", "ADBE", "INTC",
        ]

        rng = np.random.default_rng(42)
        outcomes_recorded = 0

        for i in range(n_baskets):
            n_tickers = int(rng.choice([3, 4, 5]))
            tickers = list(rng.choice(universe, size=n_tickers, replace=False))
            barrier_pct = 0.60
            term_days = int(rng.uniform(180, 540))

            try:
                outcome, worst_asset = self._check_historical_basket(
                    tickers, term_days, barrier_pct,
                )
                if outcome is None:
                    continue

                report = self._scorer.score_basket(tickers, barrier_pct=barrier_pct)

                self._evolution.record_outcome(
                    tickers=tickers,
                    date=datetime.now().isoformat(),
                    autocall_triggered=(outcome == "autocall"),
                    worst_of_asset=worst_asset,
                    predicted_score=report.total_score,
                    predicted_prob=report.total_score / 100.0,
                )
                outcomes_recorded += 1
            except Exception as exc:
                logger.debug("Backfill basket %d failed: %s", i, exc)

        if outcomes_recorded >= 10:
            evo_result = self._evolution.evolve(trigger="backfill")
            logger.info("Post-backfill evolution: %s", evo_result.get("status"))

        self._save()
        return {
            "baskets_tested": n_baskets,
            "outcomes_recorded": outcomes_recorded,
            "evolution_weights": self._evolution.weights,
        }

    def _check_barrier(
        self,
        tickers: list[str],
        date_scored: str,
        barrier_pct: float,
    ) -> str | None:
        """Check if any ticker breached barrier since scoring date."""
        try:
            import yfinance as yf
            from datetime import datetime as dt

            scored_date = dt.fromisoformat(date_scored).date()
            days_since = (datetime.now().date() - scored_date).days
            if days_since < 30:
                return None

            for ticker in tickers:
                hist = yf.Ticker(ticker).history(start=str(scored_date))
                if hist.empty:
                    continue
                initial = float(hist["Close"].iloc[0])
                min_price = float(hist["Close"].min())
                if min_price / initial < barrier_pct:
                    return "knock_in"

            if days_since > 90:
                all_above = True
                for ticker in tickers:
                    hist = yf.Ticker(ticker).history(start=str(scored_date))
                    if hist.empty:
                        continue
                    initial = float(hist["Close"].iloc[0])
                    current = float(hist["Close"].iloc[-1])
                    if current < initial:
                        all_above = False
                if all_above:
                    return "autocall"

            return None
        except Exception:
            return None

    def _check_historical_basket(
        self,
        tickers: list[str],
        term_days: int,
        barrier_pct: float,
    ) -> tuple[str | None, str]:
        """Check historical basket outcome over a past period."""
        try:
            import yfinance as yf

            worst_asset = tickers[0]
            worst_ratio = 1.0
            knocked_in = False

            for ticker in tickers:
                hist = yf.Ticker(ticker).history(period="2y")
                if hist.empty or len(hist) < term_days:
                    return None, ""

                end_idx = min(len(hist), len(hist) - 30 + int(np.random.uniform(0, 30)))
                start_idx = max(0, end_idx - term_days)

                window = hist["Close"].iloc[start_idx:end_idx]
                if len(window) < 20:
                    return None, ""

                initial = float(window.iloc[0])
                min_price = float(window.min())
                ratio = min_price / initial

                if ratio < worst_ratio:
                    worst_ratio = ratio
                    worst_asset = ticker

                if ratio < barrier_pct:
                    knocked_in = True

            if knocked_in:
                return "knock_in", worst_asset

            all_above = True
            for ticker in tickers:
                hist = yf.Ticker(ticker).history(period="2y")
                window = hist["Close"].iloc[-term_days:]
                if float(window.iloc[-1]) < float(window.iloc[0]):
                    all_above = False
            if all_above:
                return "autocall", worst_asset

            return "hold", worst_asset
        except Exception:
            return None, ""

    def _save(self) -> None:
        try:
            FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "pending": self._pending[-200:],
                "completed": self._completed[-200:],
            }
            FEEDBACK_PATH.write_text(json.dumps(data, indent=2, default=str))
        except Exception as exc:
            logger.warning("Feedback save failed: %s", exc)

    def _load(self) -> None:
        try:
            if FEEDBACK_PATH.exists():
                data = json.loads(FEEDBACK_PATH.read_text())
                self._pending = data.get("pending", [])
                self._completed = data.get("completed", [])
        except Exception:
            pass

    def get_stats(self) -> dict:
        """Get feedback loop statistics."""
        correct = sum(
            1 for c in self._completed
            if (c["predicted_score"] >= 70) == (c["outcome"] == "autocall")
        )
        total = len(self._completed)
        return {
            "pending": len(self._pending),
            "completed": total,
            "accuracy": round(correct / total, 4) if total > 0 else 0.0,
            "current_weights": self._evolution.weights,
        }
