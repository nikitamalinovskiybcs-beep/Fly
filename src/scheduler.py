"""Fly Scheduler — orchestrates daily/weekly/monthly agent runs.

Integrates:
1. PaperTradingAgent.run_daily() — daily signal generation + execution
2. BasketEvolutionAgent.evolve() — monthly weight optimization
3. Autopilot agents (#4-#8) — periodic improvement cycle
4. Storage backup — hourly local, daily cloud

Can be run as:
- CLI: python -m src.scheduler --once
- Cron: */60 * * * * cd /path/to/Fly && python -m src.scheduler --once
- Daemon: python -m src.scheduler --daemon
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
SCHEDULE_LOG = DATA_DIR / "scheduler_log.json"
NUMERAI_STATE = DATA_DIR / "numerai_submissions.json"


class FlyScheduler:
    """Central scheduler for all Fly agents."""

    DEFAULT_UNIVERSE = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "JPM", "XOM",
        "JNJ", "TSLA", "AMD", "BAC",
    ]

    def __init__(
        self,
        tickers: Optional[list[str]] = None,
        universe: Optional[list[str]] = None,
    ) -> None:
        self.tickers = tickers or ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
        self.universe = universe or self.DEFAULT_UNIVERSE
        self._log: list[dict] = []
        self._load_log()

    def run_once(self) -> dict:
        """Run all scheduled tasks for current time.

        Returns:
            Dict with results from each task.
        """
        now = datetime.now()
        results: dict = {
            "timestamp": now.isoformat(),
            "tasks_run": [],
        }

        paper_result = self._run_paper_trading()
        results["paper_trading"] = paper_result
        results["tasks_run"].append("paper_trading")

        if now.weekday() == 6:
            learning = self._run_weekly_learning()
            results["weekly_learning"] = learning
            results["tasks_run"].append("weekly_learning")

        if now.day == 1:
            evolution = self._run_monthly_evolution()
            results["monthly_evolution"] = evolution
            results["tasks_run"].append("monthly_evolution")

            basket_evo = self._run_basket_evolution()
            results["basket_evolution"] = basket_evo
            results["tasks_run"].append("basket_evolution")

        # Numerai submits are round-gated (idempotent), so it is safe to
        # attempt on every scheduled run — it no-ops within an open round.
        numerai = self._run_numerai_submission()
        if numerai.get("status") != "no_credentials":
            results["numerai"] = numerai
            results["tasks_run"].append("numerai")

        if now.hour == 0:
            agents = self._run_improvement_agents()
            results["improvement_agents"] = agents
            results["tasks_run"].append("improvement_agents")

        # Autopilot health/analysis/optimization cycle — runs every scheduled
        # tick so it is genuinely live rather than dormant.
        autopilot = self._run_autopilot()
        results["autopilot"] = autopilot
        results["tasks_run"].append("autopilot")

        # Core goal: keep the best structured product up to date.
        product = self._run_product_search()
        results["best_product"] = product
        results["tasks_run"].append("best_product")

        outcomes = self._run_outcome_tracking(product)
        results["outcomes"] = outcomes
        results["tasks_run"].append("outcomes")

        backup = self._run_backup()
        results["backup"] = backup
        results["tasks_run"].append("backup")

        self._save_run(results)
        return results

    def run_all_now(self) -> dict:
        """Force-run all tasks regardless of schedule.

        Returns:
            Combined results dict.
        """
        results: dict = {
            "timestamp": datetime.now().isoformat(),
            "forced": True,
            "tasks_run": [],
        }

        paper_result = self._run_paper_trading()
        results["paper_trading"] = paper_result
        results["tasks_run"].append("paper_trading")

        learning = self._run_weekly_learning()
        results["weekly_learning"] = learning
        results["tasks_run"].append("weekly_learning")

        evolution = self._run_monthly_evolution()
        results["monthly_evolution"] = evolution
        results["tasks_run"].append("monthly_evolution")

        basket_evo = self._run_basket_evolution()
        results["basket_evolution"] = basket_evo
        results["tasks_run"].append("basket_evolution")

        agents = self._run_improvement_agents()
        results["improvement_agents"] = agents
        results["tasks_run"].append("improvement_agents")

        autopilot = self._run_autopilot()
        results["autopilot"] = autopilot
        results["tasks_run"].append("autopilot")

        product = self._run_product_search()
        results["best_product"] = product
        results["tasks_run"].append("best_product")

        outcomes = self._run_outcome_tracking(product)
        results["outcomes"] = outcomes
        results["tasks_run"].append("outcomes")

        backup = self._run_backup()
        results["backup"] = backup
        results["tasks_run"].append("backup")

        self._save_run(results)
        return results

    def bootstrap(self, days: int = 120) -> dict:
        """Bootstrap paper trading with historical data.

        Args:
            days: Number of days to simulate.

        Returns:
            Bootstrap results including trade count and learning.
        """
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=self.tickers)
        result = agent.bootstrap_historical(days=days)
        self._save_run({"timestamp": datetime.now().isoformat(),
                        "task": "bootstrap", "result": result})
        return result

    def _run_paper_trading(self) -> dict:
        """Execute daily paper trading."""
        try:
            from src.agents.paper_trader import PaperTradingAgent
            agent = PaperTradingAgent(tickers=self.tickers)
            trades = agent.run_daily()
            stats = agent.get_stats()
            return {
                "trades_today": len(trades),
                "total_trades": stats.total_trades,
                "win_rate": stats.win_rate,
                "sharpe": stats.sharpe_ratio,
                "portfolio_value": agent.get_portfolio().total_value,
            }
        except Exception as exc:
            logger.error("Paper trading failed: %s", exc)
            return {"error": str(exc)}

    def _run_weekly_learning(self) -> dict:
        """Run weekly learning cycle."""
        try:
            from src.agents.paper_trader import PaperTradingAgent
            agent = PaperTradingAgent(tickers=self.tickers)
            insights = agent.weekly_learning()
            return {
                "insights": len(insights),
                "details": [
                    {"signal": i.description, "change": i.metric_after - i.metric_before}
                    for i in insights
                ],
            }
        except Exception as exc:
            logger.error("Weekly learning failed: %s", exc)
            return {"error": str(exc)}

    def _run_monthly_evolution(self) -> dict:
        """Run monthly weight evolution."""
        try:
            from src.agents.paper_trader import PaperTradingAgent
            agent = PaperTradingAgent(tickers=self.tickers)
            return agent.monthly_evolution()
        except Exception as exc:
            logger.error("Monthly evolution failed: %s", exc)
            return {"error": str(exc)}

    def _run_numerai_submission(
        self, feature_set: str = "small", era_stride: int = 4, force: bool = False,
    ) -> dict:
        """Train + submit to the current Numerai round (idempotent per round).

        Skips gracefully when credentials are absent. Guards against duplicate
        submissions by recording the last round submitted in NUMERAI_STATE.
        Never logs secret values.

        Args:
            feature_set: "small" | "medium" | "all".
            era_stride: Era subsampling stride for training.
            force: Re-submit even if this round was already submitted.

        Returns:
            Dict describing the outcome.
        """
        import os

        if not (os.getenv("NUMERAI_PUBLIC_ID") and os.getenv("NUMERAI_SECRET_KEY")):
            return {"status": "no_credentials"}

        try:
            from src.integrations.numerai_pipeline import _napi, run
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

        try:
            current_round = int(_napi().get_current_round())
        except Exception as exc:
            logger.warning("Numerai round lookup failed: %s", exc)
            return {"status": "error", "error": str(exc)}

        last_round = self._load_numerai_round()
        if not force and last_round == current_round:
            return {"status": "already_submitted", "round": current_round}

        try:
            result = run(feature_set=feature_set, era_stride=era_stride, do_submit=True)
            self._save_numerai_round(current_round)
            submission = result.get("submission", {})
            return {
                "status": "submitted",
                "round": current_round,
                "validation_corr": result.get("validation_corr"),
                "submission_id": submission.get("submission_id"),
            }
        except Exception as exc:
            logger.error("Numerai submission failed: %s", exc)
            return {"status": "error", "round": current_round, "error": str(exc)}

    def _load_numerai_round(self) -> Optional[int]:
        """Read the last successfully submitted Numerai round."""
        try:
            if NUMERAI_STATE.exists():
                return json.loads(NUMERAI_STATE.read_text()).get("last_round")
        except Exception:
            pass
        return None

    def _save_numerai_round(self, round_num: int) -> None:
        """Persist the last submitted Numerai round."""
        try:
            NUMERAI_STATE.parent.mkdir(parents=True, exist_ok=True)
            NUMERAI_STATE.write_text(json.dumps(
                {"last_round": round_num, "submitted_at": datetime.now().isoformat()},
                indent=2,
            ))
        except Exception as exc:
            logger.warning("Numerai state save failed: %s", exc)

    def _run_autopilot(self) -> dict:
        """Run one Autopilot cycle (health → analysis → optimize → report).

        Respects the kill switch so it never fights a manual stop.
        """
        try:
            from src.autopilot.safety import SafetySystem
            if SafetySystem().check_kill_switch():
                return {"status": "kill_switch_engaged"}
            from src.autopilot.scheduler import AutopilotScheduler
            cycle = AutopilotScheduler().run_once()
            return {
                "status": "ran",
                "health": cycle.get("health", {}),
                "insights": len(cycle.get("analysis", [])),
                "optimizations": len(cycle.get("optimization", [])),
            }
        except Exception as exc:
            logger.error("Autopilot cycle failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    def _run_product_search(self) -> dict:
        """Search the universe for the best structured product (core goal)."""
        try:
            from src.data_module import fetch_ticker_data
            from src.structured_product import find_best_structured_product
            market_data = fetch_ticker_data(self.universe)
            has_complete_real_data = all(
                market_data.get(t, {}).get(
                    "is_real",
                    market_data.get(t, {}).get("source") in {"xfinlink", "yfinance"},
                )
                for t in self.universe
            )
            if not has_complete_real_data:
                return {
                    "status": "blocked_by_evidence",
                    "best": {},
                    "n_evaluated": 0,
                    "recommendation": "",
                    "market_data_source": "estimated_or_incomplete",
                    "agents_enabled": False,
                }
            result = find_best_structured_product(
                self.universe,
                basket_size=3,
                yf_data=market_data,
            )
            best = result.get("best", {})
            return {
                "status": "ok",
                "best": best,
                "n_evaluated": result.get("n_evaluated", 0),
                "recommendation": result.get("recommendation", ""),
                "market_data_source": (
                    "live_complete" if has_complete_real_data else "estimated_or_incomplete"
                ),
                "agents_enabled": has_complete_real_data,
            }
        except Exception as exc:
            logger.error("Product search failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    def _run_outcome_tracking(self, product: dict) -> dict:
        """Issue and refresh paper notes only when the safety gate passes."""
        try:
            from src.outcome_engine import (
                PaperOutcomeTracker,
                StructuredNoteSpec,
                QUALITY_REPORT_PATH,
                build_quality_report,
                evaluate_product_safety,
                replay_historical_windows,
                simulate_stress_suite,
            )

            best = product.get("best", {})
            if not best:
                return {"status": "no_product"}
            quality_spec = StructuredNoteSpec(
                basket=list(best["basket"]),
                barrier=float(best.get("barrier", 60)) / 100.0,
                coupon_rate=float(best.get("coupon", 0.0)) / 100.0 / 4.0,
                term_months=int(best.get("tenor_months", 24)),
            )
            historical_prices = self._load_historical_prices(quality_spec.basket)
            replay = replay_historical_windows(
                historical_prices,
                quality_spec,
                window_days=max(252, quality_spec.term_months * 21),
                step_days=21,
                max_windows=50,
                predicted_p_loss=float(best.get("p_loss_pct", 0.0)) / 100.0,
            )
            tracker = PaperOutcomeTracker()
            realized_count = sum(
                1 for note in tracker.notes if note.get("status") == "realized"
            )
            quality = build_quality_report(replay, realized_count)
            QUALITY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            QUALITY_REPORT_PATH.write_text(json.dumps(quality, indent=2))
            stress = simulate_stress_suite(
                quality_spec,
                n_paths=500,
            )
            gate = evaluate_product_safety(
                best,
                stress_report=stress,
                quality_report=quality,
            )
            if not gate["passed"]:
                return {
                    "status": "blocked_by_safety_gate",
                    "gate": gate,
                    "quality": quality,
                }

            spec = quality_spec
            note_id = (
                f"paper_{datetime.now().date().isoformat()}_"
                f"{'_'.join(spec.basket)}_{int(spec.barrier * 100)}_{spec.term_months}"
            )
            tracker.open_note(
                spec,
                note_id=note_id,
                metadata={
                    "predicted_score": best.get("final_objective", 0.0),
                    "predicted_autocall_prob": best.get("p_autocall", 0.5),
                    "agent_contributions": best.get("agent_contributions", {}),
                },
            )
            refreshed = []
            for note in tracker.notes:
                if note.get("status") != "open":
                    continue
                if note.get("opened_at", "")[:10] >= datetime.now().date().isoformat():
                    continue
                prices = self._load_note_prices(note)
                if not prices:
                    continue
                state = tracker.refresh(
                    note["id"],
                    prices,
                    as_of=datetime.now().date().isoformat(),
                )
                if state.get("status") == "realized":
                    refreshed.append(tracker.apply_realized_feedback(note["id"]))
                else:
                    refreshed.append(state)
            return {
                "status": "updated",
                "safety_gate": gate,
                "quality": quality,
                "notes_checked": len(refreshed),
                "states": refreshed,
            }
        except Exception as exc:
            logger.error("Outcome tracking failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    def _load_note_prices(self, note: dict) -> dict[str, list[float]]:
        """Load prices from issue date, avoiding pre-issuance look-ahead."""
        try:
            import yfinance as yf

            prices: dict[str, list[float]] = {}
            start = note.get("opened_at", "")[:10]
            for ticker in note["spec"]["basket"]:
                history = yf.Ticker(ticker).history(start=start)
                if not history.empty and "Close" in history:
                    prices[ticker] = history["Close"].dropna().tolist()
            return prices
        except Exception as exc:
            logger.info("Paper price refresh skipped: %s", exc)
            return {}

    def _load_historical_prices(self, tickers: list[str]) -> dict[str, list[float]]:
        """Load multi-year closes for replay without inventing missing data."""
        try:
            import yfinance as yf

            prices: dict[str, list[float]] = {}
            for ticker in tickers:
                history = yf.Ticker(ticker).history(period="5y")
                if not history.empty and "Close" in history:
                    values = history["Close"].dropna().tolist()
                    if values:
                        prices[ticker] = values
            return prices
        except Exception as exc:
            logger.info("Historical replay data unavailable: %s", exc)
            return {}

    def _run_basket_evolution(self) -> dict:
        """Run basket scoring weight evolution."""
        try:
            from src.basket.evolution import BasketEvolutionAgent
            agent = BasketEvolutionAgent()
            return agent.evolve(trigger="scheduled")
        except Exception as exc:
            logger.error("Basket evolution failed: %s", exc)
            return {"error": str(exc)}

    def _run_improvement_agents(self) -> dict:
        """Run the 5 improvement agents."""
        try:
            from src.agents import run_all_agents
            return run_all_agents()
        except Exception as exc:
            logger.error("Improvement agents failed: %s", exc)
            return {"error": str(exc)}

    def _run_backup(self) -> dict:
        """Run storage backup."""
        try:
            from src.storage import Storage
            storage = Storage()
            return storage.backup()
        except Exception as exc:
            logger.info("Backup skipped: %s", exc)
            return {"status": "skipped", "reason": str(exc)}

    def _save_run(self, result: dict) -> None:
        """Log scheduler run."""
        self._log.append(result)
        try:
            SCHEDULE_LOG.parent.mkdir(parents=True, exist_ok=True)
            SCHEDULE_LOG.write_text(
                json.dumps(self._log[-100:], indent=2, default=str),
            )
        except Exception as exc:
            logger.warning("Log save failed: %s", exc)

    def _load_log(self) -> None:
        """Load scheduler log."""
        try:
            if SCHEDULE_LOG.exists():
                self._log = json.loads(SCHEDULE_LOG.read_text())
        except Exception:
            self._log = []

    def get_history(self) -> list[dict]:
        """Get scheduler run history."""
        return list(self._log)

    def run_daemon(self, interval_minutes: int = 60) -> None:
        """Run scheduler as daemon (blocking).

        Args:
            interval_minutes: Minutes between runs.
        """
        logger.info("Scheduler daemon started (interval=%dm)", interval_minutes)
        while True:
            try:
                result = self.run_once()
                logger.info("Scheduler run: %s tasks", len(result["tasks_run"]))
            except Exception as exc:
                logger.error("Scheduler error: %s", exc)
            time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description="Fly Scheduler")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--bootstrap", type=int, default=0,
                        help="Bootstrap with N days of historical data")
    parser.add_argument("--all", action="store_true", help="Force-run all tasks now")
    parser.add_argument("--numerai", action="store_true",
                        help="Train + submit to current Numerai round (idempotent)")
    parser.add_argument("--numerai-force", action="store_true",
                        help="Re-submit Numerai even if round already submitted")
    parser.add_argument("--feature-set", type=str, default="small",
                        choices=["small", "medium", "all"],
                        help="Numerai feature set size")
    parser.add_argument("--autopilot", action="store_true",
                        help="Run one Autopilot cycle now")
    parser.add_argument("--best-product", action="store_true",
                        help="Search the universe for the best structured product")
    parser.add_argument("--tickers", type=str, default="AAPL,MSFT,GOOGL,AMZN,NVDA",
                        help="Comma-separated tickers")
    parser.add_argument("--interval", type=int, default=60,
                        help="Daemon interval in minutes")
    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",")]
    scheduler = FlyScheduler(tickers=tickers)

    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except Exception:
        pass

    if args.numerai or args.numerai_force:
        print("Running Numerai submission...")
        result = scheduler._run_numerai_submission(
            feature_set=args.feature_set, force=args.numerai_force,
        )
        print(json.dumps(result, indent=2, default=str))
    elif args.autopilot:
        print("Running Autopilot cycle...")
        result = scheduler._run_autopilot()
        print(json.dumps(result, indent=2, default=str))
    elif args.best_product:
        print("Searching for best structured product...")
        result = scheduler._run_product_search()
        print(json.dumps(result, indent=2, default=str))
    elif args.bootstrap > 0:
        print(f"Bootstrapping with {args.bootstrap} days...")
        result = scheduler.bootstrap(days=args.bootstrap)
        print(json.dumps(result, indent=2, default=str))
    elif args.all:
        print("Running all tasks...")
        result = scheduler.run_all_now()
        print(json.dumps(result, indent=2, default=str))
    elif args.daemon:
        scheduler.run_daemon(interval_minutes=args.interval)
    else:
        result = scheduler.run_once()
        print(json.dumps(result, indent=2, default=str))
