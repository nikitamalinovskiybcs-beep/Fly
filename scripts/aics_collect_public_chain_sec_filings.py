#!/usr/bin/env python3
"""Original SEC submissions snapshot for nine public AI-chain issuers.

This captures *current* SEC metadata, not a historical SEC vintage, issuer
corporate-action occurrence, a drawn liability or a model score.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CIKS = {
    "NVDA": "0001045810",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "AMZN": "0001018724",
    "META": "0001326801",
    "ORCL": "0001341439",
    "MU": "0000723125",
    "AMD": "0000002488",
    "AVGO": "0001730168",
}
FORMS = frozenset(("10-K", "10-Q", "8-K", "10-K/A", "10-Q/A", "8-K/A"))
REVIEW_8K_ITEMS = frozenset(("1.01", "2.01", "3.03", "5.03", "8.01"))
MAX_BYTES = 15_000_000
SCHEMA = "aics-public-chain-sec-originals-v1"
DAY_RANGE = 730


def url_for(ticker: str) -> str:
    if ticker not in CIKS:
        raise ValueError("SEC issuer outside research roster")
    return f"https://data.sec.gov/submissions/CIK{CIKS[ticker]}.json"


def require_identity(contact: str) -> str:
    if not isinstance(contact, str) or len(contact.strip()) < 15 or "@" not in contact or "example." in contact.lower():
        raise ValueError("Accountable SEC contact User-Agent required")
    return contact.strip()


def retrieve(url: str, contact: str, opener=urlopen) -> bytes:
    contact = require_identity(contact)
    if url not in {url_for(t) for t in CIKS}:
        raise ValueError("SEC endpoint must be an approved original")
    req = Request(url, headers={"User-Agent":contact, "Accept":"application/json"})
    for attempt in range(3):
        try:
            with opener(req, timeout=50) as response:
                if response.geturl() != url:
                    raise ValueError("Unexpected SEC source redirect")
                raw = response.read(MAX_BYTES + 1)
            if not raw or len(raw) > MAX_BYTES:
                raise ValueError("Empty/oversized SEC submissions")
            return raw
        except HTTPError as error:
            if error.code != 429 or attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    raise ValueError("SEC retry budget exhausted")


def interpret(raw: bytes, ticker: str, as_of: dt.date) -> dict:
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Missing/oversized SEC original")
    data = json.loads(raw)
    if not isinstance(data, dict) or int(data.get("cik", -1)) != int(CIKS[ticker]):
        raise ValueError("Official SEC CIK does not match issuer")
    tickers = data.get("tickers")
    if not isinstance(tickers, list) or ticker not in tickers:
        raise ValueError("Issuer/ticker identity not supported by original SEC source")
    recent = data.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict):
        raise ValueError("No recent SEC submissions")
    columns = ("form", "filingDate", "accessionNumber", "primaryDocument")
    if any(not isinstance(recent.get(key), list) for key in columns):
        raise ValueError("SEC recent filings arrays missing")
    lengths = {len(recent[k]) for k in columns}
    if len(lengths) != 1:
        raise ValueError("SEC recent filing arrays inconsistent")
    items = recent.get("items")
    if items is not None and (not isinstance(items, list) or len(items) != len(recent["form"])):
        raise ValueError("SEC 8-K items array inconsistent")
    first_day = as_of - dt.timedelta(days=DAY_RANGE)
    eligible = []
    in_window_seen = set()
    held_by_14_days = 0
    not_in_window = 0
    for i, (form, filed_raw, accn, primary) in enumerate(
        zip(*(recent[c] for c in columns))
    ):
        if form not in FORMS:
            continue
        filed = dt.date.fromisoformat(filed_raw)
        if filed < first_day or filed > as_of:
            not_in_window += 1
            continue
        if (not isinstance(accn, str) or
                not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accn) or
                not isinstance(primary, str) or
                not re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", primary)):
            raise ValueError("Untrusted SEC filing identifier")
        if accn in in_window_seen:
            raise ValueError("Duplicate SEC accession in original index")
        in_window_seen.add(accn)
        available = filed + dt.timedelta(days=14)
        if available > as_of:
            held_by_14_days += 1
            continue
        item_text = items[i] if items is not None else ""
        if not isinstance(item_text, str):
            raise ValueError("Malformed SEC 8-K item labels")
        item_codes = set(re.findall(r"\b\d+\.\d{2}\b", item_text)) if form.startswith("8-K") else set()
        # Only metadata *hints*; no original underlying 8-K text evaluated.
        candidate_flags = sorted(item_codes.intersection(REVIEW_8K_ITEMS))
        eligible.append({
            "ticker":ticker, "cik":CIKS[ticker], "form":form,
            "filed_at":filed.isoformat(), "available_at":available.isoformat(),
            "accession":accn, "primary_document":primary,
            "sec_filing_url":("https://www.sec.gov/Archives/edgar/data/"
                +str(int(CIKS[ticker]))+"/"+accn.replace("-", "")+"/"+primary),
            "possible_8k_item_codes_for_human_review":candidate_flags,
            "actual_corporate_action_verified":False,
            "verified_historical_pit":False,
            "score_eligible":False,
        })
    eligible.sort(key=lambda r:(r["filed_at"],r["accession"]))
    return {
        "as_of":as_of.isoformat(),
        "ticker":ticker,"cik":CIKS[ticker],
        "candidate_filings_eligible_sec_14d":len(eligible),
        "excluded_due_sec_14d":held_by_14_days,
        "form_filings_outside_research_window":not_in_window,
        "possible_8k_item_review_count":sum(bool(r["possible_8k_item_codes_for_human_review"]) for r in eligible),
        "eligible_filing_metadata":eligible,
        "complete_historical_submissions_vintages":False,
        "historical_coverage_independently_attested":False,
        "corporate_actions_independently_attested":False,
        "origin":"SEC_ORIGINAL_CURRENT_SUBMISSIONS_SNAPSHOT",
    }


def archive(out: Path, ticker: str, raw: bytes) -> tuple[str, str]:
    digest = hashlib.sha256(raw).hexdigest()
    p = out/"raw"/f"{ticker}_{digest}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and p.read_bytes()!=raw:
        raise ValueError("SEC original already exists with different raw bytes")
    if not p.exists():
        p.write_bytes(raw)
    return digest,str(p)


def collect(out: Path, *, as_of: dt.date, contact: str, fetcher=retrieve,
            clock=None) -> dict:
    now = clock() if clock else dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("SEC capture requires UTC-offset-aware clock")
    now = now.astimezone(dt.timezone.utc)
    if as_of > now.date():
        raise ValueError("Cannot label current SEC retrieval as a future as-of vintage")
    out.mkdir(parents=True,exist_ok=True)
    rows = []
    for ticker in CIKS:
        source = {"ticker":ticker, "cik":CIKS[ticker], "source_url":url_for(ticker),
                  "status":"not_captured","retrieved_at_utc":now.isoformat()}
        try:
            raw = fetcher(source["source_url"],contact)
            fields = interpret(raw,ticker,as_of)
            digest,where = archive(out,ticker,raw)
            source.update(fields)
            source.update(status="raw_original_sec_snapshot_unverified",
                          raw_sha256=digest,raw_bytes=len(raw),raw_path=where)
        except (ValueError, KeyError, TypeError, OSError, URLError, HTTPError) as error:
            source.update(status="blocked",error_type=type(error).__name__)
        rows.append(source)
    manifest = {
        "schema_version":SCHEMA, "scope":"NINE_PUBLIC_ISSUERS_NOT_ALL_37_PRIVATE_COUNTERPARTIES",
        "as_of":as_of.isoformat(), "captured_at_utc":now.isoformat(),
        "research_roster":list(CIKS),
        "raw_original_issuers":sum(row["status"]=="raw_original_sec_snapshot_unverified" for row in rows),
        "issuers":rows,
        "historical_sec_vintages_attested":False,
        "signed_contract_recourse_verified":False,
        "sec_8k_item_hint_is_action_proof":False,
        "historical_pit_attested":False,
        "node_stress_scores":None, "index_aics":None, "predictive_skill_score":None,
        "promotion":"BLOCKED","trades_created":False,
        "notes":[
            "Current SEC submissions JSON is not an original historical release archive.",
            "8-K metadata item numbers are review hints, not proof of splits, dividends or contract terms.",
            "Recent filing array and SEC embargo may omit older filings; never assume complete coverage.",
            "NVIDIA chain has 37 named research entities, only nine in this public-issuer SEC candidate set.",
        ],
    }
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return manifest


def audit(out: Path) -> dict:
    manifest = json.loads((out/"manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version")!=SCHEMA or
            manifest.get("scope")!="NINE_PUBLIC_ISSUERS_NOT_ALL_37_PRIVATE_COUNTERPARTIES" or
            manifest.get("research_roster")!=list(CIKS) or
            manifest.get("raw_original_issuers")!=len(CIKS) or
            manifest.get("historical_sec_vintages_attested") is not False or
            manifest.get("signed_contract_recourse_verified") is not False or
            manifest.get("sec_8k_item_hint_is_action_proof") is not False or
            manifest.get("historical_pit_attested") is not False or
            manifest.get("node_stress_scores") is not None or
            manifest.get("index_aics") is not None or
            manifest.get("predictive_skill_score") is not None or
            manifest.get("promotion")!="BLOCKED" or
            manifest.get("trades_created") is not False):
        raise ValueError("Unverified issuer evidence promoted or omitted")
    capture = dt.datetime.fromisoformat(manifest["captured_at_utc"])
    if capture.tzinfo is None or capture.utcoffset() is None or capture > dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=5):
        raise ValueError("Untrusted SEC capture time")
    as_of = dt.date.fromisoformat(manifest["as_of"])
    if as_of > capture.date():
        raise ValueError("Future-dated SEC current-capture cutoff")
    rows = manifest.get("issuers")
    if not isinstance(rows,list) or [r.get("ticker") for r in rows]!=list(CIKS):
        raise ValueError("Incomplete/modified SEC issuer roster")
    total = 0
    for row in rows:
        ticker = row["ticker"]
        if (row.get("status") != "raw_original_sec_snapshot_unverified" or
                row.get("cik") != CIKS[ticker] or
                row.get("source_url") != url_for(ticker) or
                row.get("retrieved_at_utc") != manifest["captured_at_utc"]):
            raise ValueError("Untrusted issuer receipt")
        sha = row.get("raw_sha256")
        if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{64}",sha):
            raise ValueError("Invalid original issuer fingerprint")
        p = Path(row.get("raw_path",""))
        if not p.is_absolute():
            p = Path.cwd()/p
        expected = (out.resolve()/"raw"/f"{ticker}_{sha}.json").resolve()
        if p.resolve()!=expected or not p.is_file():
            raise ValueError("SEC original file missing or outside archive")
        raw = p.read_bytes()
        if (hashlib.sha256(raw).hexdigest()!=sha or len(raw)!=row.get("raw_bytes")):
            raise ValueError("SEC original source SHA mismatch")
        expected = interpret(raw,ticker,as_of)
        for key in expected:
            if row.get(key)!=expected[key]:
                raise ValueError("SEC dated filing metadata disagrees with original bytes")
        total += row["candidate_filings_eligible_sec_14d"]
    result = {
        "schema_version":"aics-public-chain-sec-rehash-v1",
        "original_sec_issuers_rehashed":len(rows),
        "sec_14d_eligible_filing_metadata_records":total,
        "seven_price_tickers_is_not_nine_public_issuers":True,
        "thirty_seven_name_network_still_uncertified":True,
        "historical_pit_attested":False,
        "contracted_drawn_exposure_usd":None,
        "index_aics":None,"node_stress_scores":None,
        "promotion":"BLOCKED","trades_created":False,
    }
    (out/"rehash_receipt.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("collect","audit"),required=True)
    parser.add_argument("--out",type=Path,default=Path("aics_data/source_evidence/public_chain_sec_live"))
    args=parser.parse_args()
    try:
        if args.mode=="collect":
            data=collect(args.out,as_of=dt.datetime.now(dt.timezone.utc).date(),
                         contact=os.getenv("AICS_SEC_USER_AGENT",""))
            summary={"original_sec_issuers":data["raw_original_issuers"],
                     "expected":len(CIKS),"model_promotion":"BLOCKED"}
            print(json.dumps(summary))
            return 0 if data["raw_original_issuers"]==len(CIKS) else 2
        result=audit(args.out)
        print(json.dumps(result))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as error:
        print("AICS SEC issuer-original provenance BLOCKED: "+type(error).__name__)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
