#!/usr/bin/env python3
"""Acquire raw Nasdaq AI-equity price candidates without pretending they are PIT.

The historical quote endpoint can revise past rows for corporate actions.
A successful retrieval is only a dated capture, not a contemporaneous
historical vintage, a certified basket, a stress score, or trading evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Research candidates predeclared from AICS official IR research roster.
# This is NOT a retrospectively validated, historical index constituency.
RESEARCH_SYMBOLS = ("NVDA", "MSFT", "GOOGL", "AMZN", "META", "ORCL", "MU")
HOST = "https://api.nasdaq.com"
MAX_BYTES = 3_000_000
MAX_ROWS = 500


def quote_url(symbol: str, start: dt.date, end: dt.date) -> str:
    if symbol not in RESEARCH_SYMBOLS or start > end:
        raise ValueError("symbol or date window is not in the research protocol")
    query = urlencode({
        "assetclass": "stocks", "fromdate": start.strftime("%m/%d/%Y"),
        "todate": end.strftime("%m/%d/%Y"), "limit": "500"
    })
    return f"{HOST}/api/quote/{symbol}/historical?{query}"


def _date(value: str) -> dt.date:
    if not isinstance(value, str):
        raise ValueError("non-text price date")
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    raise ValueError("unrecognized price date")


def _number(value, *, strictly_positive: bool) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("unsupported market value")
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    try:
        out = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError("invalid market value") from exc
    if not out.is_finite() or (out <= 0 if strictly_positive else out < 0):
        raise ValueError("out-of-range market value")
    return out


def validate_price_response(raw: bytes, start: dt.date, end: dt.date) -> dict:
    """Validate structure, dates and numeric types, NEVER historical availability."""
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("empty or oversized price response")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid JSON response") from exc
    if not isinstance(payload, dict):
        raise ValueError("provider returned an invalid envelope")
    status = payload.get("status")
    code = status.get("rCode", 200) if isinstance(status, dict) else None
    if str(code) != "200":
        label = str(code)[:8] if str(code).isdigit() else "unknown"
        raise ValueError("provider rejected request: status " + label)
    data = payload.get("data")
    table = data.get("tradesTable") if isinstance(data, dict) else None
    rows = table.get("rows") if isinstance(table, dict) else None
    if not isinstance(rows, list) or not rows or len(rows) > MAX_ROWS:
        raise ValueError("price rows missing or unreasonably large")
    dates = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("non-object price row")
        day = _date(row.get("date"))
        if day < start or day > end or day in dates:
            raise ValueError("out-of-window, future or duplicate price date")
        dates.add(day)
        _number(row.get("close"), strictly_positive=True)
        _number(row.get("volume"), strictly_positive=False)
    return {
        "rows_validated": len(rows),
        "first_observation_date": min(dates).isoformat(),
        "last_observation_date": max(dates).isoformat(),
        "provider_data_are_historically_pit_attested": False,
        "split_dividend_adjustment_verified": False,
        "score_eligible": False,
    }


def retrieve(url: str, opener=urlopen) -> bytes:
    if not url.startswith(HOST + "/api/quote/") or "/historical?" not in url:
        raise ValueError("disallowed quote URL")
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AICS-Research/1.0)",
        "Accept": "application/json",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/",
    })
    with opener(request, timeout=30) as response:
        if response.geturl() != url:
            raise ValueError("unexpected quote endpoint redirect")
        if "application/json" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("provider did not return JSON")
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("oversized provider response")
    return body


def collect(output_dir: Path, *, as_of: dt.date,
            start: dt.date | None = None, symbols=RESEARCH_SYMBOLS,
            fetcher=retrieve, clock=None) -> dict:
    now = clock() if clock is not None else dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("capture timestamp must contain a timezone")
    captured_at = now.astimezone(dt.timezone.utc)
    if as_of > captured_at.date():
        raise ValueError("future as-of is disallowed")
    start = start or (as_of - dt.timedelta(days=90))
    if start > as_of:
        raise ValueError("future date window is disallowed")
    if (not isinstance(symbols, (list, tuple)) or not symbols
            or len(set(symbols)) != len(symbols)
            or any(s not in RESEARCH_SYMBOLS for s in symbols)):
        raise ValueError("invalid research security universe")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    captured = []
    for symbol in symbols:
        url = quote_url(symbol, start, as_of)
        row = {
            "symbol": symbol, "requested_url": url,
            "candidate_node": "AI Equities",
            "requested_as_of": as_of.isoformat(),
            "retrieved_at_utc": captured_at.isoformat(),
            "status": "not_fetched", "score_eligible": False,
            "independently_attested_pit": False,
        }
        try:
            raw = fetcher(url)
            checked = validate_price_response(raw, start, as_of)
            sha = hashlib.sha256(raw).hexdigest()
            raw_path = raw_dir / f"{symbol}_{sha}.json"
            raw_dir.mkdir(parents=True, exist_ok=True)
            if raw_path.exists() and hashlib.sha256(raw_path.read_bytes()).hexdigest() != sha:
                raise ValueError("source archive was tampered with")
            if not raw_path.exists():
                raw_path.write_bytes(raw)
            row.update(checked)
            row.update(status="raw_candidate_archived_not_pit", sha256=sha,
                       raw_path=str(raw_path), bytes=len(raw))
        except (ValueError, TypeError, OSError, RuntimeError, KeyError) as exc:
            row.update(status="blocked", error_type=type(exc).__name__,
                       error_code=str(exc)[:140] if isinstance(exc, ValueError)
                       else type(exc).__name__)
        captured.append(row)
    manifest = {
        "schema_version": "aics-ai-equities-price-capture-v1",
        "research_only_universe": list(symbols),
        "requested_as_of": as_of.isoformat(),
        "retrieved_at_utc": captured_at.isoformat(),
        "candidate_node": "AI Equities",
        "provider": "Nasdaq market activity historical quotes",
        "price_adjustments_as_of_historical_date_attested": False,
        "historical_membership_attested": False,
        "independently_verified_pit": False,
        "archive_candidates": sum(x["status"] == "raw_candidate_archived_not_pit" for x in captured),
        "attempted": len(captured),
        "sources": captured,
        "node_stress_score": None,
        "index_aics": None,
        "predictive_skill_score": None,
        "promotion": "BLOCKED",
        "trades_created": False,
        "limits": [
            "Raw current retrievals cannot reconstruct historical Nasdaq response vintages.",
            "Historical split and dividend adjustments may be revised after the date.",
            "Research symbols are not independently validated point-in-time constituents.",
            "Do not change the AI Equities 1/6 progress gate without verified raw archive receipt.",
            "No score, market-model history, or investment signal is calculated."
        ]
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("aics_data/source_evidence/ai_equities_prices"))
    parser.add_argument("--as-of", type=dt.date.fromisoformat,
                        default=dt.datetime.now(dt.timezone.utc).date())
    parser.add_argument("--start", type=dt.date.fromisoformat)
    parser.add_argument("--symbol", action="append", choices=RESEARCH_SYMBOLS)
    args = parser.parse_args()
    result = collect(args.out, as_of=args.as_of, start=args.start,
                     symbols=tuple(args.symbol) if args.symbol else RESEARCH_SYMBOLS)
    print(json.dumps({
        "archived_raw_price_candidates": result["archive_candidates"],
        "attempted": result["attempted"],
        "index_aics": None, "promotion": "BLOCKED"
    }))
    return 0 if result["archive_candidates"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
