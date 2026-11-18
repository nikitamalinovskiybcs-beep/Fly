#!/usr/bin/env python3
"""Verify BXSL Q3 2026 original SEC 8-K, index, and EX-99.1 non-accrual.

Original source contains 2.1% at fair market value and a separate
2.8% at amortized cost, disclosed in the exhibit's explanatory note.
Distinguish issuer reporting from contemporaneous archive PIT. Apply
SEC+14 calendar days (2026-11-18). No source-free backfill or AICS score.
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

OUT = "aics_data/research/bxsl_q3_2026_original_sec"
BASE = "https://www.sec.gov/Archives/edgar/data/1736035/000121390026115721/"
ACCESSION = "0001213900-26-115721"
FILLED = "2026-11-04"
PERIOD = "2026-09-30"
ORIGINAL_FILES = {
    "index": ACCESSION + "-index.htm",
    "filing": "ea0310494-8k_blackstone.htm",
    "exhibit": "ea0310494-01_ex991.htm",
}
LIMIT = 2_000_000


class BXSLError(ValueError):
    pass


def flatten(original: bytes) -> str:
    if len(original) < 250 or len(original) > LIMIT or b"<html" not in original[:8192].lower():
        raise BXSLError("missing or unexpected SEC original")
    raw = html.unescape(original.decode("utf-8", "replace"))
    raw = re.sub(r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"\s+", " ", raw)
    raw = re.sub(r"\b(\d+)\s*\.\s*(\d+)\s*%", r"\1.\2%", raw)
    return raw


def parse(index: bytes, filing: bytes, exhibit: bytes) -> dict:
    idx, form, release = (flatten(x) for x in (index, filing, exhibit))
    if (ACCESSION not in idx or ORIGINAL_FILES["exhibit"] not in idx
            or not re.search(r"Filing Date\s+2026-11-04\b", idx, flags=re.I)
            or "Form 8-K" not in idx or "1736035" not in idx):
        raise BXSLError("SEC accession, index filing date or exhibit identity wrong")
    if ("Blackstone Secured Lending Fund" not in form
            or "November 4, 2026" not in form
            or "September 30, 2026" not in form
            or "Exhibit 99.1" not in form):
        raise BXSLError("SEC 8-K does not establish right issuer, period, or exhibit")
    if ("Blackstone Secured Lending Fund" not in release
            or "Third Quarter 2026 Results" not in release):
        raise BXSLError("wrong issuer or quarter's financial results exhibit")

    fair_matches = re.findall(
        r"(\d+(?:\.\d+)?)%\s+of investments on non\s*-\s*accrual\s*\(at fair market value\)",
        release, flags=re.I,
    )
    cost_matches = re.findall(
        r"Based on amortized cost,\s*investments on non\s*-\s*accrual represent\s+"
        r"(\d+(?:\.\d+)?)%\s+of total investments",
        release, flags=re.I,
    )
    if len(fair_matches) != 1 or len(cost_matches) != 1:
        raise BXSLError(f"original fair-value or amortized-cost non-accrual definition ambiguous fair={len(fair_matches)} cost={len(cost_matches)}")
    if not re.search(
        r"Based on non\s*-\s*accrual debt investments as a percentage of the "
        r"fair market value of total investments", release, re.I
    ):
        raise BXSLError("fair-value denominator missing from original exhibit")
    fair, cost = Decimal(fair_matches[0]), Decimal(cost_matches[0])
    if (not fair.is_finite() or not cost.is_finite()
            or fair != Decimal("2.1") or cost != Decimal("2.8")):
        raise BXSLError("source values changed; original disclosure manual review needed")

    date_filed = dt.date.fromisoformat(FILLED)
    candidate = date_filed + dt.timedelta(days=14)
    return {
        "schema_version": "aics-bxsl-sec-q3-2026-original-nonaccrual-v1",
        "issuer": "BXSL", "cik": "0001736035", "accession": ACCESSION,
        "period_end": PERIOD, "sec_filed_at": FILLED,
        "sec_available_at": candidate.isoformat(),
        "source_fair_nonaccrual_pct": str(fair),
        "source_cost_nonaccrual_pct": str(cost),
        "fair_denominator": "fair_market_value_of_total_investments",
        "cost_denominator": "amortized_cost_of_total_investments",
        "raw_sec_sha256": {
            name: hashlib.sha256(source).hexdigest()
            for name, source in (("index", index), ("filing", filing), ("exhibit", exhibit))
        },
        "original_source_bytes": {
            name: len(source) for name, source in (
                ("index", index), ("filing", filing), ("exhibit", exhibit))
        },
        "source_urls": {name: BASE + file for name, file in ORIGINAL_FILES.items()},
        "original_sec_html_count": 3,
        "synthetic_financial_observations": 0,
        "historical_live_capture_pit_independently_attested": False,
        "independent_24_month_oos": False,
        "private_credit_node_score": None,
        "aics_index": None, "promotion": "BLOCKED",
        "limitations": [
            "Cost and fair percentages have separate denominators.",
            "2026 Q3 8-K source copies fetched after the date do not prove a contemporaneous archived market feed.",
            "One issuer-quarter is not a validated Private Credit stress model or sector-wide sample.",
        ],
    }


def permitted(url: str) -> bool:
    try:
        u = urlparse(url)
    except ValueError:
        return False
    return (u.scheme == "https" and u.hostname == "www.sec.gov"
            and u.path.startswith("/Archives/edgar/data/1736035/000121390026115721/")
            and not u.query and not u.fragment and u.port in (None, 443)
            and u.username is None and u.password is None)


def fetch(url: str, agent: str, opener=urllib.request.urlopen) -> bytes:
    if not permitted(url):
        raise BXSLError("non-SEC or untrusted BXSL archive source URL")
    if len(agent.strip()) < 15 or "@" not in agent:
        raise BXSLError("SEC requires an identifiable user agent")
    req = urllib.request.Request(url, headers={
        "User-Agent": agent, "Accept": "text/html", "Accept-Encoding": "identity"
    })
    with opener(req, timeout=35) as response:
        if not permitted(response.geturl()) or "text/html" not in response.headers.get("Content-Type", "").lower():
            raise BXSLError("SEC redirected to non-original or non-HTML content")
        data = response.read(LIMIT + 1)
    flatten(data)
    return data


def run(output, agent: str, asof: dt.date) -> dict:
    if asof > dt.date(2026, 11, 19):
        raise BXSLError("frozen source research date exceeded")
    raw = {name: fetch(BASE + filename, agent) for name, filename in ORIGINAL_FILES.items()}
    report = parse(raw["index"], raw["filing"], raw["exhibit"])
    report["research_as_of"] = asof.isoformat()
    report["visible_after_sec_embargo"] = asof >= dt.date.fromisoformat(report["sec_available_at"])
    report["visible_values"] = 2 if report["visible_after_sec_embargo"] else 0
    from pathlib import Path
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name, data in raw.items():
        digest = report["raw_sec_sha256"][name]
        (output / (digest + ".html")).write_bytes(data)
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    import os
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default="2026-11-19")
    p.add_argument("--out", default=OUT)
    args = p.parse_args()
    try:
        d = run(args.out, os.environ.get("AICS_SEC_USER_AGENT", ""),
                dt.date.fromisoformat(args.as_of))
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "BLOCKED", "error_type": type(exc).__name__,
                          "evidence_gate": str(exc) if isinstance(exc, BXSLError) else "source unavailable"}))
        return 2
    print(json.dumps({
        "verified_original_sec_html": d["original_sec_html_count"],
        "reported_cost_pct": d["source_cost_nonaccrual_pct"],
        "reported_fair_pct": d["source_fair_nonaccrual_pct"],
        "available_at": d["sec_available_at"],
        "AICS": None, "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
