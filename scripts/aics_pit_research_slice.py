"""Strict research-only record isolation, adapted from supplied AICS CI v1.2.0.

This module selects records visible at a historical DATE without representing
that a present-day API response proves original historical publication or PIT.
It NEVER calculates a 0-100 stress score, market signal, or AICS index.
"""
from __future__ import annotations

import datetime as dt
import math
from collections.abc import Iterable, Mapping

SOURCE_TYPES = frozenset({"ALFRED", "SEC"})


class PITRecordError(ValueError):
    """Invalid, ambiguous or potentially look-ahead-contaminated record."""


def _date(value: object, label: str) -> dt.date:
    if not isinstance(value, str):
        raise PITRecordError(f"{label} must be an ISO calendar date")
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise PITRecordError(f"{label} must be an ISO calendar date") from None


def slice_research_records(records: Iterable[Mapping], eval_date: str) -> list[dict]:
    """Select historical candidates; output is explicitly NEVER score-eligible.

    SEC observations are delayed exactly 14 calendar days after filing;
    ALFRED observations require a source-claimed vintage covering eval_date.
    This gate does not verify whether an old vintage was actually published
    then, which requires independent original-source attestation.
    """
    cutoff = _date(eval_date, "eval_date")
    retained: dict[tuple[str, str, str, str, str], tuple[dt.date, dict]] = {}
    seen_alfred_intervals: set[tuple[str, str, str, str, str]] = set()
    if isinstance(records, (str, bytes)):
        raise PITRecordError("records must be structured observations")
    for raw in records:
        if not isinstance(raw, Mapping):
            raise PITRecordError("invalid structured observation")
        record = dict(raw)
        source = record.get("source")
        if source not in SOURCE_TYPES:
            raise PITRecordError("only SEC and ALFRED supported by this gate")
        fields = ("node_id", "metric_id", "entity", "observation_date")
        if any(not isinstance(record.get(field), str) or not record.get(field) for field in fields):
            raise PITRecordError("missing node/metric/entity/date identity")
        obs = _date(record["observation_date"], "observation_date")
        if any(record.get(flag) is True for flag in (
            "certified", "model_eligible", "independently_attested_pit")):
            raise PITRecordError("source record attempts to self-certify")
        value = record.get("value")
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value)):
            raise PITRecordError("invalid numeric research observation")
        if obs > cutoff:
            continue
        group = (source, record["node_id"], record["metric_id"],
                 record["entity"], record["observation_date"])
        if source == "SEC":
            filed = _date(record.get("filed_at"), "filed_at")
            available = _date(record.get("available_at"), "available_at")
            if available != filed + dt.timedelta(days=14):
                raise PITRecordError("SEC available_at must equal filed_at + 14 calendar days")
            if filed > cutoff or available > cutoff:
                continue
            eligible_since = available
        else:
            start = _date(record.get("realtime_start"), "realtime_start")
            end = _date(record.get("realtime_end"), "realtime_end")
            if start > end:
                raise PITRecordError("ALFRED realtime interval inverted")
            if not (start <= cutoff <= end):
                continue
            if group in seen_alfred_intervals:
                raise PITRecordError("two overlapping ALFRED vintages, fail closed")
            seen_alfred_intervals.add(group)
            eligible_since = start

        record["model_eligible"] = False
        record["independently_attested_pit"] = False
        record["record_class"] = "RESEARCH_ONLY_AS_OF_CANDIDATE"
        existing = retained.get(group)
        if existing is None or eligible_since > existing[0]:
            retained[group] = (eligible_since, record)
        elif eligible_since == existing[0]:
            raise PITRecordError("ambiguous duplicate source observation")
    return [item[1] for key, item in sorted(retained.items())]
