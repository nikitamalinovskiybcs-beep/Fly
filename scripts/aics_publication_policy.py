"""Research first-publication eligibility alongside immutable legacy SEC+14.

The research dates are *candidate* dates, never independent historical PIT
attestation. Date-only SEC original filings use a conservative next-calendar-
day proxy; exact timestamps require a proven public dissemination source.
Trading-session eligibility additionally requires an explicit session calendar.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
ALLOWED_PROOF_TYPES = frozenset({"sec_public_dissemination", "original_issuer_public_release"})


@dataclass(frozen=True)
class Eligibility:
    eligible_date: str
    mode: str
    evidence_strength: str
    original_source_url: str
    independently_pit_attested: bool = False


def _date(value: str) -> dt.date:
    if not isinstance(value, str):
        raise ValueError("A source calendar date must be a string")
    return dt.date.fromisoformat(value)


def _timestamp(value: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError("A public timestamp must be a string")
    value = value.replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Naive public timestamps cannot be used")
    return parsed.astimezone(NY)


def research_eligibility(*, source_url: str, filed_at: str,
                         public_at: str | None = None,
                         public_date: str | None = None,
                         proof_type: str = "sec_filing_date_proxy") -> Eligibility:
    """Return conservative source visibility (never a certified PIT observation).

    A verified public release with exact time becomes eligible in its New York
    calendar day. With only an original SEC filing date, use next calendar day
    to avoid mistakenly claiming publication before the end of that filing day.
    An IR release may have a separate earlier first-public timestamp.
    """
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        raise ValueError("Original source must have an HTTPS provenance link")
    filed = _date(filed_at)
    if (public_at is None) == (public_date is None):
        raise ValueError("Provide exactly one of timestamp or date-only evidence")
    if public_at is not None:
        if proof_type not in ALLOWED_PROOF_TYPES:
            raise ValueError("Exact timestamps require a public dissemination proof type")
        published = _timestamp(public_at)
        if proof_type == "sec_public_dissemination" and published.date() < filed:
            raise ValueError("SEC dissemination cannot predate its filing")
        return Eligibility(published.date().isoformat(), "research_first_public",
                           "documented_public_timestamp_not_independent_pit", source_url)
    if proof_type != "sec_filing_date_proxy":
        raise ValueError("Date-only fallback only for original SEC filing dates")
    if _date(public_date) != filed:
        raise ValueError("Date-only proxy must match original SEC filed_at")
    return Eligibility((filed + dt.timedelta(days=1)).isoformat(),
                       "research_next_calendar_day_proxy",
                       "date_only_unverified_public_time", source_url)


def legacy_eligibility(*, source_url: str, filed_at: str) -> Eligibility:
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        raise ValueError("Original source must have an HTTPS provenance link")
    return Eligibility((_date(filed_at) + dt.timedelta(days=14)).isoformat(),
                       "legacy_sec_plus14", "artificial_14_day_embargo", source_url)


def first_eligible_close_session(*, source_url: str, filed_at: str,
                                 sessions: list[str], public_at: str | None = None,
                                 public_date: str | None = None,
                                 proof_type: str = "sec_filing_date_proxy") -> str:
    """Choose an actual supplied NYSE session whose 16:00 ET close is after release.

    Explicit session calendar is mandatory; no fabricated weekend/holiday
    sessions. With only date evidence, require a strictly later session.
    """
    research_eligibility(source_url=source_url, filed_at=filed_at,
                         public_at=public_at, public_date=public_date,
                         proof_type=proof_type)
    parsed = [_date(x) for x in sessions]
    if not parsed or len(set(parsed)) != len(parsed) or parsed != sorted(parsed):
        raise ValueError("Supply a sorted unique nonempty session calendar")
    for day in parsed:
        if public_at is None:
            if day > _date(public_date):
                return day.isoformat()
        elif _timestamp(public_at) < dt.datetime.combine(
                day, dt.time(16, 0), NY):
            return day.isoformat()
    raise ValueError("No eligible market-close session in supplied calendar")
