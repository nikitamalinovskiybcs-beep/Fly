#!/usr/bin/env python3
"""Archive ARCC primary disclosure HTML with SHA256. RESEARCH EVIDENCE ONLY.

The numeric disclosures in the research CSV were manually transcribed. Fetching
the originals here does NOT verify those numbers, certify PIT, or create scores.
No source bytes or historical prices are fabricated.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.aics_arcc_nonaccrual_monitor import read_checked

MAX_SOURCE_BYTES = 8_000_000
ALLOWED_HOSTS = frozenset(("www.sec.gov", "arcc.ares.com"))
DEFAULT_INPUT = Path("aics_data/research/arcc_primary_disclosures_2026-11-18.csv")
DEFAULT_OUTPUT = Path("aics_data/research/arcc_primary_raw")


def allowed_url(url: str) -> bool:
    try:
        u = urlsplit(url)
        return (u.scheme == "https" and u.hostname in ALLOWED_HOSTS
                and u.username is None and u.password is None
                and u.port in (None, 443) and not u.fragment)
    except ValueError:
        return False


def fetch_source(url: str, user_agent: str, opener=urlopen):
    """Fetch a bounded primary-source HTML response; reject unsafe redirects."""
    if not allowed_url(url):
        raise ValueError("source_url_not_allowlisted")
    if urlsplit(url).hostname == "www.sec.gov":
        if len(user_agent.strip()) < 15 or "@" not in user_agent:
            raise ValueError("real_sec_user_agent_required")
        agent = user_agent
    else:
        agent = user_agent or "AICS research primary source archive"
    req = Request(url, headers={"User-Agent": agent, "Accept": "text/html"})
    with opener(req, timeout=35) as response:
        final_url = response.geturl()
        if not allowed_url(final_url):
            raise ValueError("unsafe_redirect")
        content_type = response.headers.get("Content-Type", "").lower()
        if not any(mime in content_type for mime in ("text/html", "application/xhtml+xml")):
            raise ValueError("unexpected_content_type")
        body = response.read(MAX_SOURCE_BYTES + 1)
    if not body or len(body) > MAX_SOURCE_BYTES:
        raise ValueError("empty_or_oversized_payload")
    if b"<html" not in body[:4096].lower():
        raise ValueError("not_html_document")
    return body, final_url, content_type


def run(csv_path: Path, output: Path, user_agent: str, as_of: dt.date | None = None, opener=urlopen):
    as_of = as_of or dt.datetime.now(dt.timezone.utc).date()
    # Requires the original research CSV to be unpromoted, with the SEC 14-day
    # lag and all issuer identifiers already independently schema-checked.
    rows = read_checked(csv_path, as_of)
    source_rows = {}
    for r in rows:
        url = r["source_uri"]
        if not allowed_url(url):
            raise ValueError("source_url_not_allowlisted")
        source_rows.setdefault(url, []).append({
            "entity": r["entity"], "metric_id": r["metric_id"],
            "period_end": r["period_end"], "filed_at": r["filed_at"],
            "available_at": r["available_at"]})
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    for url, observations in sorted(source_rows.items()):
        entry = {"source_url": url, "referenced_observations": observations,
                 "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                 "status": "not_downloaded", "numeric_values_verified": False,
                 "independently_verified_pit": False, "score_eligible": False}
        if urlsplit(url).hostname == "www.sec.gov" and (
                len(user_agent.strip()) < 15 or "@" not in user_agent):
            entry["status"] = "blocked_missing_real_sec_user_agent"
            entries.append(entry)
            continue
        try:
            body, final_url, mime = fetch_source(url, user_agent, opener=opener)
            digest = hashlib.sha256(body).hexdigest()
            destination = output / (digest + ".html")
            if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise ValueError("existing_source_hash_mismatch")
            if not destination.exists():
                destination.write_bytes(body)
            entry.update(status="archived_raw_unverified", sha256=digest, bytes=len(body),
                         response_url=final_url, content_type=mime, raw_path=str(destination))
        except Exception as exc:
            entry.update(status="fetch_failed", error=type(exc).__name__)
        entries.append(entry)
    result = {
        "report_version": "aics-sec-raw-evidence-v1", "as_of": as_of.isoformat(),
        "input_csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "input_observation_count": len(rows),
        "unique_primary_sources": len(entries),
        "archived_sources": sum(e["status"] == "archived_raw_unverified" for e in entries),
        "sources": entries,
        "numeric_values_verified_against_raw": False,
        "independently_verified_pit": False, "private_credit_node_score": None,
        "index_aics": None, "predictive_skill_score": None,
        "promotion": "BLOCKED", "trades_created": False,
        "note": ("Archival SHA256 attests collected bytes only; historical availability "
                 "and transcribed numeric figures require separate independent verification.")
    }
    (output / "manifest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                         encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    a = p.parse_args()
    report = run(a.input, a.output, os.environ.get("AICS_SEC_USER_AGENT", ""))
    print(json.dumps({"archived_sources": report["archived_sources"],
                      "unique_sources": report["unique_primary_sources"],
                      "index_aics": None, "status": report["promotion"]}))
    return 0 if report["archived_sources"] == report["unique_primary_sources"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
