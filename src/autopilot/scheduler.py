"""Autopilot Scheduler — runs all cycles on schedule.

Uses threading for background operation. Does not block Streamlit.
Cycles: hourly health, daily analysis, optimization, reporting, weekly deep.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional

from src.autopilot.analyzer import PerformanceAnalyzer
from src.autopilot.deployer import SafeDeployer
from src.autopilot.models import HealthStatus
from src.autopilot.monitor import SystemMonitor
from src.autopilot.optimizer import ParameterOptimizer
from src.autopilot.reporter import AutopilotReporter
from src.autopilot.safety import SafetySystem
from src.autopilot.tester import ChangeValidator

logger = logging.getLogger(__name__)

HOURLY_INTERVAL = 3600
DAILY_ANALYSIS_HOUR = 17
DAILY_OPTIMIZE_HOUR = 19
DAILY_REPORT_HOUR = 20
WEEKLY_DAY = 6  # Sunday


class AutopilotScheduler:
    """Runs all autopilot tasks on schedule in a background thread."""

    def __init__(self) -> None:
        self.monitor = SystemMonitor()
        self.analyzer = PerformanceAnalyzer()
        self.optimizer = ParameterOptimizer()
        self.tester = ChangeValidator()
        self.deployer = SafeDeployer()
        self.reporter = AutopilotReporter()
        self.safety = SafetySystem()
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._last_hourly: float = 0
        self._last_daily_analysis: str = ""
        self._last_daily_optimize: str = ""
        self._last_daily_report: str = ""
        self._last_weekly: str = ""

    def start(self) -> None:
        """Start scheduler in background thread."""
        if self.running:
            logger.warning("Scheduler already running")
            return

        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Autopilot scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        self.running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("Autopilot scheduler stopped")

    def run_once(self) -> dict:
        """Run a full cycle once (for testing or manual trigger).

        Returns:
            Dict with results from each stage.
        """
        results: dict = {}
        results["health"] = self._hourly_cycle()
        results["analysis"] = self._daily_cycle()
        results["optimization"] = self._optimization_cycle()
        results["report"] = self._report_cycle()
        return results

    def _run_loop(self) -> None:
        """Main scheduler loop — runs until stopped."""
        while self.running:
            try:
                if self.safety.check_kill_switch():
                    logger.info("Kill switch engaged, sleeping 60s")
                    time.sleep(60)
                    continue

                now = datetime.now()
                ts = time.time()

                if ts - self._last_hourly >= HOURLY_INTERVAL:
                    self._hourly_cycle()
                    self._last_hourly = ts

                today = now.strftime("%Y-%m-%d")

                if now.hour >= DAILY_ANALYSIS_HOUR and self._last_daily_analysis != today:
                    self._daily_cycle()
                    self._last_daily_analysis = today

                if now.hour >= DAILY_OPTIMIZE_HOUR and self._last_daily_optimize != today:
                    self._optimization_cycle()
                    self._last_daily_optimize = today

                if now.hour >= DAILY_REPORT_HOUR and self._last_daily_report != today:
                    self._report_cycle()
                    self._last_daily_report = today

                week_key = f"{now.isocalendar()[1]}-{now.year}"
                if now.weekday() == WEEKLY_DAY and self._last_weekly != week_key:
                    self._weekly_cycle()
                    self._last_weekly = week_key

                time.sleep(30)

            except Exception as exc:
                logger.error("Scheduler error: %s", exc, exc_info=True)
                time.sleep(60)

    def _hourly_cycle(self) -> dict:
        """Quick health check + trial mode check.

        Returns:
            Health status dict.
        """
        health = self.monitor.check_health()
        logger.info("Health: %s (Sharpe=%.2f, DD=%.1f%%)",
                     health.status.value, health.sharpe_30d, health.max_drawdown * 100)

        if health.status == HealthStatus.CRITICAL:
            self.reporter.send_alert(
                level=__import__("src.autopilot.models", fromlist=["AlertLevel"]).AlertLevel.CRITICAL,
                message=f"System CRITICAL: {[a['msg'] for a in health.alerts]}",
            )

        trial_result = self.deployer.check_trial()
        if trial_result is not None:
            logger.info("Trial result: %s accepted=%s", trial_result.parameter_name, trial_result.accepted)

        return {"status": health.status.value, "sharpe": health.sharpe_30d}

    def _daily_cycle(self) -> list[dict]:
        """Full daily analysis.

        Returns:
            List of insight summaries.
        """
        insights = self.analyzer.daily_analysis()
        logger.info("Daily analysis: %d insights", len(insights))
        return [{"category": i.category, "finding": i.finding} for i in insights]

    def _optimization_cycle(self) -> list[dict]:
        """Optimization: propose, test, deploy.

        Returns:
            List of deployment results.
        """
        if not self.monitor.is_safe_to_optimize():
            logger.info("Not safe to optimize, skipping")
            return []

        insights = self.analyzer.daily_analysis()
        proposals = self.optimizer.optimize(insights)
        results: list[dict] = []

        import numpy as np
        trades = self.monitor._load_trades()
        if len(trades) < 30:
            logger.info("Not enough trades for optimization")
            return []

        trade_returns = np.array([t.get("pnl", 0) for t in trades])

        for change in proposals:
            validated = self.tester.validate(change, trade_returns)
            if validated.status == "approved":
                result = self.deployer.deploy(validated)
                results.append({
                    "parameter": validated.parameter_name,
                    "old": validated.current_value,
                    "new": validated.proposed_value,
                    "accepted": result.accepted,
                })

        return results

    def _report_cycle(self) -> dict:
        """Generate and send daily report.

        Returns:
            Report summary dict.
        """
        trades = self.monitor._load_trades()
        equity = self.monitor._load_equity_curve().tolist()
        report = self.reporter.daily_report(trades, equity, [], [])
        return {"date": report.date, "pnl": report.pnl_today, "sharpe": report.sharpe_30d}

    def _weekly_cycle(self) -> str:
        """Weekly deep analysis and report.

        Returns:
            Weekly report string.
        """
        trades = self.monitor._load_trades()
        equity = self.monitor._load_equity_curve().tolist()
        return self.reporter.weekly_report(trades, equity)
