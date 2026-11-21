#!/usr/bin/env python3
"""Original SEC BXSL Q1/Q2 2026 non-accrual source archiver and exact parser.

Research-only. SEC +14 calendar-day model candidate availability; current
download DOES NOT prove contemporaneous provider-feed PIT. Fair value and
amortized cost are separate denominators. Original HTML saved with SHA-256.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import urllib.request
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from scripts.aics_collect_bxsl_original_nonaccrual import flatten

SOURCE = {
    "2026-03-31": {
        "accession": "0001213900-26-053022",
        "base": "https://www.sec.gov/Archives/edgar/data/1736035/000121390026053022/",
        "files": {
            "index": "0001213900-26-053022-index.htm",
            "filing": "ea0289403-8k_blackstone.htm",
            "exhibit": "ea0289403-01_ex991.htm",
        },
        "filed_at": "2026-05-07", "available_at": "2026-05-21",
        "quarter": "First", "press_date": "May 7, 2026",
        "cost": "4.7", "fair": "3.1",
    },
    "2026-06-30": {
        "accession": "0001213900-26-085889",
        "base": "https://www.sec.gov/Archives/edgar/data/1736035/000121390026085889/",
        "files": {
            "index": "0001213900-26-085889-index.htm",
            "filing": "ea0300654-8k_blackstone.htm",
            "exhibit": "ea0300654-01_ex991.htm",
        },
        "filed_at": "2026-08-06", "available_at": "2026-08-20",
        "quarter": "Second", "press_date": "August 6, 2026",
        "cost": "3.6", "fair": "1.8",
    },
}
OUT = Path("aics_data/research/bxsl_q1_q2_2026_sec_originals")
LIMIT = 2_000_000


class Q1Q2EvidenceError(ValueError):
    pass


def permitted(url: str) -> bool:
    try:
        u = urlsplit(url)
        return (
            u.scheme == "https" and u.hostname == "www.sec.gov"
            and u.username is None and u.password is None
            and u.port in (None, 443) and not u.query and not u.fragment
            and any(u.path == urlsplit(meta["base"] + name).path
                    for meta in SOURCE.values() for name in meta["files"].values())
        )
    except ValueError:
        return False


def fetch(url: str, agent: str, opener=urllib.request.urlopen) -> bytes:
    if not permitted(url):
        raise Q1Q2EvidenceError("unapproved SEC primary source")
    if len(agent.strip()) < 15 or "@" not in agent:
        raise Q1Q2EvidenceError("real identifiable SEC user agent required")
    req = urllib.request.Request(url, headers={
        "User-Agent": agent, "Accept": "text/html", "Accept-Encoding": "identity",
    })
    with opener(req, timeout=35) as response:
        if (not permitted(response.geturl())
                or "text/html" not in response.headers.get("Content-Type", "").lower()):
            raise Q1Q2EvidenceError("untrusted original SEC redirect or content type")
        raw = response.read(LIMIT + 1)
    if not 250 <= len(raw) <= LIMIT:
        raise Q1Q2EvidenceError("SEC original HTML empty or unexpectedly large")
    flatten(raw)
    return raw


def parse(period: str, originals: dict[str, bytes]) -> dict:
    meta = SOURCE.get(period)
    if meta is None or set(originals) != {"index", "filing", "exhibit"}:
        raise Q1Q2EvidenceError("unexpected quarter or missing original source")
    idx, form, exhibit = [flatten(originals[k]) for k in ("index", "filing", "exhibit")]
    if (meta["accession"] not in idx or "1736035" not in idx
            or "Form 8-K" not in idx
            or meta["files"]["exhibit"] not in idx
            or not re.search(r"Filing Date\s+" + re.escape(meta["filed_at"]) + r"\b", idx, re.I)):
        raise Q1Q2EvidenceError("original SEC index identity and filing date failed")
    if ("Blackstone Secured Lending Fund" not in form
            or meta["press_date"] not in form
            or "Exhibit 99.1" not in form
            or "2026" not in form):
        raise Q1Q2EvidenceError("original 8-K issuer or exhibit identity missing")
    if ("Blackstone Secured Lending Fund" not in exhibit
            or meta["quarter"] + " Quarter 2026 Results" not in exhibit):
        raise Q1Q2EvidenceError("original earnings exhibit wrong issuer or quarter")
    fair = re.findall(
        r"(\d+(?:\.\d+)?)%\s+of investments on non\s*-\s*accrual\s*\(at fair market value\)",
        exhibit, re.I,
    )
    cost = re.findall(
        r"Based on amortized cost,\s*investments on non\s*-\s*accrual represent\s+"
        r"(\d+(?:\.\d+)?)%\s+of total investments",
        exhibit, re.I,
    )
    if len(fair) != 1 or not 1 <= len(cost) <= 2 or len(set(cost)) != 1:
        raise Q1Q2EvidenceError("source original non-accrual values ambiguous")
    if not re.search(
        r"Based on non\s*-\s*accrual debt investments as a percentage\s+"
        r"(?:the|of the)\s+fair market value of total investments", exhibit, re.I,
    ):
        raise Q1Q2EvidenceError("original fair-value denominator not proven")
    if (not Decimal(cost[0]).is_finite() or not Decimal(fair[0]).is_finite()
            or Decimal(cost[0]) != Decimal(meta["cost"])
            or Decimal(fair[0]) != Decimal(meta["fair"])):
        raise Q1Q2EvidenceError("SEC source percentages changed, require manual re-review")
    if dt.date.fromisoformat(meta["available_at"]) != (
            dt.date.fromisoformat(meta["filed_at"]) + dt.timedelta(days=14)):
        raise Q1Q2EvidenceError("SEC +14 day embargo invalid")
    return {
        "period_end": period, "issuer": "BXSL", "cik": "0001736035",
        "sec_accession": meta["accession"],
        "source_filed_at": meta["filed_at"],
        "candidate_available_at": meta["available_at"],
        "nonaccrual_amortized_cost_pct": str(Decimal(cost[0])),
        "nonaccrual_fair_value_pct": str(Decimal(fair[0])),
        "cost_denominator": "amortized_cost_of_total_investments",
        "fair_denominator": "fair_market_value_of_total_investments",
        "raw_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in originals.items()},
        "raw_bytes": {k: len(v) for k, v in originals.items()},
        "source_urls": {k: meta["base"] + v for k, v in meta["files"].items()},
        "cost_footnote_occurrences": len(cost),
        "historical_release_feed_pit_attested": False,
        "source_to_score_eligible": False,
    }


def collect(destination: Path, agent: str, as_of: dt.date) -> dict:
    if as_of > dt.date(2026, 11, 19):
        raise Q1Q2EvidenceError("frozen historical research date exceeded")
    # Obtain and validate everything before persisting any candidate market data.
    records, archived = [], []
    for period, meta in SOURCE.items():
        raw = {k: fetch(meta["base"] + filename, agent) for k, filename in meta["files"].items()}
        entry = parse(period, raw)
        entry["visible_after_sec_14d"] = entry["candidate_available_at"] <= as_of.isoformat()
        entry["score_eligible"] = False
        records.append(entry)
        archived.extend((entry["raw_sha256"][k] + ".html", v) for k, v in raw.items())
    if len(records) != 2 or len({f for f, _ in archived}) != 6:
        raise Q1Q2EvidenceError("missing or duplicate original SEC documents")
    destination.mkdir(parents=True, exist_ok=True)
    for filename, raw in archived:
        (destination / filename).write_bytes(raw)
    report = {
        "schema_version": "aics-bxsl-q1-q2-original-sec-nonaccrual-v1",
        "as_of": as_of.isoformat(),
        "issuer": "BXSL", "original_8k_quarters": 2,
        "raw_original_sec_html_documents": len(archived),
        "original_reported_nonaccrual_percentages": len(records) * 2,
        "source_periods": records,
        "SEC_embargo_calendar_days": 14,
        "synthetic_financial_rows": 0,
        "historical_realtime_feed_independently_attested": False,
        "independent_24month_oos": False,
        "node_score": None, "index_aics": None, "promotion": "BLOCKED",
    }
    (destination / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    import os
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--as-of", default="2026-11-19")
    args = parser.parse_args()
    try:
        result = collect(args.out, os.environ.get("AICS_SEC_USER_AGENT", ""),
                         dt.date.fromisoformat(args.as_of))
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": type(exc).__name__}))
        return 2
    print(json.dumps({
        "verified_original_html": result["raw_original_sec_html_documents"],
        "quarters": result["original_8k_quarters"], "values": result["original_reported_nonaccrual_percentages"],
        "private_credit_node_score": None, "aics_index": None, "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
