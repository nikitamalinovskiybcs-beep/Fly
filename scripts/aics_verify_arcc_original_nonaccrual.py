#!/usr/bin/env python3
"""Independently verify eight ARCC non-accrual figures against original SEC HTML.

The user-entered research CSV is NOT sufficient. Require source-bytes ZIP SHA,
SEC exhibit origin, filing-date +14 gate, exact Q1/Q2/Q3 paragraph matching
and December 2025 cross-confirmation in all three filings. The issuer
February 2026 fetched page is a 3.5 KB shell and does NOT prove an original
February release. Do not backdate the Dec 2025 figures to that page.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import zipfile
from decimal import Decimal
from pathlib import Path

from scripts.aics_arcc_nonaccrual_monitor import read_checked

ORIGINAL_ZIP_SHA = "805c1b5d692625b1d2d7c0c9ebb56986187d92eb6f10015e1bb3e79ce103d7d6"
ORIGINAL_MANIFEST_SHA = "005dc820284e99de32cf71af1b6eeea01822eeadf7748aacb55687e8efd9fc9f"
RESEARCH_CSV = Path("aics_data/research/arcc_primary_disclosures_2026-11-18.csv")
DEFAULT_OUT = Path("docs/audit/aics_arcc_primary_sec_nonaccrual_verified_2026-11-18.json")

PERIOD_LOOKUP = {
    "2026-03-31": ("March", "31", "2026-04-28"),
    "2026-06-30": ("June", "30", "2026-07-29"),
    "2026-09-30": ("September", "30", "2026-10-27"),
}
PARAGRAPH = re.compile(
    r"As of (?P<month>March|June|September) (?P<day>31|30), 2026 "
    r"and December 31, 2025,.*?"
    r"loans on non-accrual status represented "
    r"(?P<cost>\d+(?:\.\d+)?)% of the total investments at amortized cost "
    r"\(or (?P<fair>\d+(?:\.\d+)?)% at fair value\) and "
    r"(?P<prior_cost>\d+(?:\.\d+)?)% at amortized cost "
    r"\(or (?P<prior_fair>\d+(?:\.\d+)?)% at fair value\), respectively",
    re.I,
)


class OriginalEvidenceError(ValueError):
    pass


def parse_reported_nonaccrual(source_html: bytes, period_end: str) -> dict:
    if period_end not in PERIOD_LOOKUP:
        raise OriginalEvidenceError("unknown expected SEC period")
    document = html.unescape(re.sub(r"<[^>]+>", " ", source_html.decode("utf-8", "replace")))
    document = re.sub(r"\s+", " ", document)
    matches = list(PARAGRAPH.finditer(document))
    if len(matches) != 1:
        raise OriginalEvidenceError("missing or ambiguous source statement")
    statement = matches[0]
    month, day, filed = PERIOD_LOOKUP[period_end]
    if (statement["month"].lower() != month.lower() or statement["day"] != day
            or f"filed with the Securities and Exchange Commission" not in document):
        raise OriginalEvidenceError("period and original SEC disclosure mismatch")
    # The exact SEC filing date appears in the original press-release exhibit.
    date_label = dt.date.fromisoformat(filed).strftime("%B %-d, %Y")
    if date_label not in document:
        raise OriginalEvidenceError("SEC filing date missing from original")
    values = {
        "current_cost_pct": statement["cost"], "current_fair_value_pct": statement["fair"],
        "dec_2025_cost_pct": statement["prior_cost"],
        "dec_2025_fair_value_pct": statement["prior_fair"],
    }
    for value in values.values():
        v = Decimal(value)
        if not v.is_finite() or not 0 <= v <= 100:
            raise OriginalEvidenceError("invalid source percentage")
    return values


def verify(source_archive: Path, research_csv: Path = RESEARCH_CSV) -> dict:
    if hashlib.sha256(source_archive.read_bytes()).hexdigest() != ORIGINAL_ZIP_SHA:
        raise OriginalEvidenceError("original ARCC ZIP SHA mismatch")
    manual = read_checked(research_csv, dt.date(2026, 11, 18))
    if len(manual) != 8:
        raise OriginalEvidenceError("research source expected eight observed candidates")
    source_index = {(x["metric_id"], x["period_end"]): x for x in manual}
    if len(source_index) != 8:
        raise OriginalEvidenceError("duplicate issuer source metric")
    with zipfile.ZipFile(source_archive) as z:
        if hashlib.sha256(z.read("manifest.json")).hexdigest() != ORIGINAL_MANIFEST_SHA:
            raise OriginalEvidenceError("original manifest SHA mismatch")
        manifest = json.loads(z.read("manifest.json"))
        sources = manifest.get("sources", [])
        if (manifest.get("unique_primary_sources") != 4
                or manifest.get("archived_sources") != 4
                or manifest.get("independently_verified_pit") is not False
                or manifest.get("numeric_values_verified_against_raw") is not False
                or manifest.get("index_aics") is not None
                or len(sources) != 4):
            raise OriginalEvidenceError("original research archive claimed unsafe certification")
        expected_names = {x["sha256"] + ".html" for x in sources}
        if set(z.namelist()) != expected_names | {"manifest.json"}:
            raise OriginalEvidenceError("missing original SEC/issuer evidence")
        index = {}
        for item in sources:
            if item["status"] != "archived_raw_unverified":
                raise OriginalEvidenceError("source capture incomplete")
            raw = z.read(item["sha256"] + ".html")
            if (hashlib.sha256(raw).hexdigest() != item["sha256"]
                    or len(raw) != item["bytes"]):
                raise OriginalEvidenceError("source HTML content SHA mismatch")
            index[item["source_url"]] = (item, raw)

    # The 2025 annual issuer page is only a navigation shell: no disclosure.
    issuer = [v for url, v in index.items() if url.startswith("https://arcc.ares.com/")]
    if len(issuer) != 1 or b"non-accrual" in issuer[0][1].lower():
        raise OriginalEvidenceError("issuer shell status changed: re-review originals")
    originals = []
    verified = {}
    comparisons = []
    for period, (month, day, filing_date) in PERIOD_LOOKUP.items():
        candidates = [r for r in manual if r["period_end"] == period]
        if len(candidates) != 2:
            raise OriginalEvidenceError("missing period/denominator in research candidate")
        urls = {r["source_uri"] for r in candidates}
        if len(urls) != 1:
            raise OriginalEvidenceError("SEC metric candidates disagree on source")
        url = next(iter(urls))
        if not url.startswith("https://www.sec.gov/Archives/edgar/data/1287750/"):
            raise OriginalEvidenceError("wrong SEC accession host/issuer")
        if url not in index or any(row["filed_at"] != filing_date for row in candidates):
            raise OriginalEvidenceError("SEC original or filing-date metadata mismatch")
        item, raw = index[url]
        observed = parse_reported_nonaccrual(raw, period)
        for key, metric in (
            ("current_cost_pct", "nonaccrual_amortized_cost_pct"),
            ("current_fair_value_pct", "nonaccrual_fair_value_pct"),
        ):
            candidate = source_index[(metric, period)]
            if Decimal(candidate["value_pct"]) != Decimal(observed[key]):
                raise OriginalEvidenceError("issuer manually transcribed value conflicts with SEC")
        if (Decimal(observed["dec_2025_cost_pct"]) != Decimal(
                    source_index[("nonaccrual_amortized_cost_pct", "2025-12-31")]["value_pct"])
                or Decimal(observed["dec_2025_fair_value_pct"]) != Decimal(
                    source_index[("nonaccrual_fair_value_pct", "2025-12-31")]["value_pct"])):
            raise OriginalEvidenceError("SEC prior-period values disagree with input CSV")
        available = (dt.date.fromisoformat(filing_date) + dt.timedelta(days=14)).isoformat()
        if any(row["available_at"] != available for row in candidates):
            raise OriginalEvidenceError("14 calendar day SEC embargo violated")
        originals.append({
            "period_end": period, "SEC_exhibit_url": url, "SEC_source_sha256": item["sha256"],
            "SEC_filed_at": filing_date, "SEC_available_at": available,
            "nonaccrual_amortized_cost_percent": observed["current_cost_pct"],
            "nonaccrual_fair_value_percent": observed["current_fair_value_pct"],
            "original_verified": True, "released_historical_PIT_certified": False,
        })
        comparisons.append(observed)
    if len(originals) != 3 or len(comparisons) != 3:
        raise OriginalEvidenceError("not all dated SEC originals verified")
    for observation in comparisons:
        if (Decimal(observation["dec_2025_cost_pct"]) != Decimal("1.8")
                or Decimal(observation["dec_2025_fair_value_pct"]) != Decimal("1.2")):
            raise OriginalEvidenceError("December 2025 repeated SEC comparison drift")

    baseline = {
        "period_end": "2025-12-31", "nonaccrual_amortized_cost_percent": "1.8",
        "nonaccrual_fair_value_percent": "1.2",
        "earliest_verified_sec_filed_at": "2026-04-28",
        "earliest_verified_sec_available_at": "2026-05-12",
        "research_csv_claimed_issuer_available_at": "2026-02-18",
        "earlier_issuer_release_original_bytes_confirmed": False,
        "retrospectively_corrobated_by_sec_exhibits_count": 3,
    }
    return {
        "schema_version": "aics-arcc-sec-primary-nonaccrual-independent-raw-verification-v1",
        "research_as_of": "2026-11-18",
        "primary_original_archive_sha256": ORIGINAL_ZIP_SHA,
        "primary_archive_artifact_id": 14474764347,
        "original_source_html_rehashed": 4,
        "verified_sec_exhibit_originals": 3,
        "distinct_periods_with_verified_values": 4,
        "independently_verified_source_transcription_values": 8,
        "source_values": [baseline, *originals],
        "dec_2025_prior_values_independent_sec_crosschecks": 3,
        "last_nonaccrual_cost_pct": "2.4",
        "last_nonaccrual_fair_value_pct": "1.4",
        "cost_nonaccrual_change_since_dec2025_percentage_points": "0.6",
        "fair_value_nonaccrual_change_since_dec2025_percentage_points": "0.2",
        "earliest_verified_dec2025_disclosure_PIT_from_original": "2026-05-12",
        "earlier_february_issuer_release_PIT_attested": False,
        "historical_24mo_PIT_complete": False,
        "independent_24mo_predictive_OOS": False,
        "one_BDC_does_not_prove_entire_private_credit_market": True,
        "synthetic_financial_observations": 0,
        "private_credit_node_stress_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
        "notes": [
            "The issuer February 2026 URL returned a 3555-byte shell without the asserted figures; do not assign February available_at as proved.",
            "SEC Q1/Q2/Q3 exhibits explicitly state current quarter nonaccrual and prior Dec 2025 data; identical prior values appear in all three.",
            "For December 2025, first actual archived source is SEC Q1, filed 2026-04-28; a separate original issuer announcement would be required to prove earlier availability.",
            "Original SEC HTML is primary source for numeric values; source-to-model PIT/OOS calibration and representative sector coverage are not complete.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        result = verify(args.archive)
    except (OriginalEvidenceError, KeyError, ValueError, OSError, zipfile.BadZipFile) as exc:
        print("AICS ARCC primary figures BLOCKED:", type(exc).__name__)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "verified_raw_source_values": result["independently_verified_source_transcription_values"],
        "original_SEC_exhibits": result["verified_sec_exhibit_originals"],
        "february_issuer_release_original_proved": False,
        "private_credit_node_stress_score": None,
        "aics_index": None,
        "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
