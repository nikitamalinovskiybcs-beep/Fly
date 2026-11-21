"""Ten deterministic AICS source-monitor agents with shared primary-source archive.

Research only: capture present-day source bytes, retain provenance and failures.
This cannot create historical PIT evidence, numeric AICS scores or trades.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.aics_score_reproducibility_gate import WEIGHTS

NODE_TASKS = {
    "Private Credit": ("SEC_ARCC", "SEC_BXSL", "SEC_OBDC"),
    "Insurers": ("SEC_PRU", "SEC_MET"),
    "UST 30Y": ("ALFRED_DGS30",),
    "Neoclouds": ("SEC_CRWV", "SEC_NBIS"),
    "Hyperscalers": ("SEC_MSFT", "SEC_AMZN", "SEC_GOOG", "SEC_META"),
    "SPV": ("SEC_CRWV", "SEC_NBIS"),
    "Repo": ("NYFED_SOFR", "ALFRED_IORB"),
    "Power/Data Centers": ("SEC_APLD", "EIA_CATALOG"),
    "Semiconductors Supply": ("FED_G17", "SEC_NVDA", "SEC_MU"),
    "AI Demand": ("SEC_AVGO",),
}
SEC_CIK = {
    "SEC_ARCC": "0001287750", "SEC_BXSL": "0001736035",
    "SEC_OBDC": "0001655888", "SEC_PRU": "0001137774",
    "SEC_MET": "0001099219", "SEC_CRWV": "0001769628",
    "SEC_NBIS": "0001513845", "SEC_MSFT": "0000789019",
    "SEC_AMZN": "0001018724", "SEC_GOOG": "0001652044",
    "SEC_META": "0001326801", "SEC_APLD": "0001144879",
    "SEC_NVDA": "0001045810", "SEC_MU": "0000723125",
    "SEC_AVGO": "0001730168",
}
NON_SEC = ("ALFRED_DGS30", "ALFRED_IORB", "NYFED_SOFR",
           "EIA_CATALOG", "FED_G17")
MAX_BYTES = 16_000_000
RAW_SUBDIR = "raw"
RESEARCH_NODES = frozenset(NODE_TASKS)
assert len(NODE_TASKS) == 10
assert set(WEIGHTS) - RESEARCH_NODES == {"AI Equities"}
assert sum(WEIGHTS.values()) == 1050


def require_clock(now):
    if not isinstance(now, dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Collection timestamp must be timezone aware")
    return now.astimezone(dt.timezone.utc)


def sources(now, *, fred_api_key=None):
    """Only allow finite, explicitly enumerated original publisher endpoints."""
    now = require_clock(now)
    date = now.date().isoformat()
    specs = {}
    for key, cik in SEC_CIK.items():
        specs[key] = {
            "url": f"https://data.sec.gov/submissions/CIK{cik}.json",
            "format": "sec_submissions_current",
            "cik": cik,
            "credential": "sec_identity",
        }
    for key, series in (("ALFRED_DGS30", "DGS30"), ("ALFRED_IORB", "IORB")):
        params = {
            "series_id": series, "file_type": "json",
            "realtime_start": date, "realtime_end": date,
            "observation_start": (now.date() - dt.timedelta(days=40)).isoformat(),
            "observation_end": date, "limit": "500",
            "api_key": fred_api_key or "",
        }
        specs[key] = {
            "url": "https://api.stlouisfed.org/fred/series/observations?" + urlencode(params),
            "format": "fred_current_vintage_not_historical_replay",
            "series": series, "credential": "fred_api_key",
        }
    specs["NYFED_SOFR"] = {
        "url": "https://markets.newyorkfed.org/api/rates/secured/sofr/last/20.json",
        "format": "nyfed_current_historical_values_not_vintage",
    }
    specs["EIA_CATALOG"] = {
        "url": "https://api.eia.gov/v2/",
        "format": "eia_api_catalog_not_dc_metric",
    }
    specs["FED_G17"] = {
        "url": "https://www.federalreserve.gov/releases/g17/current/default.htm",
        "format": "fed_g17_current_html_not_release_vintage",
    }
    assert len(specs) == 20
    assert set(specs) == {s for seq in NODE_TASKS.values() for s in seq}
    return specs


def _download(url, user_agent):
    """Network transport is injectable in tests; only fixed approved URLs above."""
    req = Request(url, headers={"User-Agent": user_agent, "Accept": "*/*"})
    with urlopen(req, timeout=35) as response:
        if response.geturl() != url:
            raise ValueError("Unexpected source redirect")
        raw = response.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Empty or oversized source response")
    return raw


def validate_original(spec, raw, *, at):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ValueError("Invalid original source bytes")
    kind = spec["format"]
    if kind == "fed_g17_current_html_not_release_vintage":
        sample = raw[:4096].lower()
        if b"<html" not in sample and b"<!doctype html" not in sample:
            raise ValueError("Expected original Federal Reserve HTML release")
        return {"source_structure": "html_received_unverified"}
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Expected original publisher JSON object")
    if kind == "sec_submissions_current":
        # SEC submission JSON may publish the CIK as a zero-padded string,
        # whereas other endpoints return a JSON integer. Identity is numeric.
        cik = obj.get("cik")
        if (isinstance(cik, bool) or not isinstance(cik, (int, str))
                or not str(cik).isdigit() or int(cik) != int(spec["cik"])):
            raise ValueError("SEC CIK mismatches original source")
        recent = obj.get("filings", {}).get("recent", {})
        if not isinstance(recent, dict):
            raise ValueError("No SEC recent filing metadata")
        required = ("form", "filingDate", "accessionNumber")
        if any(not isinstance(recent.get(k), list) for k in required):
            raise ValueError("SEC filing arrays missing")
        if len({len(recent[k]) for k in required}) != 1:
            raise ValueError("SEC metadata columns mismatch")
        return {"source_structure": "submissions_json_only",
                "reported_recent_filing_rows": len(recent["form"])}
    if kind == "fred_current_vintage_not_historical_replay":
        rows = obj.get("observations")
        if not isinstance(rows, list):
            raise ValueError("Original FRED observation list missing")
        for item in rows:
            if item["date"] > at.date().isoformat():
                raise ValueError("Future-dated observation")
            if item.get("realtime_start") > at.date().isoformat():
                raise ValueError("Future vintage")
        return {"source_structure": "fred_current_vintage",
                "reported_rows": len(rows)}
    if kind == "nyfed_current_historical_values_not_vintage":
        rows = obj.get("refRates")
        if not isinstance(rows, list):
            raise ValueError("Original NY Fed reference rates missing")
        for item in rows:
            if item.get("effectiveDate", "9999") > at.date().isoformat():
                raise ValueError("Future NY Fed observation")
            if item.get("type") != "SOFR":
                raise ValueError("Unexpected NY Fed rate type")
        return {"source_structure": "nyfed_current_json", "reported_rows": len(rows)}
    if kind == "eia_api_catalog_not_dc_metric":
        if not isinstance(obj.get("response"), dict):
            raise ValueError("EIA metadata response missing")
        return {"source_structure": "eia_catalog_only"}
    raise ValueError("Unrecognized original publisher")


def _archive(out, source_id, raw):
    digest = hashlib.sha256(raw).hexdigest()
    path = out / RAW_SUBDIR / f"{source_id}_{digest}.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("Conflicting content-addressed original bytes")
    else:
        path.write_bytes(raw)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("Archived original failed SHA-256 recheck")
    return digest, path


def collect(*, out=Path("aics_data/agent_runs"), now=None, contact=None,
            fred_api_key=None, transport=_download, live=False):
    """Collect once per source; mocked/offline mode makes no network requests.

    All ten node agents are reported regardless of source availability. A
    source is never called twice just because several nodes use it.
    """
    now = require_clock(now or dt.datetime.now(dt.timezone.utc))
    out = Path(out)
    contact = (contact if contact is not None
               else os.environ.get("AICS_SEC_USER_AGENT", "")).strip()
    fred_api_key = (fred_api_key if fred_api_key is not None
                    else os.environ.get("FRED_API_KEY", "")).strip()
    specs = sources(now, fred_api_key=fred_api_key)
    reused = {}
    for node in NODE_TASKS:
        for source_id in NODE_TASKS[node]:
            if source_id in reused:
                continue
            spec = specs[source_id]
            item = {"source_id": source_id, "format": spec["format"],
                    "publisher_url": spec["url"].split("api_key=")[0] if
                    "api_key=" in spec["url"] else spec["url"],
                    "captured_at_utc": now.isoformat(),
                    "historical_provider_pit_attested": False,
                    "score_eligible": False, "status": "not_attempted"}
            if not live:
                item["status"] = "offline_no_network"
            elif spec.get("credential") == "sec_identity" and (
                    "@" not in contact or len(contact) < 15):
                item["status"] = "blocked_sec_contact_missing"
            elif spec.get("credential") == "fred_api_key" and not fred_api_key:
                item["status"] = "blocked_fred_api_key_missing"
            else:
                try:
                    # Avoid credential echo in stored output or exception text.
                    raw = transport(spec["url"], contact if source_id.startswith("SEC_")
                                    else "AICS primary-source research/1.0")
                    evidence = validate_original(spec, raw, at=now)
                    sha, saved = _archive(out, source_id, raw)
                    item.update(status="archived_current_original_not_pit",
                                raw_sha256=sha, raw_bytes=len(raw),
                                raw_path=str(saved), **evidence)
                except (HTTPError, URLError, TimeoutError, ValueError, KeyError,
                        TypeError, OSError, UnicodeError) as exc:
                    # Restricted diagnostic vocabulary, never log API keys/URLs.
                    known_errors = {
                        "Unexpected source redirect": "unapproved_http_redirect",
                        "SEC CIK mismatches original source": "sec_cik_mismatch",
                        "No SEC recent filing metadata": "sec_recent_missing",
                        "SEC filing arrays missing": "sec_fields_missing",
                        "SEC metadata columns mismatch": "sec_field_lengths",
                        "Empty or oversized source response": "empty_or_oversized",
                        "Original FRED observation list missing": "fred_observations_missing",
                        "EIA metadata response missing": "eia_catalog_structure",
                        "Invalid original source bytes": "invalid_response_bytes",
                    }
                    item.update(status="blocked_source_fetch_or_validation",
                                error_class=type(exc).__name__,
                                error_code=(f"http_{exc.code}" if isinstance(exc, HTTPError)
                                            else known_errors.get(str(exc), "other_validation_error")))
            reused[source_id] = item
    agents = []
    for node, source_ids in NODE_TASKS.items():
        retrieved = [s for s in source_ids
                     if reused[s]["status"] == "archived_current_original_not_pit"]
        agents.append({
            "node": node, "weight": WEIGHTS[node], "source_ids": list(source_ids),
            "sources_total": len(source_ids), "sources_archived": len(retrieved),
            "status": ("captured_current_unverified" if len(retrieved) == len(source_ids)
                       else "partial_capture" if retrieved else "blocked_or_offline"),
            "stress_score": None, "model_updated": False,
        })
    report = {
        "schema": "aics-ten-agents-current-source-collector-v1",
        "captured_at_utc": now.isoformat(), "live_attempted": bool(live),
        "agent_count": len(agents), "source_tasks": sum(len(x) for x in NODE_TASKS.values()),
        "unique_publisher_sources": len(reused),
        "deduplicated_source_calls": sum(map(len, NODE_TASKS.values())) - len(reused),
        "original_sources_archived": sum(
            r["status"] == "archived_current_original_not_pit" for r in reused.values()),
        "agents": agents, "sources": list(reused.values()),
        "ai_equities": "separate_existing_price_capture_and_PIT_corporate_action_gate",
        "current_download_not_historical_pit": True,
        "independently_verified_node_scores": 0, "index_aics": None,
        "model_predictive_accuracy": None, "production_weights_changed": False,
        "hot_node_multiplier_applied": False, "trades_created": False,
        "limitations": [
            "SEC submissions only locate filings, not audited financial line items",
            "ALFRED query is a current as-of snapshot and not historical provider tape",
            "EIA endpoint is an API catalog, not data-center grid constraints",
            "Fed G17 current HTML is not an archived release vintage",
            "New capture must be parsed and independently audited before any score promotion",
        ],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live", action="store_true")
    p.add_argument("--out", type=Path, default=Path("aics_data/agent_runs"))
    args = p.parse_args()
    data = collect(out=args.out, live=args.live)
    print(json.dumps({
        "agents": data["agent_count"],
        "unique_sources": data["unique_publisher_sources"],
        "archives": data["original_sources_archived"],
        "mode": "live_current_capture" if args.live else "offline_inventory",
        "index_aics": None, "trades_created": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
