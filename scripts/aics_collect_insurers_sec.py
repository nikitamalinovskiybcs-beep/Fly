#!/usr/bin/env python3
"""Research-only SEC XBRL evidence for the AICS Insurers node (MET, PRU).

Downloads actual SEC submissions/companyfacts JSON, archives byte-exact raw
payloads with SHA256, and extracts strictly dated issuer balance-sheet
candidates.  Values are NOT Insurers stress scores and must not be used to
calculate certified AICS.  Current SEC companyfacts are not archival PIT
snapshots: as-of filtering alone does not verify historical taxonomy/revisions.

Requires a genuine AICS_SEC_USER_AGENT with an accountable contact email.
No synthetic observations, historical backfill, or predicted data.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen

ISSUERS = {"MET": "0001099219", "PRU": "0001137774"}
# US-GAAP tags are *candidate observations*, NOT stress metrics.
# Other insurer-specific Level 3 / private-credit disclosures often only
# exist in issuer-specific contexts or textual footnotes.
INSTANT_US_GAAP_TAGS = (
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "AvailableForSaleSecuritiesDebtSecurities",
    "DebtSecuritiesAvailableForSaleExcludingAccruedInterest",
    "MortgageLoansOnRealEstate",
    "MortgageLoansOnRealEstateNet",
    "LongTermDebt",
)
FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}
COLUMNS = (
    "issuer", "cik", "candidate_node", "taxonomy", "tag", "unit",
    "observation_start", "observation_date", "form", "accession", "fy",
    "fp", "frame", "filed_at", "available_at", "value",
    "companyfacts_raw_sha256", "submissions_raw_sha256",
    "sec_filing_url", "pit_verified", "score_eligible"
)
MAX_BYTES = 75_000_000
DEFAULT_OUT = Path("aics_data/source_evidence/insurers_sec")


def sec_url(cik: str, kind: str) -> str:
    if cik not in ISSUERS.values() or kind not in ("submissions", "companyfacts"):
        raise ValueError("SEC CIK or endpoint outside declared insurer universe")
    return ("https://data.sec.gov/submissions/CIK" + cik + ".json"
            if kind == "submissions"
            else "https://data.sec.gov/api/xbrl/companyfacts/CIK" + cik + ".json")


def require_contact(user_agent: str) -> str:
    value = user_agent.strip()
    if len(value) < 15 or "@" not in value or "example." in value.lower():
        raise ValueError("AICS_SEC_USER_AGENT must identify a real contact")
    return value


def retrieve_json(url: str, user_agent: str, opener=urlopen) -> tuple[bytes, dict]:
    agent = require_contact(user_agent)
    if not any(url == sec_url(cik, kind) for cik in ISSUERS.values()
               for kind in ("submissions", "companyfacts")):
        raise ValueError("SEC URL outside allowlist")
    req = Request(url, headers={"User-Agent": agent, "Accept": "application/json"})
    with opener(req, timeout=50) as response:
        if response.geturl() != url:
            raise ValueError("unexpected SEC redirect")
        raw = response.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("empty or oversized SEC response")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("invalid SEC JSON")
    return raw, parsed


def archive_payload(folder: Path, issuer: str, kind: str, raw: bytes) -> tuple[str, str]:
    digest = hashlib.sha256(raw).hexdigest()
    path = folder / (issuer.lower() + "_" + kind + "_" + digest + ".json")
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("existing evidence hash mismatch")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(raw)
    return digest, str(path)


def recent_accessions(submissions: dict) -> dict:
    """Only accession/form/filing-date matches in downloaded SEC submissions count."""
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filed_dates = recent.get("filingDate", [])
    primaries = recent.get("primaryDocument", [])
    if not all(isinstance(x, list) for x in (forms, accessions, filed_dates, primaries)):
        raise ValueError("malformed recent SEC filing index")
    if len({len(forms), len(accessions), len(filed_dates), len(primaries)}) != 1:
        raise ValueError("inconsistent SEC filing index lengths")
    mapping = {}
    for form, accn, filed, primary in zip(forms, accessions, filed_dates, primaries):
        if form not in FORMS:
            continue
        if (not isinstance(accn, str) or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accn)
                or not isinstance(filed, str) or not isinstance(primary, str)
                or not re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", primary)):
            continue
        dt.date.fromisoformat(filed)
        mapping[(accn, form, filed)] = primary
    return mapping


def extract_candidates(issuer: str, facts: dict, submissions: dict,
                       cutoff: dt.date, raw_facts_sha: str,
                       raw_sub_sha: str, first_period: dt.date | None = None) -> tuple[list[dict], dict]:
    if issuer not in ISSUERS:
        raise ValueError("issuer outside universe")
    cik = ISSUERS[issuer]
    if int(facts.get("cik", -1)) != int(cik) or int(submissions.get("cik", -1)) != int(cik):
        raise ValueError("SEC source CIK mismatch")
    index = recent_accessions(submissions)
    us = facts.get("facts", {}).get("us-gaap", {})
    if not isinstance(us, dict):
        raise ValueError("malformed SEC facts taxonomy")
    excluded = {"unmatched_accession": 0, "unavailable_sec_14d": 0,
                "prehistory": 0, "not_instant": 0, "invalid_observation": 0}
    missing_tags = []
    out = []
    seen = set()
    for tag in INSTANT_US_GAAP_TAGS:
        detail = us.get(tag)
        if not isinstance(detail, dict):
            missing_tags.append(tag)
            continue
        units = detail.get("units", {})
        if not isinstance(units, dict):
            missing_tags.append(tag)
            continue
        values = units.get("USD", [])
        if not isinstance(values, list):
            raise ValueError("malformed XBRL unit values")
        for v in values:
            if not isinstance(v, dict):
                excluded["invalid_observation"] += 1
                continue
            try:
                filed = dt.date.fromisoformat(v["filed"])
                observed = dt.date.fromisoformat(v["end"])
                accn = v["accn"]
                form = v["form"]
                value = v["val"]
                if (not isinstance(value, (int, float)) or isinstance(value, bool)
                        or not math.isfinite(value)):
                    raise ValueError("not finite numeric")
            except (KeyError, ValueError, TypeError, OverflowError):
                excluded["invalid_observation"] += 1
                continue
            # This collector is for *instant* balance-sheet facts only.
            if v.get("start") is not None:
                excluded["not_instant"] += 1
                continue
            if first_period is not None and observed < first_period:
                excluded["prehistory"] += 1
                continue
            if observed > filed or observed > cutoff:
                excluded["invalid_observation"] += 1
                continue
            available = filed + dt.timedelta(days=14)
            if available > cutoff:
                excluded["unavailable_sec_14d"] += 1
                continue
            primary = index.get((accn, form, filed.isoformat()))
            if not primary:
                excluded["unmatched_accession"] += 1
                continue
            key = (tag, observed, accn, form, filed, value)
            if key in seen:
                continue
            seen.add(key)
            # Preserve individual accession versions and context metadata;
            # never select an amended fact by future values.
            doc_url = ("https://www.sec.gov/Archives/edgar/data/"
                       + str(int(cik)) + "/" + accn.replace("-", "") + "/" + primary)
            out.append({
                "issuer": issuer, "cik": cik, "candidate_node": "Insurers",
                "taxonomy": "us-gaap", "tag": tag, "unit": "USD",
                "observation_start": "", "observation_date": observed.isoformat(),
                "form": form, "accession": accn,
                "fy": str(v.get("fy", "")), "fp": str(v.get("fp", "")),
                "frame": str(v.get("frame", "")), "filed_at": filed.isoformat(),
                "available_at": available.isoformat(), "value": str(value),
                "companyfacts_raw_sha256": raw_facts_sha,
                "submissions_raw_sha256": raw_sub_sha,
                "sec_filing_url": doc_url,
                "pit_verified": "false", "score_eligible": "false"
            })
    out.sort(key=lambda x: (x["issuer"], x["tag"], x["observation_date"],
                            x["filed_at"], x["accession"]))
    return out, {"missing_tags": missing_tags, "excluded": excluded,
                 "matched_filing_accessions": len(index),
                 "candidate_observations": len(out)}


def run(out: Path, as_of: dt.date, agent: str,
        opener=urlopen, first_period: dt.date | None = None) -> dict:
    agent = require_contact(agent)
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    all_rows = []
    for issuer, cik in ISSUERS.items():
        entry = {"issuer": issuer, "cik": cik, "status": "not_downloaded",
                 "independently_verified_pit": False,
                 "candidate_node": "Insurers", "node_score": None}
        try:
            sources = {}
            for kind in ("submissions", "companyfacts"):
                url = sec_url(cik, kind)
                raw, decoded = retrieve_json(url, agent, opener=opener)
                digest, path = archive_payload(out / "raw", issuer, kind, raw)
                sources[kind] = {"url": url, "sha256": digest, "raw_path": path,
                                 "bytes": len(raw), "data": decoded}
            rows, detail = extract_candidates(
                issuer, sources["companyfacts"]["data"], sources["submissions"]["data"],
                as_of, sources["companyfacts"]["sha256"], sources["submissions"]["sha256"],
                first_period=first_period
            )
            all_rows.extend(rows)
            entry.update(status="downloaded_unverified",
                         sources={k: {key: val for key, val in item.items() if key != "data"}
                                  for k, item in sources.items()}, **detail)
        except Exception as exc:
            entry.update(status="collection_error", error=type(exc).__name__)
        jobs.append(entry)
        time.sleep(0.3)
    csv_path = out / "insurer_balance_sheet_candidates.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)
    manifest = {
        "schema_version": "aics-insurers-sec-evidence-v1",
        "as_of": as_of.isoformat(),
        "first_period": first_period.isoformat() if first_period else None,
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "issuer_count": len(ISSUERS), "source_downloads_expected": 4,
        "successful_issuers": sum(j["status"] == "downloaded_unverified" for j in jobs),
        "candidate_observations": len(all_rows),
        "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "issuers": jobs,
        "independently_verified_pit": False,
        "validated_node_scores": 0,
        "insurers_node_score": None,
        "index_aics": None, "predictive_skill_score": None,
        "promotion": "BLOCKED", "trades_created": False,
        "limitations": [
            "Current SEC companyfacts JSON may contain later restatements/taxonomy changes; historical as-of filtering is not independent vintage proof.",
            "SEC 14-calendar-day eligibility is enforced for 10-Q/10-K and amendments, but filing provenance still requires original source review.",
            "US-GAAP balance-sheet values are not direct private-credit exposure, Level 3 assets, NAIC RBC, nor calibrated insurer stress scores.",
            "Only filed accession records present in current SEC submissions.recent are used; other genuine records remain missing, not backfilled.",
            "All raw SHA-256 checksums refer to newly downloaded bytes, not proven historical snapshots."
        ]
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--as-of", type=dt.date.fromisoformat,
                   default=dt.datetime.now(dt.timezone.utc).date())
    p.add_argument("--first-period", type=dt.date.fromisoformat,
                   default=dt.date(2018, 1, 1))
    args = p.parse_args()
    result = run(args.out, args.as_of, os.environ.get("AICS_SEC_USER_AGENT", ""),
                 first_period=args.first_period)
    print(json.dumps({"successful_issuers": result["successful_issuers"],
                      "candidate_observations": result["candidate_observations"],
                      "insurers_node_score": None, "index_aics": None}))
    return 0 if result["successful_issuers"] == len(ISSUERS) else 2


if __name__ == "__main__":
    raise SystemExit(main())
