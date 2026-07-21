"""System Monitor — checks health every hour.

Reads from data files, checks all metrics, generates alerts.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.autopilot.models import HealthReport, HealthStatus, AlertLevel
from src.autopilot.safety import SafetySystem

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
TRADES_FILE = DATA_DIR / "trades_history.json"
EQUITY_FILE = DATA_DIR / "equity_curve.json"


class SystemMonitor:
    """Monitors system health every hour."""

    def __init__(self) -> None:
        self.safety = SafetySystem()

    def check_health(self) -> HealthReport:
        """Run full health check across all metrics.

        Returns:
            HealthReport with status, metrics, and alerts.
        """
        alerts: list[dict] = []
        now = datetime.now()

        sharpe = self._rolling_sharpe_30d()
        win_rate = self._win_rate_last_n(20)
        max_dd = self._current_drawdown()
        positions = self._count_open_positions()
        sig_quality = self._signal_quality()
        freshness = self._data_freshness_hours()
        disk = self._disk_usage_pct()

        status = HealthStatus.HEALTHY

        if sharpe < 0:
            alerts.append({"level": "critical", "msg": f"Sharpe 30d = {sharpe:.2f} < 0"})
            status = HealthStatus.CRITICAL
        elif sharpe < 0.5:
            alerts.append({"level": "warning", "msg": f"Sharpe 30d = {sharpe:.2f} < 0.5"})
            if status != HealthStatus.CRITICAL:
                status = HealthStatus.WARNING

        if win_rate < 0.40 and win_rate >= 0:
            alerts.append({"level": "warning", "msg": f"Win rate = {win_rate:.0%} < 40%"})
            if status == HealthStatus.HEALTHY:
                status = HealthStatus.WARNING

        if max_dd >= 0.20:
            alerts.append({"level": "critical", "msg": f"Drawdown = {max_dd:.1%} >= 20%"})
            status = HealthStatus.CRITICAL
        elif max_dd >= 0.10:
            alerts.append({"level": "warning", "msg": f"Drawdown = {max_dd:.1%} >= 10%"})
            if status == HealthStatus.HEALTHY:
                status = HealthStatus.WARNING

        if self.safety.check_kill_switch():
            status = HealthStatus.STOPPED

        return HealthReport(
            timestamp=now,
            status=status,
            sharpe_30d=sharpe,
            win_rate_20=win_rate,
            max_drawdown=max_dd,
            open_positions=positions,
            signals_quality=sig_quality,
            data_freshness_hours=freshness,
            disk_usage_pct=disk,
            alerts=alerts,
        )

    def is_safe_to_trade(self) -> bool:
        """Check all kill switches and health.

        Returns:
            True if trading is allowed.
        """
        if self.safety.check_kill_switch():
            return False
        health = self.check_health()
        return health.status not in (HealthStatus.CRITICAL, HealthStatus.STOPPED)

    def is_safe_to_optimize(self) -> bool:
        """Check optimization readiness.

        Returns:
            True if optimization is allowed.
        """
        if not self.is_safe_to_trade():
            return False
        if not self.safety.check_optimization_cooldown():
            return False
        if not self.safety.check_change_limits():
            return False
        return True

    def _rolling_sharpe_30d(self) -> float:
        """Compute rolling 30-day Sharpe from equity curve."""
        curve = self._load_equity_curve()
        if len(curve) < 5:
            return 0.0
        recent = curve[-30:] if len(curve) >= 30 else curve
        returns = np.diff(recent) / (np.abs(recent[:-1]) + 1e-12)
        if len(returns) == 0 or np.std(returns) < 1e-12:
            return 0.0
        return float(np.mean(returns) / np.std(returns) * np.sqrt(252))

    def _win_rate_last_n(self, n: int = 20) -> float:
        """Win rate of last N trades."""
        trades = self._load_trades()
        if not trades:
            return -1.0
        recent = trades[-n:]
        wins = sum(1 for t in recent if t.get("pnl", 0) > 0)
        return wins / len(recent) if recent else 0.0

    def _current_drawdown(self) -> float:
        """Current drawdown from equity peak."""
        curve = self._load_equity_curve()
        if len(curve) < 2:
            return 0.0
        peak = np.max(curve)
        if peak <= 0:
            return 0.0
        return float((peak - curve[-1]) / peak)

    def _count_open_positions(self) -> int:
        """Count open positions from positions file."""
        pos_file = DATA_DIR / "open_positions.json"
        if not pos_file.exists():
            return 0
        try:
            return len(json.loads(pos_file.read_text()))
        except Exception:
            return 0

    def _signal_quality(self) -> float:
        """Average confidence of recent signals."""
        sig_file = DATA_DIR / "recent_signals.json"
        if not sig_file.exists():
            return 0.5
        try:
            signals = json.loads(sig_file.read_text())
            if not signals:
                return 0.5
            return float(np.mean([s.get("confidence", 0.5) for s in signals[-20:]]))
        except Exception:
            return 0.5

    def _data_freshness_hours(self) -> float:
        """Hours since last data update."""
        ts_file = DATA_DIR / "last_data_update.txt"
        if not ts_file.exists():
            return 999.0
        try:
            ts = datetime.fromisoformat(ts_file.read_text().strip())
            return (datetime.now() - ts).total_seconds() / 3600
        except Exception:
            return 999.0

    def _disk_usage_pct(self) -> float:
        """Disk usage percentage."""
        try:
            st = os.statvfs("/")
            used = (st.f_blocks - st.f_bfree) / st.f_blocks
            return round(used * 100, 1)
        except Exception:
            return 0.0

    def _load_trades(self) -> list[dict]:
        """Load trades history from disk."""
        if not TRADES_FILE.exists():
            return []
        try:
            return json.loads(TRADES_FILE.read_text())
        except Exception:
            return []

    def _load_equity_curve(self) -> np.ndarray:
        """Load equity curve from disk."""
        if not EQUITY_FILE.exists():
            return np.array([100.0])
        try:
            data = json.loads(EQUITY_FILE.read_text())
            return np.array(data, dtype=float)
        except Exception:
            return np.array([100.0])
