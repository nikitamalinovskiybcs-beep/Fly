#!/usr/bin/env python3
"""FRED/ALFRED real-time request day anchored to the St Louis calendar.

The upstream FRED API uses the US central calendar date for its 'today'
bound; UTC has already rolled over during the US afternoon. We never request
a future vintage or backdate economic observations to repair missing data.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo


def fred_realtime_day(clock: dt.datetime) -> dt.date:
    if not isinstance(clock, dt.datetime) or clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("An offset-aware clock is required")
    utc_day = clock.astimezone(dt.timezone.utc).date()
    st_louis_day = clock.astimezone(ZoneInfo("America/Chicago")).date()
    return min(utc_day, st_louis_day)
