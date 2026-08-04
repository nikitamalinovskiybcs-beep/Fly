"""Performance Analyzer — finds what works and what doesn't.

Runs daily after market close. Analyzes per-signal accuracy, per-ticker
performance, temporal patterns, regime effectiveness, and parameter staleness.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np

from src.autopilot.models import AnalysisInsight

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
TRADES_FILE = DATA_DIR / "trades_history.json"


class PerformanceAnalyzer:
    """Analyzes what works and what doesn't. Runs daily after market close."""

    def daily_analysis(self) -> list[AnalysisInsight]:
        """Run all analysis modules and return prioritized insights.

        Returns:
            List of AnalysisInsight sorted by priority (high first).
        """
        trades = self._load_trades()
        if len(trades) < 10:
            logger.info("Not enough trades (%d) for analysis", len(trades))
            return []

        insights: list[AnalysisInsight] = []
        insights.extend(self._analyze_signal_accuracy(trades))
        insights.extend(self._analyze_ticker_performance(trades))
        insights.extend(self._analyze_temporal_patterns(trades))
        insights.extend(self._analyze_regime_effectiveness(trades))
        insights.extend(self._analyze_parameter_staleness())

        priority_order = {"high": 0, "medium": 1, "low": 2}
        insights.sort(key=lambda x: priority_order.get(x.priority, 2))
        return insights

    def _analyze_signal_accuracy(self, trades: list[dict]) -> list[AnalysisInsight]:
        """Analyze win rate per signal type, split by regime.

        Args:
            trades: List of trade dicts with signal_type, regime, pnl fields.

        Returns:
            List of insights about signal accuracy.
        """
        insights: list[AnalysisInsight] = []
        by_signal: dict[str, list[dict]] = {}
        for t in trades:
            sig = t.get("signal_type", "unknown")
            by_signal.setdefault(sig, []).append(t)

        for sig, sig_trades in by_signal.items():
            if len(sig_trades) < 5:
                continue
            wins = sum(1 for t in sig_trades if t.get("pnl", 0) > 0)
            wr = wins / len(sig_trades)

            if wr < 0.45:
                insights.append(AnalysisInsight(
                    timestamp=datetime.now(), category="signal_accuracy",
                    finding=f"{sig} signal win rate = {wr:.0%} (below 45%)",
                    metric_name=f"win_rate_{sig}", metric_value=wr,
                    recommendation=f"Reduce weight for {sig} signal",
                    confidence=min(len(sig_trades) / 20, 1.0), priority="high",
                ))
            elif wr > 0.60:
                insights.append(AnalysisInsight(
                    timestamp=datetime.now(), category="signal_accuracy",
                    finding=f"{sig} signal win rate = {wr:.0%} (above 60%)",
                    metric_name=f"win_rate_{sig}", metric_value=wr,
                    recommendation=f"Increase weight for {sig} signal",
                    confidence=min(len(sig_trades) / 20, 1.0), priority="medium",
                ))

            by_regime: dict[str, list[dict]] = {}
            for t in sig_trades:
                regime = t.get("regime", "unknown")
                by_regime.setdefault(regime, []).append(t)

            regime_wrs: dict[str, float] = {}
            for regime, rtrades in by_regime.items():
                if len(rtrades) >= 3:
                    rwins = sum(1 for t in rtrades if t.get("pnl", 0) > 0)
                    regime_wrs[regime] = rwins / len(rtrades)

            if len(regime_wrs) >= 2:
                max_wr = max(regime_wrs.values())
                min_wr = min(regime_wrs.values())
                if max_wr - min_wr > 0.15:
                    worst_regime = min(regime_wrs, key=lambda k: regime_wrs[k])
                    insights.append(AnalysisInsight(
                        timestamp=datetime.now(), category="signal_accuracy",
                        finding=f"{sig}: {max_wr:.0%} vs {min_wr:.0%} across regimes",
                        metric_name=f"regime_diff_{sig}",
                        metric_value=max_wr - min_wr,
                        recommendation=f"Add regime filter: disable {sig} in {worst_regime}",
                        confidence=0.7, priority="high",
                    ))

        return insights

    def _analyze_ticker_performance(self, trades: list[dict]) -> list[AnalysisInsight]:
        """Analyze win rate and P&L per ticker.

        Args:
            trades: List of trade dicts.

        Returns:
            List of insights about ticker performance.
        """
        insights: list[AnalysisInsight] = []
        by_ticker: dict[str, list[dict]] = {}
        for t in trades:
            ticker = t.get("ticker", "unknown")
            by_ticker.setdefault(ticker, []).append(t)

        for ticker, ttrades in by_ticker.items():
            if len(ttrades) < 5:
                continue
            wins = sum(1 for t in ttrades if t.get("pnl", 0) > 0)
            wr = wins / len(ttrades)
            avg_pnl = np.mean([t.get("pnl", 0) for t in ttrades])

            if wr < 0.30 and len(ttrades) >= 10:
                insights.append(AnalysisInsight(
                    timestamp=datetime.now(), category="ticker_performance",
                    finding=f"{ticker} win rate = {wr:.0%} with {len(ttrades)} trades",
                    metric_name=f"win_rate_{ticker}", metric_value=wr,
                    recommendation=f"Consider blacklisting {ticker}",
                    confidence=min(len(ttrades) / 20, 1.0), priority="high",
                ))
            elif avg_pnl < 0:
                insights.append(AnalysisInsight(
                    timestamp=datetime.now(), category="ticker_performance",
                    finding=f"{ticker} avg P&L = ${avg_pnl:.2f} (negative)",
                    metric_name=f"avg_pnl_{ticker}", metric_value=float(avg_pnl),
                    recommendation=f"Reduce position size for {ticker}",
                    confidence=min(len(ttrades) / 15, 1.0), priority="medium",
                ))

        return insights

    def _analyze_temporal_patterns(self, trades: list[dict]) -> list[AnalysisInsight]:
        """Analyze win rate by day of week.

        Args:
            trades: List of trade dicts with entry_date field.

        Returns:
            List of insights about temporal patterns.
        """
        insights: list[AnalysisInsight] = []
        by_day: dict[str, list[dict]] = {}
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for t in trades:
            entry = t.get("entry_date", "")
            if not entry:
                continue
            try:
                dt = datetime.fromisoformat(entry)
                day_name = days[dt.weekday()] if dt.weekday() < 5 else "Weekend"
                by_day.setdefault(day_name, []).append(t)
            except Exception:
                continue

        for day, dtrades in by_day.items():
            if len(dtrades) < 3:
                continue
            wins = sum(1 for t in dtrades if t.get("pnl", 0) > 0)
            wr = wins / len(dtrades)
            if wr < 0.35:
                insights.append(AnalysisInsight(
                    timestamp=datetime.now(), category="temporal",
                    finding=f"{day} win rate = {wr:.0%} ({len(dtrades)} trades)",
                    metric_name=f"win_rate_{day}", metric_value=wr,
                    recommendation=f"Avoid trading on {day}",
                    confidence=min(len(dtrades) / 10, 1.0), priority="medium",
                ))

        return insights

    def _analyze_regime_effectiveness(self, trades: list[dict]) -> list[AnalysisInsight]:
        """Analyze Sharpe by regime at entry time.

        Args:
            trades: List of trade dicts with regime and pnl fields.

        Returns:
            List of insights about regime effectiveness.
        """
        insights: list[AnalysisInsight] = []
        by_regime: dict[str, list[float]] = {}
        for t in trades:
            regime = t.get("regime", "unknown")
            by_regime.setdefault(regime, []).append(t.get("pnl", 0.0))

        for regime, pnls in by_regime.items():
            if len(pnls) < 5:
                continue
            arr = np.array(pnls)
            sharpe = float(arr.mean() / (arr.std() + 1e-12) * np.sqrt(252))
            if sharpe < 0:
                insights.append(AnalysisInsight(
                    timestamp=datetime.now(), category="regime",
                    finding=f"Sharpe in {regime} regime = {sharpe:.2f} (negative)",
                    metric_name=f"sharpe_{regime}", metric_value=sharpe,
                    recommendation=f"Disable trading in {regime} regime",
                    confidence=min(len(pnls) / 20, 1.0), priority="high",
                ))

        return insights

    def _analyze_parameter_staleness(self) -> list[AnalysisInsight]:
        """Check when each parameter was last optimized.

        Returns:
            List of insights about stale parameters.
        """
        insights: list[AnalysisInsight] = []
        staleness_file = DATA_DIR / "parameter_last_optimized.json"
        if not staleness_file.exists():
            return insights

        try:
            data = json.loads(staleness_file.read_text())
        except Exception:
            return insights

        now = datetime.now()
        for param, last_opt in data.items():
            try:
                dt = datetime.fromisoformat(last_opt)
                days_ago = (now - dt).days
                if days_ago > 60:
                    insights.append(AnalysisInsight(
                        timestamp=now, category="staleness",
                        finding=f"{param} last optimized {days_ago} days ago",
                        metric_name=f"staleness_{param}", metric_value=float(days_ago),
                        recommendation=f"Re-optimize {param}",
                        confidence=0.8, priority="low",
                    ))
            except Exception:
                continue

        return insights

    def _load_trades(self) -> list[dict]:
        """Load trades from disk."""
        if not TRADES_FILE.exists():
            return []
        try:
            return json.loads(TRADES_FILE.read_text())
        except Exception:
            return []
