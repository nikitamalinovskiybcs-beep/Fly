"""Event calendar — earnings dates and event risk."""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class EventCalendar:
    """Track upcoming events and assess risk near observation dates."""

    def get_upcoming_events(
        self,
        tickers: list[str],
        days: int = 60,
    ) -> list[dict]:
        """Get upcoming earnings dates.

        Args:
            tickers: List of tickers.
            days: Lookahead window.

        Returns:
            List of event dicts.
        """
        events: list[dict] = []
        try:
            import yfinance as yf
            for ticker in tickers:
                cal = yf.Ticker(ticker).calendar
                if cal is None or cal.empty if hasattr(cal, 'empty') else not cal:
                    continue
                if isinstance(cal, dict):
                    for key, val in cal.items():
                        if "earnings" in key.lower() or "date" in key.lower():
                            events.append({
                                "ticker": ticker,
                                "event": key,
                                "date": str(val),
                            })
                elif hasattr(cal, "iterrows"):
                    for _, row in cal.iterrows():
                        events.append({
                            "ticker": ticker,
                            "event": str(row.name),
                            "date": str(row.values[0]) if len(row) > 0 else "",
                        })
        except Exception as exc:
            logger.warning("Event fetch failed: %s", exc)
        return events

    def event_risk_near_date(
        self,
        tickers: list[str],
        target_date: str,
        window: int = 14,
    ) -> list[dict]:
        """Check if any events fall near a target date.

        Args:
            tickers: Tickers to check.
            target_date: Target date (YYYY-MM-DD).
            window: Days before/after to flag.

        Returns:
            List of risk flags.
        """
        flags: list[dict] = []
        events = self.get_upcoming_events(tickers, days=60)

        try:
            target = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            return flags

        for event in events:
            try:
                event_date = datetime.strptime(str(event["date"])[:10], "%Y-%m-%d").date()
                gap = abs((event_date - target).days)
                if gap <= window:
                    flags.append({
                        "ticker": event["ticker"],
                        "event": event["event"],
                        "date": str(event_date),
                        "days_from_target": gap,
                        "risk": "high" if gap <= 3 else "medium",
                    })
            except (ValueError, TypeError):
                continue
        return flags
