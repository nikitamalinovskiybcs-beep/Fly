"""Ten *real acquisition waves* across the ten AICS source agents.

Each wave contacts its node's primary publishers, and for SEC issuers also
downloads original current SEC companyfacts numeric XBRL snapshots. Shared
SPV issuers are fetched again in their own wave for an actual freshness
comparison. This is NOT ten repeated fake scoring/backtesting runs.

Current SEC companyfacts are mutable consolidated API representations, not
historically preserved release vintages. All values and original raw bytes
are archived; no current capture is assigned an earlier provider receipt date.
No AICS node score, historical model skill, production weights or trading.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from decimal import Decimal

from scripts.aics_ten_node_agents import (
    NODE_TASKS, SEC_CIK, _archive, _download, require_clock, sources,
    validate_original,
)
from scripts.aics_score_reproducibility_gate import WEIGHTS

OUT = Path("aics_data/agent_runs/ten_real_collection_rounds")
ROUNDS = 10
TAGS = (
    "NetCashProvidedByUsedInOperatingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "LongTermDebtNoncurrent",
    "CashAndCashEquivalentsAtCarryingValue",
)
FORM_TYPES = frozenset(("10-Q", "10-K", "10-Q/A", "10-K/A"))
ACC = re.compile(r"^\d{10}-\d{2}-\d{6}$")
MAX_PER_TAG = 4
MAX_ROWS_PER_ISSUER = len(TAGS)*MAX_PER_TAG

def _safe_url(url):
    """Never persist API keys or user info in the report."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("Official HTTPS endpoint required")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _event(source_id, kind, round_no, attempted_at, status, **kw):
    return dict(source_id=source_id, data_kind=kind, round=round_no,
                fetched_at_utc=attempted_at.isoformat(), status=status,
                independently_historical_pit_attested=False,
                node_score_eligible=False, **kw)


def parse_companyfacts(raw, *, cik, at, sha):
    """Report actual filing-timestamped numeric XBRL facts without imputation."""
    if not isinstance(raw, bytes) or not raw or len(raw) > 16_000_000:
        raise ValueError("Invalid companyfacts source size")
    obj = json.loads(raw)
    val = obj.get("cik")
    if (isinstance(val, bool) or not isinstance(val, (int, str))
            or not str(val).isdigit() or int(val) != int(cik)):
        raise ValueError("Companyfacts issuer CIK mismatch")
    facts = obj.get("facts")
    if not isinstance(facts, dict):
        raise ValueError("Official SEC fact taxonomy missing")
    us = facts.get("us-gaap", {})
    if not isinstance(us, dict):
        raise ValueError("Official US GAAP taxonomy invalid")
    output = []
    for tag in TAGS:
        record = us.get(tag)
        if record is None:
            continue
        units = record.get("units", {}) if isinstance(record, dict) else None
        if not isinstance(units, dict):
            raise ValueError("Companyfacts units malformed")
        candidates = []
        for unit, observations in units.items():
            if not isinstance(unit, str) or not isinstance(observations, list):
                raise ValueError("Companyfacts unit observations malformed")
            for x in observations:
                if not isinstance(x, dict) or x.get("form") not in FORM_TYPES:
                    continue
                filed, period, accession = x.get("filed"), x.get("end"), x.get("accn")
                if not (isinstance(filed, str) and isinstance(period, str)
                        and isinstance(accession, str) and ACC.fullmatch(accession)):
                    continue
                filed_date, period_date = (dt.date.fromisoformat(filed),
                                           dt.date.fromisoformat(period))
                if filed_date > at.date() or period_date > at.date():
                    continue
                if isinstance(x.get("val"), bool) or not isinstance(x.get("val"), (int, float)):
                    continue
                value = x["val"]
                if not math.isfinite(value):
                    raise ValueError("Nonfinite original companyfact")
                # filing-day-plus-one is a CONSERVATIVE RESEARCH proxy, not
                # proof of original dissemination time or PIT provider receipt.
                eligible = filed_date + dt.timedelta(days=1)
                if eligible > at.date():
                    continue
                candidates.append({
                    "tag": tag, "unit": unit, "value": value,
                    "period_start": x.get("start"),
                    "period_end": period, "filed_at": filed,
                    "research_eligible_date_only_proxy": eligible.isoformat(),
                    "original_sec_accession": accession, "form": x["form"],
                    "frame": x.get("frame"),
                    "original_companyfacts_snapshot_sha256": sha,
                    "original_first_document_bytes_verified": False,
                    "retrospective_provider_pit_certified": False,
                })
        candidates.sort(key=lambda r: (r["filed_at"], r["period_end"],
                                       r["original_sec_accession"]), reverse=True)
        # Retain different periods/accessions, no inferred quarterly arithmetic.
        output.extend(candidates[:MAX_PER_TAG])
    if len(output) > MAX_ROWS_PER_ISSUER:
        raise ValueError("Unbounded numeric selection")
    return output


def collect_ten(*, out=OUT, now=None, sec_contact=None, fred_api_key=None,
                eia_api_key=None, fetcher=None, pause=None):
    """Perform 10 actual waves, 1 per AICS collector; no fake data.

    fetcher can be injected only for offline unit tests. The live default is
    the existing bounded primary-source _download. Explicit failures persist.
    """
    now = require_clock(now or dt.datetime.now(dt.timezone.utc))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    contact = (sec_contact if sec_contact is not None
               else os.getenv("AICS_SEC_USER_AGENT", "")).strip()
    fred = (fred_api_key if fred_api_key is not None
            else os.getenv("FRED_API_KEY", "")).strip()
    eia = (eia_api_key if eia_api_key is not None
           else os.getenv("EIA_API_KEY", "")).strip()
    specs = sources(now, fred_api_key=fred, eia_api_key=eia)
    fetcher = fetcher or _download
    pause = pause or (lambda: time.sleep(0.16))
    waves, attempts, numerical, raw_sources = [], [], [], {}
    xbrl_already = set()
    previous = {}
    for round_no, (node, IDs) in enumerate(NODE_TASKS.items(), 1):
        wave_attempts = []
        for source_id in IDs:
            spec = specs[source_id]
            creds = spec.get("credential")
            if creds == "sec_identity" and ("@" not in contact or len(contact) < 15):
                issue = _event(source_id, spec["format"], round_no, now,
                               "blocked_sec_identity_missing")
            elif creds == "fred_api_key" and not fred:
                issue = _event(source_id, spec["format"], round_no, now,
                               "blocked_fred_key_missing")
            elif creds == "eia_api_key" and not eia:
                issue = _event(source_id, spec["format"], round_no, now,
                               "blocked_eia_key_missing")
            else:
                try:
                    raw = fetcher(spec["url"], contact if source_id.startswith("SEC_")
                                  else "AICS-ten-waves-research/1.0")
                    evidence = validate_original(spec, raw, at=now)
                    sha, raw_path = _archive(out, source_id, raw)
                    changed = source_id in previous and previous[source_id] != sha
                    issue = _event(
                        source_id, spec["format"], round_no, now,
                        "original_archived_no_pit", raw_sha256=sha,
                        original_bytes=len(raw), raw_path=str(raw_path),
                        source_endpoint=_safe_url(spec["url"]),
                        previously_collected_in_same_run=source_id in previous,
                        changed_since_prior_wave=changed, **evidence)
                    previous[source_id] = sha
                    raw_sources[source_id] = sha
                except (ValueError, KeyError, TypeError, OSError, UnicodeError,
                        HTTPError, URLError, TimeoutError) as exc:
                    issue = _event(source_id, spec["format"], round_no, now,
                                   "source_fetch_or_validation_failed",
                                   error_type=type(exc).__name__,
                                   http_code=exc.code if isinstance(exc, HTTPError) else None)
                pause()
            attempts.append(issue)
            wave_attempts.append(issue)
            if not (source_id.startswith("SEC_") and
                    source_id not in xbrl_already and
                    creds == "sec_identity" and "@" in contact and len(contact) >= 15):
                continue
            xbrl_already.add(source_id)
            cik = SEC_CIK[source_id]
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            xbrl_id = f"XBRL_{source_id.removeprefix('SEC_')}"
            try:
                raw = fetcher(url, contact)
                sha, raw_path = _archive(out, xbrl_id, raw)
                extracted = parse_companyfacts(raw, cik=cik, at=now, sha=sha)
                issue_xbrl = _event(
                    xbrl_id, "original_sec_companyfacts_current_snapshot",
                    round_no, now, "numeric_source_archived_no_historical_pit",
                    raw_sha256=sha, original_bytes=len(raw),
                    raw_path=str(raw_path), source_endpoint=_safe_url(url),
                    real_numeric_rows_extracted=len(extracted),
                    tags_present=sorted(set(z["tag"] for z in extracted)),
                    original_data_may_be_amended_after_filing=True)
                for r in extracted:
                    numerical.append({"source_id":xbrl_id, "node_first_requested_by":node,
                                      "cik":cik, **r})
            except (ValueError, KeyError, TypeError, OSError, UnicodeError,
                    HTTPError, URLError, TimeoutError) as exc:
                issue_xbrl = _event(
                    xbrl_id, "original_sec_companyfacts_current_snapshot",
                    round_no, now, "source_fetch_or_validation_failed",
                    error_type=type(exc).__name__,
                    http_code=exc.code if isinstance(exc, HTTPError) else None)
            pause()
            attempts.append(issue_xbrl)
            wave_attempts.append(issue_xbrl)
        wave = {
            "round": round_no, "agent": node,
            "weight_unchanged": WEIGHTS[node],
            "source_assignments": len(IDs),
            "real_http_attempts": sum(x["status"] not in (
                "blocked_eia_key_missing", "blocked_fred_key_missing",
                "blocked_sec_identity_missing") for x in wave_attempts),
            "raw_sources_archived": sum(x["status"] in (
                "original_archived_no_pit",
                "numeric_source_archived_no_historical_pit") for x in wave_attempts),
            "numeric_facts_extracted": sum(
                x.get("real_numeric_rows_extracted", 0) for x in wave_attempts),
            "failures": [x["source_id"] for x in wave_attempts if
                         x["status"] not in ("original_archived_no_pit",
                                            "numeric_source_archived_no_historical_pit")],
            "research_usable_scored_node": False,
            "operations": wave_attempts,
        }
        waves.append(wave)
    if len(waves) != ROUNDS or sum(WEIGHTS.values()) != 1050:
        raise ValueError("Ten original research source waves required")
    report = {
        "schema": "aics-ten-real-source-acquisition-waves-with-companyfacts-v1",
        "captured_at_utc": now.isoformat(),
        "rounds": ROUNDS, "source_agents": len(NODE_TASKS),
        "total_http_attempts": sum(x["real_http_attempts"] for x in waves),
        "successful_http_archives": sum(x["raw_sources_archived"] for x in waves),
        "unique_original_source_ids_archived": len(raw_sources),
        "sec_companyfacts_original_snapshots_archived": sum(
            x["status"] == "numeric_source_archived_no_historical_pit"
            for x in attempts),
        "actual_numeric_facts_extracted_current_sec_snapshots": len(numerical),
        "numeric_facts_are_retro_current_sec_api_not_historical_first_document": True,
        "rounds_report": waves, "numeric_facts": numerical,
        "unavailable_source_keys": sorted(set(
            x["source_id"] for x in attempts if x["status"] not in
            ("original_archived_no_pit", "numeric_source_archived_no_historical_pit"))),
        "independently_pit_verified_node_count": 0,
        "complete_index": None, "independent_sp500_skill": None,
        "fixed_weights_total": 1050, "production_weights_changed": False,
        "trades_created": False,
    }
    (out / "ten_rounds_manifest.json").write_text(
        json.dumps({k:v for k,v in report.items() if k != "numeric_facts"},
                   ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (out / "actual_sec_xbrl_facts_unverified.json").write_text(
        json.dumps(numerical, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    x = collect_ten(out=args.out)
    print(json.dumps({
        "real_rounds": x["rounds"], "source_agents": x["source_agents"],
        "http_attempts": x["total_http_attempts"],
        "successful_raw_archive_attempts": x["successful_http_archives"],
        "companyfacts_sources": x["sec_companyfacts_original_snapshots_archived"],
        "actual_numeric_xbrl_records": x["actual_numeric_facts_extracted_current_sec_snapshots"],
        "unavailable": x["unavailable_source_keys"], "certified_full_aics": None,
    }, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
