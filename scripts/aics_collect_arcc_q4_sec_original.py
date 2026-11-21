#!/usr/bin/env python3
"""Verify original SEC Feb 4 2026 ARCC 8-K Exhibit 99.1 for 2025Q4.

This source supersedes a prior missing original issuer-page shell: the
issuer website HTML is not evidence, but the SEC 8-K EX-99.1 IS evidence.
Never infer PIT for observations beyond the actual filed date + 14 days.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

SEC_BASE = "https://www.sec.gov/Archives/edgar/data/1287750/000128775026000004"
INDEX_URL = SEC_BASE + "/0001287750-26-000004-index.htm"
EXHIBIT_URL = SEC_BASE + "/arccq4-2025exhibit991.htm"
FILING_DATE = dt.date(2026, 2, 4)
AVAILABLE_AT = dt.date(2026, 2, 18)
DEFAULT_DIR = Path("aics_data/research/arcc_q4_2025_sec_original")
MAX_SOURCE_BYTES = 1_200_000

class SECOriginalError(ValueError):
    pass


def _plain(raw: bytes) -> str:
    try:
        s = raw.decode("utf-8", errors="replace")
    except Exception:
        raise SECOriginalError("could not decode SEC HTML") from None
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s).replace("\xa0", " "))


def verify_original(index_bytes: bytes, exhibit_bytes: bytes) -> dict:
    index = _plain(index_bytes)
    exhibit = _plain(exhibit_bytes)
    if (
        "0001287750-26-000004" not in index
        or not re.search(r"Filing Date\s+2026-02-04", index, flags=re.I)
        or "arccq4-2025exhibit991.htm" not in index
        or not re.search(r"EX-99[.]1", index, flags=re.I)
        or "ARES CAPITAL CORP" not in index.upper()
    ):
        raise SECOriginalError("SEC index accession, filing date or exhibit mismatch")
    pattern = (
        r"As of December 31, 2025 and 2024,.*?"
        r"loans on non-accrual status represented\s+"
        r"(?P<cost>\d+(?:\.\d+)?)%\s+of the total investments at amortized cost "
        r"\(or (?P<fair>\d+(?:\.\d+)?)% at fair value\) and "
        r"(?P<prior_cost>\d+(?:\.\d+)?)% at amortized cost "
        r"\(or (?P<prior_fair>\d+(?:\.\d+)?)% at fair value\), respectively"
    )
    matches = list(re.finditer(pattern, exhibit, flags=re.I))
    if len(matches) != 1:
        raise SECOriginalError("missing/ambiguous original Q4 2025 disclosure paragraph")
    match = matches[0]
    found = {key: match.group(key) for key in ("cost","fair","prior_cost","prior_fair")}
    if found != {"cost":"1.8", "fair":"1.2", "prior_cost":"1.7", "prior_fair":"1.0"}:
        raise SECOriginalError("source figures differ from expected SEC Q4 2025 statement")
    if "February 4, 2026" not in exhibit and "February  4, 2026" not in exhibit:
        raise SECOriginalError("source does not identify original February 4 release")
    if FILING_DATE + dt.timedelta(days=14) != AVAILABLE_AT:
        raise SECOriginalError("SEC +14 date calculation mismatch")
    return {
        "schema_version": "aics-arcc-q4-2025-sec-exhibit-original-v1",
        "entity": "ARCC",
        "period_end": "2025-12-31",
        "filing_accession": "0001287750-26-000004",
        "source": "SEC EDGAR 8-K EX-99.1 (original, not issuer-page shell)",
        "filing_date": FILING_DATE.isoformat(),
        "available_at": AVAILABLE_AT.isoformat(),
        "exhibit_url": EXHIBIT_URL,
        "sec_index_url": INDEX_URL,
        "nonaccrual_amortized_cost_pct": found["cost"],
        "nonaccrual_fair_value_pct": found["fair"],
        "prior_dec2024_cost_pct": found["prior_cost"],
        "prior_dec2024_fair_value_pct": found["prior_fair"],
        "raw_exhibit_sha256": hashlib.sha256(exhibit_bytes).hexdigest(),
        "raw_index_sha256": hashlib.sha256(index_bytes).hexdigest(),
        "raw_exhibit_bytes": len(exhibit_bytes),
        "raw_index_bytes": len(index_bytes),
        "source_values_verified_against_original_sec": True,
        "filed_at_plus_14_date_gate_passed": True,
        "independently_attested_contemporaneous_publication": False,
        "private_credit_node_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
        "note": "This original SEC accession corrects the previous insufficient Feb 2026 issuer-site HTML archive; it does not establish complete 24-month market PIT or sector scoring.",
    }


def fetch(url: str, user_agent: str,
          transport: Callable = urllib.request.urlopen) -> bytes:
    if url not in (INDEX_URL, EXHIBIT_URL):
        raise SECOriginalError("unapproved SEC source URL")
    if not user_agent or "@" not in user_agent or len(user_agent.strip()) < 15:
        raise SECOriginalError("real SEC contact user-agent required")
    request = urllib.request.Request(
        url, headers={"User-Agent":user_agent, "Accept":"text/html"}
    )
    for attempt in range(3):
        try:
            with transport(request, timeout=40) as response:
                body = response.read(MAX_SOURCE_BYTES + 1)
                response_url = response.geturl()
                ctype = response.headers.get("Content-Type", "").lower()
            if response_url != url or "text/html" not in ctype:
                raise SECOriginalError("unapproved redirect or non-HTML SEC response")
            if not body or len(body) > MAX_SOURCE_BYTES or b"<html" not in body[:7000].lower():
                raise SECOriginalError("empty, oversized or non-HTML SEC source")
            return body
        except urllib.error.HTTPError as exc:
            if exc.code not in {429,500,502,503,504} or attempt==2:
                raise
            time.sleep(attempt + 1)
    raise SECOriginalError("SEC retry exhausted")


def collect(out: Path, contact: str,
            transport: Callable = urllib.request.urlopen) -> dict:
    index = fetch(INDEX_URL, contact, transport=transport)
    exhibit = fetch(EXHIBIT_URL, contact, transport=transport)
    report = verify_original(index, exhibit)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sec_q4_index_original.html").write_bytes(index)
    (out / "sec_q4_exhibit99_1_original.html").write_bytes(exhibit)
    (out / "manifest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    contact = (os.getenv("AICS_SEC_USER_AGENT") or
               os.getenv("EDGAR_IDENTITY") or
               os.getenv("SEC_USER_AGENT") or "")
    try:
        report = collect(DEFAULT_DIR, contact)
    except (SECOriginalError, urllib.error.URLError, TimeoutError, OSError) as exc:
        print("ARCC SEC Q4 original BLOCKED:", type(exc).__name__)
        return 1
    print(json.dumps({
        "accession": report["filing_accession"],
        "SEC_14d_available_at": report["available_at"],
        "cost_nonaccrual_pct": report["nonaccrual_amortized_cost_pct"],
        "fair_value_nonaccrual_pct": report["nonaccrual_fair_value_pct"],
        "index_aics": None, "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
