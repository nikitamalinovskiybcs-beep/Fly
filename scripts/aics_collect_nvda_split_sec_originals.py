#!/usr/bin/env python3
"""Rehash primary SEC NVDA 2024 split announcement and effectuation separately.

Two 8-K filings are different as-of events. The AICS strict SEC+14 lag makes
the May-22 announcement eligible June 5, and the June-7 effectuation filing
eligible June 21. Neither retroactively validates traded price adjustments,
basket membership, licensing, or independently attested historical PIT.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen

from scripts.aics_observed_source_review import words

CIK = "1045810"
DOCUMENTS = (
    {
        "id": "nvda_split_announcement_20240522",
        "accession": "0001045810-24-000113",
        "filed_at": "2024-05-22",
        "primary_filename": "nvda-20240522.htm",
        "required_text": (
            "ten-for-one forward stock split",
            "On May 22, 2024, the Company announced",
            "nine additional shares of common stock",
            "June 6, 2024",
            "June 7, 2024",
            "June 10, 2024",
        ),
    },
    {
        "id": "nvda_split_effectuation_20240607",
        "accession": "0001045810-24-000144",
        "filed_at": "2024-06-07",
        "primary_filename": "nvda-20240607.htm",
        "required_text": (
            "ten-for-one forward stock split",
            "4:01 p.m. Eastern Time on June 7, 2024",
            "split-adjusted basis at market open on June 10, 2024",
        ),
        # Independently rehashed in the existing nine-originals SEC review.
        "pinned_original_sha256":
            "249aae37369da9451cc512733ffd65202e8d675cea56dc5e12ad2edf1c7fd010",
        "pinned_original_bytes": 166014,
        "pinned_document_text_sha256":
            "09ea10fc06c73c00b583eb1a279392a57fb2594a0679211e91fd840d6dc06061",
    },
)
MAX_BYTES = 1_500_000
OUTPUT = Path("aics_data/source_evidence/ai_equities_nvda_split_sec")


def source_url(item: dict) -> str:
    return ("https://www.sec.gov/Archives/edgar/data/" + CIK + "/"
            + item["accession"].replace("-", "") + "/" + item["accession"] + ".txt")


def require_contact(value: str) -> str:
    if not isinstance(value, str) or not 15 <= len(value.strip()) <= 250 or "@" not in value:
        raise ValueError("AICS SEC contact-bearing User-Agent required")
    if "example." in value.lower():
        raise ValueError("Example contact is not a real SEC identity")
    return value.strip()


def fetch_source(item: dict, contact: str, opener=urlopen) -> bytes:
    if item not in DOCUMENTS:
        raise ValueError("Unexpected SEC action source")
    url = source_url(item)
    request = Request(url, headers={"User-Agent": require_contact(contact),
                                    "Accept": "text/plain"})
    with opener(request, timeout=45) as response:
        if response.geturl() != url:
            raise ValueError("SEC original redirected to a different source")
        raw = response.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Missing or oversized SEC original")
    return raw


def verify_sec_original(raw: bytes, item: dict) -> dict:
    """Bind original bytes to issuer CIK, accession, form, date, 8-K, event text."""
    if item not in DOCUMENTS or not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Unexpected SEC original input")
    header, sep, _ = raw.partition(b"<DOCUMENT>")
    if not sep or not header.startswith(b"<SEC-DOCUMENT>"):
        raise ValueError("Original SEC submission envelope missing")
    def metadata(name: str) -> str:
        label = re.escape(name.encode())
        found = re.findall(rb"(?m)^\s*" + label + rb":\s*([^\r\n]+)", header)
        if len(found) != 1:
            raise ValueError("SEC original filing metadata missing or ambiguous")
        return found[0].decode("ascii", errors="replace").strip()
    if (metadata("ACCESSION NUMBER") != item["accession"]
            or metadata("CONFORMED SUBMISSION TYPE") != "8-K"
            or metadata("FILED AS OF DATE") != item["filed_at"].replace("-", "")
            or int(metadata("CENTRAL INDEX KEY")) != int(CIK)):
        raise ValueError("Original SEC 8-K issuer/form/date/accession mismatch")
    docs = raw.split(b"<DOCUMENT>")[1:]
    selected = []
    for document in docs:
        info, delimiter, rest = document.partition(b"<TEXT>")
        if not delimiter:
            continue
        name = b"<FILENAME>" + item["primary_filename"].encode()
        if name not in info.splitlines():
            continue
        if b"<TYPE>8-K" not in info.splitlines():
            raise ValueError("Selected SEC split document is not an 8-K")
        body, ended, _ = rest.partition(b"</TEXT>")
        if not ended:
            raise ValueError("SEC original document TEXT lacks a closing tag")
        selected.append(body)
    if len(selected) != 1:
        raise ValueError("Expected one exact primary split document")
    event_text = words(selected[0])
    if not all(text in event_text for text in item["required_text"]):
        raise ValueError("Original SEC split event details missing or changed")
    original_sha = hashlib.sha256(raw).hexdigest()
    document_sha = hashlib.sha256(selected[0]).hexdigest()
    if ("pinned_original_sha256" in item
            and (original_sha != item["pinned_original_sha256"]
                 or len(raw) != item["pinned_original_bytes"]
                 or document_sha != item["pinned_document_text_sha256"])):
        raise ValueError("Original June 8-K bytes disagree with independent receipt")
    filed = dt.date.fromisoformat(item["filed_at"])
    return {
        "source_id": item["id"], "issuer_cik": CIK, "form": "8-K",
        "accession": item["accession"],
        "original_sec_url": source_url(item),
        "primary_document_url": (
            source_url(item).rsplit("/", 1)[0] + "/" + item["primary_filename"]),
        "filed_at": filed.isoformat(),
        "available_at": (filed + dt.timedelta(days=14)).isoformat(),
        "bytes": len(raw), "sha256": original_sha,
        "primary_document_sha256": document_sha,
        "one_primary_document_text_verified": True,
        "corporate_action_event_type": "NVDA_TEN_FOR_ONE_SPLIT",
        "historical_pit_independently_attested": False,
    }


def archive(out: Path, payloads: dict[str, bytes], as_of: dt.date,
            retrieved_at_utc: dt.datetime | None = None) -> dict:
    if set(payloads) != {x["id"] for x in DOCUMENTS}:
        raise ValueError("Incomplete two-filing SEC event chain")
    now = retrieved_at_utc or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Capture timestamp lacks UTC offset")
    now = now.astimezone(dt.timezone.utc)
    if now.date() > dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1):
        raise ValueError("Future SEC capture timestamp")
    rows = []
    rawdir = out.resolve() / "raw"
    rawdir.mkdir(parents=True, exist_ok=True)
    for item in DOCUMENTS:
        if as_of < dt.date.fromisoformat(item["filed_at"]) + dt.timedelta(days=14):
            raise ValueError("SEC +14-day information embargo")
        raw = payloads[item["id"]]
        row = verify_sec_original(raw, item)
        path = rawdir / (row["source_id"] + "_" + row["sha256"] + ".txt")
        if path.is_file() and path.read_bytes() != raw:
            raise ValueError("Original SEC file collision")
        if not path.exists():
            path.write_bytes(raw)
        rows.append({**row, "raw_path": str(path),
                     "retrieved_at_utc": now.isoformat(),
                     "historic_publication_instant_independently_attested": False})
    report = {
        "schema_version": "aics-nvda-two-original-sec-split-events-v1",
        "node": "AI Equities",
        "research_as_of": as_of.isoformat(),
        "research_roster_size": 7,
        "original_filings_rehashed": 2,
        "source_records": rows,
        "event_issuer": "NVDA",
        "split_new_for_old": [10, 1],
        "announcement_filed_at": "2024-05-22",
        "announcement_sec_available_at": "2024-06-05",
        "effectuation_filed_at": "2024-06-07",
        "effectuation_sec_available_at": "2024-06-21",
        "split_effective_date": "2024-06-07",
        "first_expected_split_basis_market_session": "2024-06-10",
        "corporate_action_historical_completeness_attested": False,
        "historical_constituency_attested": False,
        "security_identity_history_attested": False,
        "historical_adjustment_factors_pit_attested": False,
        "provider_price_data_license_cleared": False,
        "retrospective_source_capture": True,
        "independent_historical_release_time_attested": False,
        "historical_basket_price_returns_calculated": False,
        "historical_price_adjustments_generated": False,
        "score_eligible": False,
        "node_stress_score": None,
        "index_aics": None, "promotion": "BLOCKED",
        "trades_created": False,
        "limitations": [
            "May 22 announced the prospective split; June 7 independently confirmed legal effectuation.",
            "An SEC filing available under +14 days is not a whole historical corporate-action feed.",
            "The SEC as-of lag is conservative even when an announcement predates the legal change.",
            "Two retrospectively downloaded SEC originals cannot certify original intraday market feed vintage.",
            "No claim of historical benchmark constituency, split-adjusted returns, complete dividend history, or 24m OOS.",
        ],
    }
    (out / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def verify_archive(out: Path) -> dict:
    manifest = json.loads((out / "manifest.json").read_bytes())
    if (manifest.get("schema_version") != "aics-nvda-two-original-sec-split-events-v1"
            or manifest.get("node") != "AI Equities"
            or manifest.get("research_roster_size") != 7
            or manifest.get("original_filings_rehashed") != 2
            or manifest.get("split_new_for_old") != [10, 1]
            or manifest.get("announcement_sec_available_at") != "2024-06-05"
            or manifest.get("effectuation_sec_available_at") != "2024-06-21"
            or manifest.get("split_effective_date") != "2024-06-07"
            or manifest.get("first_expected_split_basis_market_session") != "2024-06-10"
            or manifest.get("independent_historical_release_time_attested") is not False
            or manifest.get("historical_constituency_attested") is not False
            or manifest.get("historical_adjustment_factors_pit_attested") is not False
            or manifest.get("node_stress_score") is not None
            or manifest.get("index_aics") is not None
            or manifest.get("promotion") != "BLOCKED"):
        raise ValueError("Split archive attempted event/PIT/score promotion")
    records = manifest.get("source_records")
    if not isinstance(records, list) or len(records) != 2:
        raise ValueError("Incomplete two-event original SEC receipts")
    for item, record in zip(DOCUMENTS, records, strict=True):
        if (record.get("source_id") != item["id"]
                or record.get("accession") != item["accession"]
                or record.get("filed_at") != item["filed_at"]
                or record.get("available_at") != (
                    dt.date.fromisoformat(item["filed_at"]) + dt.timedelta(days=14)).isoformat()
                or record.get("historic_publication_instant_independently_attested") is not False
                or record.get("historical_pit_independently_attested") is not False):
            raise ValueError("Split source filing dates or original identity changed")
        original = Path(record["raw_path"]).resolve()
        if not original.is_relative_to((out.resolve() / "raw")) or not original.is_file():
            raise ValueError("Missing or untrusted split original path")
        checked = verify_sec_original(original.read_bytes(), item)
        for field in ("sha256", "bytes", "primary_document_sha256",
                      "original_sec_url", "primary_document_url", "issuer_cik", "form"):
            if record.get(field) != checked[field]:
                raise ValueError("Split original bytes/metadata receipt mismatch")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=OUTPUT)
    p.add_argument("--as-of", type=dt.date.fromisoformat,
                   default=dt.date(2026, 11, 19))
    args = p.parse_args()
    try:
        contact = (os.getenv("AICS_SEC_USER_AGENT")
                   or os.getenv("EDGAR_IDENTITY")
                   or os.getenv("SEC_USER_AGENT") or "")
        data = {d["id"]: fetch_source(d, contact) for d in DOCUMENTS}
        result = archive(args.out, data, args.as_of)
        verify_archive(args.out)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": type(exc).__name__}))
        return 2
    print(json.dumps({
        "original_sec_filings": result["original_filings_rehashed"],
        "first_announcement_sec_available_at": result["announcement_sec_available_at"],
        "legal_effectuation_sec_available_at": result["effectuation_sec_available_at"],
        "index_aics": None, "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
