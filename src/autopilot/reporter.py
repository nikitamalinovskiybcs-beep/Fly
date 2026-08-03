"""Autopilot Reporter — daily/weekly reports via Telegram, JSON, Streamlit.

Channels:
- JSON log (always)
- Streamlit dashboard (always)
- Telegram Bot (optional, free)
- Email (optional)
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from src.autopilot.models import (
    AlertLevel,
    DailyReport,
    ParameterChange,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
REPORTS_DIR = DATA_DIR / "reports"


class AutopilotReporter:
    """Reports to human via multiple channels."""

    def __init__(self) -> None:
        self.telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    def daily_report(
        self,
        trades: list[dict],
        equity: list[float],
        changes: list[ParameterChange],
        alerts: list[dict],
    ) -> DailyReport:
        """Generate and distribute daily report.

        Args:
            trades: Today's trades.
            equity: Full equity curve.
            changes: Parameter changes made today.
            alerts: Alerts generated today.

        Returns:
            DailyReport dataclass.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        today_trades = [t for t in trades if t.get("date", "").startswith(today)]
        wins = sum(1 for t in today_trades if t.get("pnl", 0) > 0)
        losses = len(today_trades) - wins
        pnl_today = sum(t.get("pnl", 0) for t in today_trades)
        pnl_total = sum(t.get("pnl", 0) for t in trades)

        import numpy as np
        if len(equity) >= 30:
            recent = np.array(equity[-30:])
            rets = np.diff(recent) / (np.abs(recent[:-1]) + 1e-12)
            sharpe = float(np.mean(rets) / (np.std(rets) + 1e-12) * np.sqrt(252))
        else:
            sharpe = 0.0

        peak = max(equity) if equity else 1.0
        max_dd = (peak - equity[-1]) / peak if equity and peak > 0 else 0.0

        report = DailyReport(
            date=today,
            pnl_today=round(pnl_today, 2),
            pnl_total=round(pnl_total, 2),
            trades_today=len(today_trades),
            wins_today=wins,
            losses_today=losses,
            sharpe_30d=round(sharpe, 2),
            max_dd=round(max_dd, 4),
            changes_today=changes,
            alerts_today=alerts,
            next_actions=[],
        )

        self._save_report_json(report)

        if self.telegram_token:
            msg = self._format_daily_telegram(report)
            self._send_telegram(msg)

        return report

    def send_alert(self, level: AlertLevel, message: str) -> None:
        """Immediate alert for WARNING/CRITICAL events.

        Args:
            level: Alert severity level.
            message: Alert message.
        """
        log_msg = f"[{level.value.upper()}] {message}"
        if level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY):
            logger.critical(log_msg)
        else:
            logger.warning(log_msg)

        if self.telegram_token and level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY):
            self._send_telegram(f"ALERT {level.value.upper()}: {message}")

    def weekly_report(
        self, trades: list[dict], equity: list[float],
    ) -> str:
        """Generate weekly summary.

        Args:
            trades: All trades this week.
            equity: Full equity curve.

        Returns:
            Formatted weekly report string.
        """
        week_pnl = sum(t.get("pnl", 0) for t in trades[-50:])
        total_trades = len(trades)
        wins = sum(1 for t in trades[-50:] if t.get("pnl", 0) > 0)

        report = (
            f"Weekly Report\n"
            f"P&L: ${week_pnl:.2f}\n"
            f"Trades: {min(50, total_trades)} | Wins: {wins}\n"
            f"Equity: ${equity[-1]:.2f}" if equity else "N/A"
        )

        if self.telegram_token:
            self._send_telegram(report)

        return report

    def _format_daily_telegram(self, report: DailyReport) -> str:
        """Format daily report for Telegram.

        Args:
            report: DailyReport to format.

        Returns:
            Markdown-formatted string for Telegram.
        """
        wr = report.wins_today / report.trades_today if report.trades_today > 0 else 0
        lines = [
            f"*Fly Daily Report* - {report.date}",
            "",
            f"P&L Today: ${report.pnl_today:+.2f} | Total: ${report.pnl_total:+.2f}",
            f"Trades: {report.trades_today} ({report.wins_today}W/{report.losses_today}L)"
            f" | WR: {wr:.0%}",
            f"Sharpe 30d: {report.sharpe_30d:.2f} | Max DD: {report.max_dd:.1%}",
        ]

        if report.changes_today:
            lines.append("")
            lines.append("Changes:")
            for c in report.changes_today:
                lines.append(
                    f"  {c.parameter_name}: {c.current_value:.4f} -> "
                    f"{c.proposed_value:.4f} ({c.improvement_pct:+.1f}%)"
                )

        if report.alerts_today:
            lines.append("")
            lines.append("Alerts:")
            for a in report.alerts_today:
                lines.append(f"  [{a.get('level', 'info')}] {a.get('msg', '')}")

        return "\n".join(lines)

    def _send_telegram(self, message: str) -> None:
        """Send message via Telegram Bot API.

        Args:
            message: Text to send.
        """
        if not self.telegram_token or not self.telegram_chat_id:
            return
        try:
            import requests
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            requests.post(
                url,
                json={
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
        except Exception as exc:
            logger.warning("Telegram send failed: %s", exc)

    def _save_report_json(self, report: DailyReport) -> None:
        """Save report as JSON to disk.

        Args:
            report: DailyReport to save.
        """
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORTS_DIR / f"daily_{report.date}.json"
        data = {
            "date": report.date,
            "pnl_today": report.pnl_today,
            "pnl_total": report.pnl_total,
            "trades_today": report.trades_today,
            "wins_today": report.wins_today,
            "losses_today": report.losses_today,
            "sharpe_30d": report.sharpe_30d,
            "max_dd": report.max_dd,
        }
        path.write_text(json.dumps(data, indent=2))
