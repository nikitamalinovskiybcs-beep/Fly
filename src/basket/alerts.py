"""Basket alert system — threshold-based monitoring."""

import logging
from typing import Optional

from src.basket.models import BasketReport

logger = logging.getLogger(__name__)


class BasketAlertSystem:
    """Monitor basket reports and trigger alerts."""

    THRESHOLDS = {
        "worst_of_below_barrier": 0.0,
        "near_barrier_pct": 0.05,
        "autocall_prob_drop_pp": 10.0,
        "correlation_spike": 0.85,
        "score_drop": 10.0,
    }

    def check_alerts(
        self,
        report: BasketReport,
        prev_report: Optional[BasketReport] = None,
    ) -> list[dict]:
        """Check a basket report against alert thresholds.

        Args:
            report: Current basket report.
            prev_report: Previous report for comparison.

        Returns:
            List of triggered alert dicts.
        """
        alerts: list[dict] = []

        for asset in report.assets:
            if asset.distance_to_barrier_pct is not None:
                if asset.distance_to_barrier_pct <= self.THRESHOLDS["worst_of_below_barrier"]:
                    alerts.append({
                        "level": "critical",
                        "type": "barrier_breach",
                        "ticker": asset.ticker,
                        "message": f"{asset.ticker} is at or below barrier",
                        "value": asset.distance_to_barrier_pct,
                    })
                elif asset.distance_to_barrier_pct < self.THRESHOLDS["near_barrier_pct"]:
                    alerts.append({
                        "level": "warning",
                        "type": "near_barrier",
                        "ticker": asset.ticker,
                        "message": f"{asset.ticker} within 5% of barrier",
                        "value": asset.distance_to_barrier_pct,
                    })

        if report.red_flag_count > 0:
            critical_flags = [f for f in report.red_flags if f.severity == "critical"]
            if critical_flags:
                alerts.append({
                    "level": "critical",
                    "type": "critical_red_flags",
                    "ticker": "",
                    "message": f"{len(critical_flags)} critical red flags detected",
                    "value": len(critical_flags),
                })

        if prev_report and prev_report.total_score - report.total_score > self.THRESHOLDS["score_drop"]:
            alerts.append({
                "level": "warning",
                "type": "score_drop",
                "ticker": "",
                "message": f"Score dropped from {prev_report.total_score:.1f} to {report.total_score:.1f}",
                "value": prev_report.total_score - report.total_score,
            })

        return alerts
