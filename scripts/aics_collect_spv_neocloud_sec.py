#!/usr/bin/env python3
"""Archive official SEC filings for AICS SPV/Neoclouds, without inventing a score.

The registry lists fixed, source-linked SEC documents (including foreign-issuer
6-K exhibits). Original SEC filing HTML is downloaded ONLY after the AICS
filed_at + 14 calendar day gate. All bytes are retained with SHA256, issuer,
accession and retrieval timestamp.

This program does not extract numeric market data, label a proxy as SPV
exposure, or attest historical PIT snapshots; index and skills stay N/A.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_REGISTRY = Path("aics_data/source_registry/sec_spv_neoclouds_filings_2026-11-18.json")
DEFAULT_OUT = Path("aics_data/source_evidence/sec_spv_neoclouds")
ISSUER_CIKS = {
    "Nebius Group": "0001513845",
    "Equinix": "0001101239",
    "Applied Digital": "0001144879",
    "CoreWeave": "0001769628",
}
ALLOWED_NODES = frozenset({"SPV", "Neoclouds"})
ALLOWED_FORMS = frozenset({"6-K", "10-K", "10-Q", "8-K", "20-F"})
MAX_BYTES = 15_000_000


def sec_url_check(source: dict) -> None:
    accession = source["accession"]
    cik = source["cik"]
    if (not isinstance(accession, str)
            or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession)
            or cik not in ISSUER_CIKS.values()):
        raise ValueError("unrecognized SEC accession or CIK")
    url = source["document_url"]
    if not isinstance(url, str):
        raise ValueError("missing document URL")
    split = urlsplit(url)
    prefix = ("/Archives/edgar/data/" + str(int(cik)) + "/"
              + accession.replace("-", "") + "/")
    if (split.scheme != "https" or split.hostname != "www.sec.gov"
            or split.port not in (None, 443) or split.username is not None
            or split.password is not None or split.fragment
            or split.query or not split.path.startswith(prefix)):
        raise ValueError("SEC document URL mismatches issuer accession")
    filename = split.path[len(prefix):]
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,255}\.html?", filename):
        raise ValueError("unsafe or invalid primary filing basename")


def load_registry(path: Path) -> dict:
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("schema_version") != "aics-sec-spv-neocloud-candidates-v1":
        raise ValueError("unknown primary SEC document registry")
    docs = registry.get("documents")
    if not isinstance(docs, list) or not docs:
        raise ValueError("missing filing documents")
    policy = registry.get("policy")
    if (not isinstance(policy, dict)
            or policy.get("sec_available_at_rule") != "filed_at_plus_14_calendar_days"
            or policy.get("future_filing_exclusion") is not True
            or policy.get("strict_primary_sec_documents") is not True
            or policy.get("allow_unverified_score_promotion") is not False
            or policy.get("spv_candidate_is_proven_spv") is not False
            or policy.get("index_aics") is not None
            or policy.get("predictive_skill_score") is not None):
        raise ValueError("registry attempts unsafe PIT or SPV promotion")
    unique = set()
    for doc in docs:
        if not isinstance(doc, dict):
            raise ValueError("invalid document row")
        identifier = doc.get("source_id")
        if (not isinstance(identifier, str)
                or not re.fullmatch(r"[A-Z0-9_]{5,90}", identifier)
                or identifier in unique):
            raise ValueError("duplicate or malformed source ID")
        unique.add(identifier)
        if (doc.get("issuer") not in ISSUER_CIKS
                or doc.get("cik") != ISSUER_CIKS[doc["issuer"]]
                or doc.get("form") not in ALLOWED_FORMS
                or not isinstance(doc.get("candidate_nodes"), list)
                or not doc["candidate_nodes"]
                or len(set(doc["candidate_nodes"])) != len(doc["candidate_nodes"])
                or not set(doc["candidate_nodes"]) <= ALLOWED_NODES):
            raise ValueError("invalid issuer form or AICS candidate node")
        filed = dt.date.fromisoformat(doc["filed_at"])
        available = dt.date.fromisoformat(doc["available_at"])
        if available != filed + dt.timedelta(days=14):
            raise ValueError("SEC filed date +14 calendar days gate violated")
        if doc.get("period_end"):
            period = dt.date.fromisoformat(doc["period_end"])
            if period > filed:
                raise ValueError("report period ends after filing")
        sec_url_check(doc)
    return registry


def require_sec_contact(agent: str) -> str:
    agent = agent.strip()
    if len(agent) < 15 or "@" not in agent or "example." in agent.lower():
        raise ValueError("genuine AICS_SEC_USER_AGENT required")
    return agent


def fetch_html(url: str, user_agent: str, opener=urlopen) -> bytes:
    """Only vetted SEC HTML documents are supplied by load_registry."""
    user_agent = require_sec_contact(user_agent)
    req = Request(url, headers={"User-Agent": user_agent,
                                "Accept": "text/html,application/xhtml+xml"})
    with opener(req, timeout=45) as response:
        if response.geturl() != url:
            raise ValueError("unexpected SEC document redirect")
        content_type = response.headers.get("Content-Type", "").lower()
        if not any(x in content_type for x in ("text/html", "application/xhtml+xml")):
            raise ValueError("SEC response is not HTML")
        raw = response.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("empty or oversized primary SEC document")
    if b"<html" not in raw[:8192].lower() and b"<!doctype html" not in raw[:8192].lower():
        raise ValueError("download is not a recognizable SEC HTML document")
    return raw


def archive(out: Path, source_id: str, data: bytes) -> tuple[str, str]:
    digest = hashlib.sha256(data).hexdigest()
    path = out / "raw" / (source_id.lower() + "_" + digest + ".html")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("previous source bytes do not match SHA256")
    if not path.exists():
        path.write_bytes(data)
    return digest, str(path)


def run(registry_path: Path, out: Path, as_of: dt.date, contact: str = "",
        opener=urlopen) -> dict:
    registry = load_registry(registry_path)
    out.mkdir(parents=True, exist_ok=True)
    contact_ready = True
    try:
        contact = require_sec_contact(contact)
    except (ValueError, AttributeError):
        contact_ready = False
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    rows = []
    for doc in registry["documents"]:
        filed = dt.date.fromisoformat(doc["filed_at"])
        available = dt.date.fromisoformat(doc["available_at"])
        row = {
            "source_id": doc["source_id"], "issuer": doc["issuer"],
            "cik": doc["cik"], "form": doc["form"],
            "accession": doc["accession"], "filed_at": filed.isoformat(),
            "available_at": available.isoformat(),
            "candidate_nodes": doc["candidate_nodes"],
            "candidate_role": doc["candidate_role"],
            "document_url": doc["document_url"],
            "retrieved_at_utc": now,
            "status": "not_collected",
            "historical_pit_independently_verified": False,
            "filing_content_numeric_metrics_certified": False,
            "score_eligible": False,
        }
        if available > as_of:
            row["status"] = "excluded_14_day_sec_lag"
        elif not contact_ready:
            row["status"] = "blocked_missing_sec_user_agent"
        else:
            try:
                raw = fetch_html(doc["document_url"], contact, opener=opener)
                sha, local = archive(out, doc["source_id"], raw)
                row.update(status="archived_raw_unverified", sha256=sha,
                           bytes=len(raw), raw_path=local)
            except Exception as exc:
                row.update(status="fetch_error", error=type(exc).__name__)
        rows.append(row)
    result = {
        "schema_version": "aics-sec-spv-neocloud-raw-v1",
        "as_of": as_of.isoformat(), "retrieved_at_utc": now,
        "source_registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        "document_count": len(rows),
        "date_eligible_documents": sum(r["available_at"] <= as_of.isoformat() for r in rows),
        "raw_documents_archived": sum(r["status"] == "archived_raw_unverified" for r in rows),
        "date_excluded_documents": sum(r["status"] == "excluded_14_day_sec_lag" for r in rows),
        "documents": rows,
        "index_aics": None, "spv_node_score": None,
        "neoclouds_node_score": None, "predictive_skill_score": None,
        "independently_verified_pit": False,
        "all_11_nodes_certified": False,
        "promotion": "BLOCKED", "trades_created": False,
        "limitations": [
            "SEC archive bytes alone do not establish economic SPV structure, debt risk or calibrated stress.",
            "The 14-day rule is enforced; original historical SEC publication and filing semantics need review.",
            "A foreign issuer 6-K has issuer-specific disclosures and may not contain standardized XBRL companyfacts.",
            "Source presence is not historical panel coverage or independent predictive OOS validation."
        ],
    }
    (out / "manifest.json").write_text(json.dumps(result, indent=2,
                                ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--as-of", type=dt.date.fromisoformat,
                   default=dt.datetime.now(dt.timezone.utc).date())
    args = p.parse_args()
    result = run(args.registry, args.out, args.as_of,
                 contact=os.getenv("AICS_SEC_USER_AGENT", ""))
    print(json.dumps({"source_statuses": {row["source_id"]: row["status"] for row in result["documents"]},
                      "archived_raw": result["raw_documents_archived"],
                      "date_eligible": result["date_eligible_documents"],
                      "date_excluded": result["date_excluded_documents"],
                      "index_aics": None, "promotion": "BLOCKED"}))
    return 0 if result["raw_documents_archived"] == result["date_eligible_documents"] and result["raw_documents_archived"] > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
