#!/usr/bin/env python3
"""Archive and independently parse OBDC 2026 Q1–Q3 SEC 8-K EX-99.1 originals.

Live SEC filing index + source exhibit must match exact CIK, accession,
filing day, issuer and quarterly non-accrual cost/fair-value denominators.
SEC.available_at = filed_at + 14 calendar days. The originally fetched
HTML is a present-day archival copy, NOT independently attested live
historical release capture, a Private Credit node score, or 24-month OOS.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import urllib.request
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path("aics_data/research/obdc_sec_originals")
BASE = "https://www.sec.gov/Archives/edgar/data/1655888/"
SOURCES = (
    ("2026-03-31", "2026-05-06", "000165588826000034", "0001655888-26-000034", "exhibit991-obdcxpressrelea.htm", "March", "31"),
    ("2026-06-30", "2026-08-05", "000165588826000055", "0001655888-26-000055", "exhibit991-obdcxpressrelea.htm", "June", "30"),
    ("2026-09-30", "2026-11-04", "000165588826000070", "0001655888-26-000070", "exhibit991pressrelease-ann.htm", "September", "30"),
)
EXTRACT = re.compile(
    r"Investments on non[\s-]*accrual represented\s+"
    r"(?P<cost>\d+(?:\.\d+)?)\s*%\s+and\s+"
    r"(?P<fair>\d+(?:\.\d+)?)\s*%\s+of the portfolio "
    r"at cost and fair value,\s+respectively", re.I,
)
MAX_BYTES = 2_000_000


class OriginalSourceError(ValueError):
    pass


def checked_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise OriginalSourceError("invalid SEC historical date") from None


def cleaned(raw: bytes) -> str:
    if not raw or len(raw) > MAX_BYTES:
        raise OriginalSourceError("empty/oversized SEC source")
    doc = html.unescape(raw.decode("utf-8", "replace"))
    doc = re.sub(r"<script\b[^>]*>.*?</script>", " ", doc, flags=re.S | re.I)
    doc = re.sub(r"<style\b[^>]*>.*?</style>", " ", doc, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", doc))


def validate_pair(index_html: bytes, exhibit_html: bytes, spec: tuple[str, ...]) -> dict:
    period, filed, accession_path, accession_hyphen, doc, month, day = spec
    metadata = cleaned(index_html)
    exhibit = cleaned(exhibit_html)
    if (
        accession_hyphen not in metadata
        or not re.search(r"\bForm\s+8-K\b", metadata, flags=re.I)
        or not re.search(r"\bFiling Date\s+" + re.escape(filed) + r"\b", metadata, flags=re.I)
        or "0001655888" not in metadata or doc not in metadata
        or "EX-99.1" not in metadata
    ):
        raise OriginalSourceError("original SEC accession/filing date/exhibit mismatch")
    if (
        "Blue Owl Capital Corporation" not in exhibit
        or not re.search(r"Announces\s+" + month + r"\s+" + day +
                         r",\s+2026\s+Financial Results", exhibit, flags=re.I)
    ):
        raise OriginalSourceError("wrong issuer or historical quarter")
    matches = list(EXTRACT.finditer(exhibit))
    if len(matches) != 1:
        raise OriginalSourceError("missing or ambiguous original issuer non-accrual statement")
    row = matches[0]
    cost, fair = Decimal(row["cost"]), Decimal(row["fair"])
    if (not cost.is_finite() or not fair.is_finite() or
            not (0 <= cost <= 100 and 0 <= fair <= 100)):
        raise OriginalSourceError("invalid original SEC cost/fair-value nonaccrual percentage")
    # Independently checked reference values: not a substitute for matching SEC originals.
    expected = {"2026-03-31": (Decimal("2.0"), Decimal("1.0")),
                "2026-06-30": (Decimal("2.8"), Decimal("0.8")),
                "2026-09-30": (Decimal("2.9"), Decimal("0.8"))}
    if (cost, fair) != expected[period]:
        raise OriginalSourceError("changed original source numeric values; manual review needed")
    available = checked_date(filed) + dt.timedelta(days=14)
    if checked_date(period) >= checked_date(filed):
        raise OriginalSourceError("SEC period after filing")
    return {
        "issuer": "OBDC", "cik": "0001655888",
        "period_end": period, "SEC_filed_at": filed,
        "SEC_available_at": available.isoformat(), "form": "8-K",
        "accession": accession_hyphen,
        "index_url": f"{BASE}{accession_path}/{accession_hyphen}-index.htm",
        "exhibit_url": f"{BASE}{accession_path}/{doc}",
        "nonaccrual_amortized_cost_percent": str(cost),
        "nonaccrual_fair_value_percent": str(fair),
        "source_index_sha256": hashlib.sha256(index_html).hexdigest(),
        "source_exhibit_sha256": hashlib.sha256(exhibit_html).hexdigest(),
        "index_original_bytes": len(index_html), "exhibit_original_bytes": len(exhibit_html),
        "source_values_verified_against_original": True,
        "independently_contemporaneous_historical_capture": False,
        "node_score_eligible": False,
    }


def fetch_sec(url: str, user_agent: str, opener=urllib.request.urlopen) -> bytes:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != "www.sec.gov"
            or not parsed.path.startswith("/Archives/edgar/data/1655888/")
            or parsed.query or parsed.fragment or parsed.username or parsed.password
            or parsed.port not in (None, 443)):
        raise OriginalSourceError("non-allowlisted SEC original")
    if len(user_agent.strip()) < 15 or "@" not in user_agent:
        raise OriginalSourceError("identifiable SEC user agent required")
    request = urllib.request.Request(url, headers={
        "User-Agent": user_agent, "Accept": "text/html", "Accept-Encoding": "identity"
    })
    with opener(request, timeout=35) as result:
        final = urlparse(result.geturl())
        if final.hostname != "www.sec.gov" or not final.path.startswith("/Archives/edgar/data/1655888/"):
            raise OriginalSourceError("untrusted source redirect")
        mime = result.headers.get("Content-Type", "").lower()
        if "text/html" not in mime:
            raise OriginalSourceError("not original SEC HTML")
        raw = result.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES or b"<html" not in raw[:8192].lower():
        raise OriginalSourceError("invalid original SEC document bytes")
    return raw


def build(captured: dict[str, tuple[bytes, bytes]], cutoff: dt.date) -> dict:
    records = []
    for spec in SOURCES:
        period, filed, accession_path, accession, doc, month, day = spec
        index_url = f"{BASE}{accession_path}/{accession}-index.htm"
        exhibit_url = f"{BASE}{accession_path}/{doc}"
        if index_url not in captured or exhibit_url not in captured:
            raise OriginalSourceError("one or more original SEC documents absent")
        index_bytes, _ = captured[index_url]
        exhibit_bytes, _ = captured[exhibit_url]
        records.append(validate_pair(index_bytes, exhibit_bytes, spec))
    eligible = [r for r in records if checked_date(r["SEC_available_at"]) <= cutoff]
    return {
        "schema_version": "aics-obdc-sec-2026-3-quarter-original-nonaccrual-v1",
        "research_as_of": cutoff.isoformat(), "issuer": "OBDC",
        "original_sec_index_and_exhibit_pairs": 3,
        "original_sec_html_files_sha256_verified": 6,
        "verified_source_periods": records,
        "visible_periods_after_sec_14_days": eligible,
        "visible_numeric_values": len(eligible) * 2,
        "nonaccrual_cost_q1_to_q3_change_percentage_points": "0.9",
        "nonaccrual_fair_q1_to_q3_change_percentage_points": "-0.2",
        "sec_availability_lag_calendar_days": 14,
        "synthetic_financial_observations": 0,
        "provider_retroactive_originals_not_live_historical_capture": True,
        "independent_24m_oos": False,
        "sector_private_credit_coverage_complete": False,
        "private_credit_stress_score": None,
        "index_aics": None, "promotion": "BLOCKED",
        "notes": [
            "SEC 8-K exhibits are dated originals but fetched now; original live capture time is not independently archived.",
            "Only three OBDC quarters; do not extrapolate across missing dates or infer full Private Credit sector.",
            "Do not pool fair-value percentages with cost percentages or ARCC issuer denominators.",
        ],
    }


def archive_originals(cutoff: dt.date, output: Path, user_agent: str) -> dict:
    if cutoff > dt.date(2026, 11, 19):
        raise OriginalSourceError("frozen research cutoff exceeded")
    captured: dict[str, tuple[bytes, bytes]] = {}
    for period, filed, accession_path, accession, doc, month, day in SOURCES:
        idx = f"{BASE}{accession_path}/{accession}-index.htm"
        exhibit = f"{BASE}{accession_path}/{doc}"
        captured[idx] = (fetch_sec(idx, user_agent), b"")
        captured[exhibit] = (fetch_sec(exhibit, user_agent), b"")
    result = build(captured, cutoff)
    # Commit to archive only after entire set validates; never write partial files.
    output.mkdir(parents=True, exist_ok=True)
    for url, (raw, _) in captured.items():
        digest = hashlib.sha256(raw).hexdigest()
        (output / f"{digest}.html").write_bytes(raw)
    (output / "manifest.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default="2026-11-19")
    parser.add_argument("--out", type=Path, default=ROOT)
    args = parser.parse_args()
    import os
    try:
        report = archive_originals(checked_date(args.as_of), args.out,
            os.environ.get("AICS_SEC_USER_AGENT", "").strip())
    except (OriginalSourceError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "BLOCKED", "error_type": type(exc).__name__,
                          "index_aics": None}))
        return 2
    print(json.dumps({
        "original_files": report["original_sec_html_files_sha256_verified"],
        "visible_source_values": report["visible_numeric_values"],
        "independent_historical_pit": False, "index_aics": None,
        "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
