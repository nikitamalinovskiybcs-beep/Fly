#!/usr/bin/env python3
"""Archive and verify the Nscale Ward County SEC agreement and S-1 disclosure.

This is an original-document research capture (not historic independent PIT,
drawn loan balance, parent guarantee amount, node score, or AICS).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "https://www.sec.gov/Archives/edgar/data/2110365/000119312526395475/"
DOCUMENTS = {
    "ward_ex10_23": BASE + "ck0002110365-ex10_23.htm",
    "nscale_s1_narrative": BASE + "ck0002110365-20260918.htm",
}
FILING = dt.date(2026, 9, 18)
AVAILABLE = FILING + dt.timedelta(days=14)
LIMIT = 1_850_000_000
FIXED = 630_000_000
FLOATING = 1_220_000_000
MAX_BYTES = 40_000_000
OUTPUT = Path("aics_data/source_evidence/nscale_ward_primary")


class SourceError(ValueError):
    pass


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []

    def handle_data(self, data: str):
        self.chunks.append(data)


def html_text(raw: bytes) -> str:
    if not raw or len(raw) > MAX_BYTES:
        raise SourceError("Missing or oversized original HTML bytes")
    if b"<html" not in raw[:8192].lower() and b"<!doctype html" not in raw[:8192].lower():
        raise SourceError("Not an HTML source")
    parser = Text()
    parser.feed(raw.decode("utf-8-sig", errors="replace"))
    parser.close()
    return " ".join(" ".join(parser.chunks).split())


def validate_source(kind: str, raw: bytes) -> dict:
    if kind not in DOCUMENTS:
        raise SourceError("Not a fixed original SEC document")
    text = html_text(raw)
    if kind == "ward_ex10_23":
        markers = (
            "Nscale Ward County Borrower SPV, LLC",
            "Nscale Ward County, LLC",
            "August 27, 2026",
            "Delayed Draw Loan Commitments",
            "$1,850,000,000",
        )
        if not all(x in text for x in markers):
            raise SourceError("SEC Ward County original loan agreement identity/ceiling missing")
    else:
        description = "The Ward County GPU Credit Agreement provides"
        recourse = "The Ward County GPU Facility is guaranteed by"
        pos = text.find(description)
        guar_pos = text.find(recourse)
        if pos < 0 or guar_pos < 0 or guar_pos <= pos:
            raise SourceError("Ward County S-1 loan and guarantee paragraphs missing")
        window = text[pos:pos + 900]
        guar_window = text[guar_pos:guar_pos + 520]
        if (not all(x in window for x in ("$1.85 billion", "$630.0 million",
                                          "$1.22 billion"))
                or not all(x in guar_window for x in
                           ("Nscale Ward County, LLC", "limited guarantees from Nscale Limited"))
                or "Nscale Ward County Borrower SPV, LLC" not in text):
            raise SourceError("S-1 fixed/floating amounts or limited guarantee evidence missing")
    return {
        "source_id": kind,
        "source_url": DOCUMENTS[kind],
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "textual_identity_and_contract_terms_checked": True,
    }


def require_contact(contact: str) -> str:
    if (not isinstance(contact, str) or len(contact.strip()) < 15
            or "@" not in contact or "example." in contact.lower()):
        raise SourceError("SEC needs a real contact-bearing User-Agent")
    return contact.strip()


def fetch_original(url: str, agent: str, opener=urlopen) -> bytes:
    if url not in DOCUMENTS.values():
        raise SourceError("SEC URL outside fixed original accession")
    request = Request(url, headers={
        "User-Agent": require_contact(agent), "Accept": "text/html",
    })
    with opener(request, timeout=50) as response:
        if response.geturl() != url:
            raise SourceError("SEC redirect rejected")
        ctype = response.headers.get("Content-Type", "").lower()
        if "text/html" not in ctype and "application/xhtml+xml" not in ctype:
            raise SourceError("SEC response is not HTML")
        data = response.read(MAX_BYTES + 1)
    return data


def archive(out: Path, sources: dict[str, bytes], as_of: dt.date) -> dict:
    if as_of < AVAILABLE:
        raise SourceError("SEC +14 embargo: source not yet eligible")
    if set(sources) != set(DOCUMENTS):
        raise SourceError("Both independent SEC pages required")
    out = out.resolve()
    rows = []
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for kind in DOCUMENTS:
        raw = sources[kind]
        checked = validate_source(kind, raw)
        path = raw_dir / (kind + "_" + checked["sha256"] + ".html")
        if path.exists() and path.read_bytes() != raw:
            raise SourceError("Archived SEC bytes disagree")
        if not path.exists():
            path.write_bytes(raw)
        rows.append({
            **checked,
            "raw_path": str(path),
            "form": "S-1", "accession": "0001193125-26-395475",
            "issuer_cik": "2110365", "filed_at": FILING.isoformat(),
            "available_at": AVAILABLE.isoformat(),
            "archived_retrospectively": True,
            "independently_attested_historical_release_time": False,
        })
    report = {
        "schema_version": "aics-nscale-ward-two-sec-originals-v1",
        "as_of": as_of.isoformat(),
        "source_count": len(rows),
        "original_sec_html_rehashed_now": len(rows),
        "source_receipts": rows,
        "borrower": "Nscale Ward County Borrower SPV, LLC",
        "affiliate_guarantor": "Nscale Ward County, LLC",
        "limited_parent_guarantees_described": True,
        "parent_guaranteed_amount_usd": None,
        "fixed_delayed_draw_commitment_usd": FIXED,
        "floating_delayed_draw_commitment_usd": FLOATING,
        "facility_commitment_ceiling_usd": LIMIT,
        "actual_drawn_principal_usd": None,
        "effective_economic_recourse_usd": None,
        "other_nscale_nc_commitment_ceiling_usd": 1_200_000_000,
        "distinct_two_facility_commitment_ceiling_sum_usd": 3_050_000_000,
        "cross_facility_debt_sum_usd": None,
        "source_pit_independently_attested": False,
        "independent_24m_oos": False,
        "spv_node_score": None, "index_aics": None,
        "promotion": "BLOCKED", "trades_created": False,
        "limitations": [
            "New original SEC bytes captured retrospectively, not contemporaneous 2026 release evidence.",
            "Debt commitments are ceiling amounts, not funded principal or current balances.",
            "Limited parent guarantees have no independently determined enforceable monetary exposure.",
            "North Carolina separately validated in a prior source review, not rehashed by this capture.",
            "No synthetic time series, AICS stress score, certified PIT, or investment action.",
        ],
    }
    if FIXED + FLOATING != LIMIT:
        raise SourceError("Inconsistent original commitment components")
    (out / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def verify_archive(out: Path, manifest: dict) -> None:
    if (manifest.get("source_count") != 2 or manifest.get("index_aics") is not None
            or manifest.get("spv_node_score") is not None
            or manifest.get("promotion") != "BLOCKED"
            or manifest.get("actual_drawn_principal_usd") is not None):
        raise SourceError("Archive attempted model promotion")
    rows = manifest.get("source_receipts")
    if not isinstance(rows, list) or len(rows) != 2:
        raise SourceError("SEC inventory missing")
    for row, kind in zip(rows, DOCUMENTS):
        path = Path(row["raw_path"]).resolve()
        if not path.is_relative_to((out.resolve() / "raw")) or not path.is_file():
            raise SourceError("Archive path outside source evidence")
        actual = validate_source(kind, path.read_bytes())
        for key in ("source_id", "source_url", "sha256", "bytes"):
            if actual[key] != row.get(key):
                raise SourceError("Original source bytes and receipt mismatch")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.date(2026, 11, 19))
    p.add_argument("--out", type=Path, default=OUTPUT)
    args = p.parse_args()
    try:
        agent = os.getenv("AICS_SEC_USER_AGENT") or os.getenv("EDGAR_IDENTITY") or ""
        data = {kind: fetch_original(url, agent) for kind, url in DOCUMENTS.items()}
        report = archive(args.out, data, args.as_of)
        verify_archive(args.out, report)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error_type": type(exc).__name__}))
        return 2
    print(json.dumps({
        "originals_verified": report["original_sec_html_rehashed_now"],
        "distinct_facility_limit_usd": report["facility_commitment_ceiling_usd"],
        "drawn_principal_usd": None, "spv_node_score": None,
        "index_aics": None, "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
