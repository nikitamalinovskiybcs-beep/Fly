"""Safety system — kill switches, bounds checks, rate limits.

Five safety levels:
1. Parametric bounds (each change <= 20% of current value)
2. Validation gate (walk-forward + PBO required)
3. Trial mode (10-trade test before confirming)
4. Kill switches (max DD, consecutive losses, Sharpe < 0)
5. Human override (file-based kill switch, Telegram STOP)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from src.autopilot.config import (
    SAFETY_LIMITS,
    TUNABLE_PARAMETERS,
    DATA_DIR,
    validate_parameter,
)

logger = logging.getLogger(__name__)

KILL_SWITCH_FILE = DATA_DIR / "KILL_SWITCH"
DEPLOY_LOG_FILE = DATA_DIR / "deploy_log.json"


class SafetySystem:
    """Kill switches and safety checks for Autopilot."""

    def check_kill_switch(self) -> bool:
        """Return True if kill switch is engaged.

        Returns:
            True if trading/optimization should stop immediately.
        """
        return KILL_SWITCH_FILE.exists()

    def engage_kill_switch(self, reason: str = "manual") -> None:
        """Create kill switch file to stop all agent activity.

        Args:
            reason: Why the kill switch was engaged.
        """
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        KILL_SWITCH_FILE.write_text(
            json.dumps({"engaged_at": datetime.now().isoformat(), "reason": reason})
        )
        logger.warning("KILL SWITCH ENGAGED: %s", reason)

    def disengage_kill_switch(self) -> None:
        """Remove kill switch file to resume agent activity."""
        if KILL_SWITCH_FILE.exists():
            KILL_SWITCH_FILE.unlink()
            logger.info("Kill switch disengaged")

    def check_max_drawdown(self, drawdown: float) -> bool:
        """Return True if drawdown is within safe limits.

        Args:
            drawdown: Current drawdown as a positive fraction (e.g. 0.15 = 15%).

        Returns:
            True if safe to continue trading.
        """
        limit = SAFETY_LIMITS["stop_trading_if_dd_exceeds"]
        if drawdown >= limit:
            logger.critical("Max DD %.1f%% >= %.1f%% limit", drawdown * 100, limit * 100)
            return False
        if drawdown >= SAFETY_LIMITS["rollback_if_dd_exceeds"]:
            logger.warning("DD %.1f%% exceeds rollback threshold", drawdown * 100)
        return True

    def check_consecutive_losses(self, recent_results: list[bool]) -> bool:
        """Return True if no dangerous loss streak.

        Args:
            recent_results: List of True (win) / False (loss) for recent trades.

        Returns:
            True if safe. False if consecutive losses exceed limit.
        """
        limit = SAFETY_LIMITS["stop_trading_if_consecutive_losses"]
        streak = 0
        for r in reversed(recent_results):
            if not r:
                streak += 1
            else:
                break
        if streak >= limit:
            logger.critical("Consecutive losses: %d >= %d limit", streak, limit)
            return False
        return True

    def check_optimization_cooldown(self) -> bool:
        """Return True if optimization is allowed (no cooldown active).

        Returns:
            True if can optimize, False if in cooldown period.
        """
        cooldown_file = DATA_DIR / "optimization_cooldown.json"
        if not cooldown_file.exists():
            return True
        try:
            data = json.loads(cooldown_file.read_text())
            cooldown_until = datetime.fromisoformat(data["until"])
            if datetime.now() < cooldown_until:
                logger.info("Optimization cooldown until %s", cooldown_until)
                return False
            cooldown_file.unlink()
            return True
        except Exception:
            return True

    def set_optimization_cooldown(self, days: int = 7) -> None:
        """Set optimization cooldown period.

        Args:
            days: Number of days to pause optimization.
        """
        until = datetime.now() + timedelta(days=days)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "optimization_cooldown.json").write_text(
            json.dumps({"until": until.isoformat(), "reason": "consecutive_rollbacks"})
        )
        logger.warning("Optimization paused for %d days", days)

    def check_change_limits(self) -> bool:
        """Return True if more changes can be deployed today.

        Returns:
            True if under the daily change limit.
        """
        log = self._load_deploy_log()
        today = datetime.now().strftime("%Y-%m-%d")
        today_changes = sum(1 for e in log if e.get("date") == today)
        limit = SAFETY_LIMITS["max_changes_per_day"]
        if today_changes >= limit:
            logger.info("Daily change limit reached: %d/%d", today_changes, limit)
            return False
        return True

    def check_weekly_limits(self) -> bool:
        """Return True if under the weekly change limit.

        Returns:
            True if under the weekly change limit.
        """
        log = self._load_deploy_log()
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        week_changes = sum(1 for e in log if e.get("date", "") >= week_ago)
        limit = SAFETY_LIMITS["max_changes_per_week"]
        return week_changes < limit

    def validate_parameter_bounds(self, name: str, value: Any) -> bool:
        """Check value is within TUNABLE_PARAMETERS bounds.

        Args:
            name: Parameter name.
            value: Proposed value.

        Returns:
            True if within bounds.
        """
        return validate_parameter(name, value)

    def validate_change_magnitude(
        self, name: str, current: float, proposed: float,
    ) -> bool:
        """Check that change is within max_change_per_day limit.

        Args:
            name: Parameter name.
            current: Current value.
            proposed: Proposed new value.

        Returns:
            True if change magnitude is acceptable.
        """
        spec = TUNABLE_PARAMETERS.get(name, {})
        max_change = spec.get("max_change_per_day")
        if max_change is None:
            return True
        return abs(proposed - current) <= max_change

    def log_deployment(self, param: str, old_val: Any, new_val: Any) -> None:
        """Record a deployment to the log file.

        Args:
            param: Parameter name.
            old_val: Previous value.
            new_val: New value.
        """
        log = self._load_deploy_log()
        log.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "parameter": param,
            "old_value": old_val,
            "new_value": new_val,
        })
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(DEPLOY_LOG_FILE, "w") as f:
            json.dump(log[-500:], f, indent=2)

    def emergency_stop(self, reason: str) -> None:
        """Stop all trading and alert.

        Args:
            reason: Why the emergency stop was triggered.
        """
        self.engage_kill_switch(reason)
        logger.critical("EMERGENCY STOP: %s", reason)

    def _load_deploy_log(self) -> list[dict]:
        """Load deployment log from disk."""
        if not DEPLOY_LOG_FILE.exists():
            return []
        try:
            return json.loads(DEPLOY_LOG_FILE.read_text())
        except Exception:
            return []
