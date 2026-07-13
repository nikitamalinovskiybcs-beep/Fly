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

SCHEDULE_LOG = Path("data/scheduler_log.json")
NUMERAI_STATE = Path("data/numerai_submissions.json")


class FlyScheduler:
    """Central scheduler for all Fly agents."""

    def __init__(self, tickers: Optional[list[str]] = None) -> None:
        self.tickers = tickers or ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
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
