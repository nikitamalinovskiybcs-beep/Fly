#!/usr/bin/env python3
"""Supersede ARCC issuer-shell date gap using authentic Feb 4 SEC Q4 8-K EX-99.1.

TWO exact independently hashed GitHub Actions archives are required:
- 2026-02-04 8-K index and exhibit with 2025Q4 and 2024Q4 comparisons;
- original 2026 Q1/Q2/Q3 SEC exhibits verifying current & prior values.
SEC available_at = filed_at + 14 calendar days. Historic observations reported
in later filings are NOT backdated to the quarter they describe. Only
research candidate as-of visibility is reconstructed, never certified PIT,
24m OOS, Private Credit node score or AICS.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import zipfile
from decimal import Decimal
from pathlib import Path

from scripts.aics_collect_arcc_q4_sec_original import verify_original
from scripts.aics_verify_arcc_original_nonaccrual import verify as verify_2026_quarters

Q4_ARTIFACT_ID = 14476018751
Q4_ZIP_SHA256 = "b06e94299ccb723174341fef2dc678e9f3924028bedf044646685b94f2e944d8"
Q4_MANIFEST_SHA256 = "51b8df9181667ee58df0baf6eb9e8e6a1e9961482510086994c628d9274a265b"
Q1Q3_ARTIFACT_ID = 14474764347
Q1Q3_ZIP_SHA256 = "805c1b5d692625b1d2d7c0c9ebb56986187d92eb6f10015e1bb3e79ce103d7d6"
REPORT = Path("docs/audit/aics_arcc_q4_sec_corrected_pit_timeline_2026-11-18.json")
PERIODS = ("2024-12-31", "2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30")
SCENARIOS = (
    "2026-02-17", "2026-02-18", "2026-05-11", "2026-05-12",
    "2026-08-11", "2026-08-12", "2026-11-09", "2026-11-10",
    "2026-11-18",
)


class ReconciliationError(ValueError):
    pass


def original_q4_report(archive: Path) -> dict:
    if hashlib.sha256(archive.read_bytes()).hexdigest() != Q4_ZIP_SHA256:
        raise ReconciliationError("Q4 original SEC archive ZIP digest mismatch")
    with zipfile.ZipFile(archive) as z:
        if set(z.namelist()) != {
            "manifest.json", "sec_q4_index_original.html", "sec_q4_exhibit99_1_original.html",
        }:
            raise ReconciliationError("Q4 source inventory incomplete or unexpected")
        manifest_bytes = z.read("manifest.json")
        if hashlib.sha256(manifest_bytes).hexdigest() != Q4_MANIFEST_SHA256:
            raise ReconciliationError("Q4 original SEC manifest digest mismatch")
        manifest = json.loads(manifest_bytes)
        actual = verify_original(
            z.read("sec_q4_index_original.html"),
            z.read("sec_q4_exhibit99_1_original.html"),
        )
        if actual != manifest:
            raise ReconciliationError("SEC original Q4 bytes differ from capture receipt")
        return actual


def build(q4: dict, q1q3: dict) -> dict:
    if (
        q4.get("schema_version") != "aics-arcc-q4-2025-sec-exhibit-original-v1"
        or q4.get("filing_accession") != "0001287750-26-000004"
        or q4.get("filing_date") != "2026-02-04"
        or q4.get("available_at") != "2026-02-18"
        or q4.get("source_values_verified_against_original_sec") is not True
        or q4.get("filed_at_plus_14_date_gate_passed") is not True
        or q4.get("independently_attested_contemporaneous_publication") is not False
        or q4.get("index_aics") is not None
        or q4.get("promotion") != "BLOCKED"
        or q1q3.get("schema_version") != "aics-arcc-sec-primary-nonaccrual-independent-raw-verification-v1"
        or q1q3.get("verified_sec_exhibit_originals") != 3
        or q1q3.get("original_source_html_rehashed") != 4
        or q1q3.get("independently_verified_source_transcription_values") != 8
        or q1q3.get("historical_24mo_PIT_complete") is not False
        or q1q3.get("index_aics") is not None
        or q1q3.get("promotion") != "BLOCKED"
    ):
        raise ReconciliationError("source data not original-verified or attempted model promotion")
    old = q1q3["source_values"]
    if len(old) != 4 or [item["period_end"] for item in old] != list(PERIODS[1:]):
        raise ReconciliationError("missing or out-of-order original SEC disclosure periods")
    if (Decimal(q4["nonaccrual_amortized_cost_pct"]) != Decimal(old[0]["nonaccrual_amortized_cost_percent"])
            or Decimal(q4["nonaccrual_fair_value_pct"]) != Decimal(old[0]["nonaccrual_fair_value_percent"])
            or old[0]["earliest_verified_sec_available_at"] != "2026-05-12"
            or old[0]["earlier_issuer_release_original_bytes_confirmed"] is not False):
        raise ReconciliationError("new authentic Q4 SEC original disagrees with the prior limited shell-era receipt")

    periods = []
    q4filed, q4available = q4["filing_date"], q4["available_at"]
    for period, cost, fair, filed, available, url, sha, evidence_type in (
        ("2024-12-31", q4["prior_dec2024_cost_pct"], q4["prior_dec2024_fair_value_pct"],
            q4filed, q4available, q4["exhibit_url"], q4["raw_exhibit_sha256"],
            "RETROSPECTIVE_PRIOR_YEAR_COMPARATIVE_IN_2025Q4_8K"),
        ("2025-12-31", q4["nonaccrual_amortized_cost_pct"], q4["nonaccrual_fair_value_pct"],
            q4filed, q4available, q4["exhibit_url"], q4["raw_exhibit_sha256"],
            "CURRENT_QUARTER_AUTHENTIC_2025Q4_8K"),
        *[
            (item["period_end"], item["nonaccrual_amortized_cost_percent"],
             item["nonaccrual_fair_value_percent"], item["SEC_filed_at"],
             item["SEC_available_at"], item["SEC_exhibit_url"],
             item["SEC_source_sha256"], "CURRENT_QUARTER_AUTHENTIC_SEC_EXHIBIT")
            for item in old[1:]
        ],
    ):
        date = dt.date.fromisoformat(period)
        filing = dt.date.fromisoformat(filed)
        avail = dt.date.fromisoformat(available)
        if not (date <= filing and filing + dt.timedelta(days=14) == avail
                and avail <= dt.date(2026, 11, 18)):
            raise ReconciliationError("SEC +14 or observation chronology violation")
        if len(sha) != 64 or not url.startswith("https://www.sec.gov/Archives/edgar/data/1287750/"):
            raise ReconciliationError("source provenance missing or unapproved")
        periods.append({
            "period_end": period, "source_filed_at": filed,
            "aics_eligible_date_after_sec_14d": available,
            "nonaccrual_amortized_cost_pct": str(Decimal(cost)),
            "nonaccrual_fair_value_pct": str(Decimal(fair)),
            "source_html_sha256": sha, "source_url": url,
            "evidence_kind": evidence_type, "independent_original_sec_value_verified": True,
            "independent_historical_publication_time_attested": False,
            "model_eligible": False,
        })
    if len(periods) != len(PERIODS):
        raise ReconciliationError("unexpected quarterly source coverage")

    visibility = []
    for query in SCENARIOS:
        queryday = dt.date.fromisoformat(query)
        visible = [row for row in periods
                   if dt.date.fromisoformat(row["aics_eligible_date_after_sec_14d"]) <= queryday
                   and dt.date.fromisoformat(row["period_end"]) <= queryday]
        latest = max(visible, key=lambda x: x["period_end"]) if visible else None
        visibility.append({
            "evaluation_as_of": query,
            "visible_original_source_verified_periods": len(visible),
            "visible_source_verified_values": len(visible) * 2,
            "latest_visible_period_end": latest["period_end"] if latest else None,
            "latest_nonaccrual_cost_pct": latest["nonaccrual_amortized_cost_pct"] if latest else None,
            "latest_nonaccrual_fair_value_pct": latest["nonaccrual_fair_value_pct"] if latest else None,
            "node_score": None,
        })

    first, last = periods[1], periods[-1]  # 2025Q4 -> 2026Q3; no false 2024 release
    return {
        "schema_version": "aics-arcc-q4-exhibit-corrected-sec-asof-source-research-v1",
        "research_as_of": "2026-11-18",
        "supersedes_research_document": "docs/audit/aics_arcc_conservative_pit_timeline_2026-11-18.json",
        "reason_for_correction": (
            "Authentic original Feb 4 2026 SEC 8-K accession verifies December 2025 "
            "figures that the previously archived issuer webpage shell could not prove."
        ),
        "earlier_unproven_issuer_shell_date": "2026-02-18",
        "new_verified_sec_8k_available_at": "2026-02-18",
        "first_original_sec_exhibit_file_sha256": q4["raw_exhibit_sha256"],
        "source_artifact_provenance": {
            "q4_zip_id": Q4_ARTIFACT_ID, "q4_zip_sha256": Q4_ZIP_SHA256,
            "q1q3_zip_id": Q1Q3_ARTIFACT_ID, "q1q3_zip_sha256": Q1Q3_ZIP_SHA256,
        },
        "source_verified_disclosed_periods": periods,
        "historical_as_of_scenarios": visibility,
        "raw_original_html_documents_rehashed": 6,
        "distinct_observation_periods": 5,
        "source_verified_nonaccrual_values": 10,
        "2025_december_to_2026_september_cost_change_pp": str(
            Decimal(last["nonaccrual_amortized_cost_pct"]) - Decimal(first["nonaccrual_amortized_cost_pct"])
        ),
        "2025_december_to_2026_september_fair_value_change_pp": str(
            Decimal(last["nonaccrual_fair_value_pct"]) - Decimal(first["nonaccrual_fair_value_pct"])
        ),
        "retrospective_2024_value_visible_in_2024": False,
        "SEC_14_calendar_day_rule_enforced": True,
        "synthetic_rows_created": 0,
        "historical_24m_pit_attested": False,
        "independent_24m_oos": False,
        "one_issuer_not_entire_private_credit_node": True,
        "private_credit_node_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
        "notes": [
            "The 2024Q4 comparative was printed in 2026Q4 source about 2025Q4; not contemporaneous in 2024.",
            "Feb 18 2026 is now based on SEC accession with original HTML, not the unverifiable issuer shell.",
            "Each as-of is a research eligibility reconstruction, not an independent live-time release archive.",
            "Only one ARCC issuer with 5 observation periods; 24-month independent PIT/OOS not certified.",
        ],
    }


def derive(q4_archive: Path, prior_archive: Path) -> dict:
    q4 = original_q4_report(q4_archive)
    if hashlib.sha256(prior_archive.read_bytes()).hexdigest() != Q1Q3_ZIP_SHA256:
        raise ReconciliationError("original Q1-Q3 SEC archive digest mismatch")
    prior = verify_2026_quarters(prior_archive)
    if prior.get("primary_original_archive_sha256") != Q1Q3_ZIP_SHA256:
        raise ReconciliationError("original Q1-Q3 SEC receipt digest mismatch")
    return build(q4, prior)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--q4-archive", type=Path, required=True)
    parser.add_argument("--q1q3-archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=REPORT)
    args = parser.parse_args()
    try:
        report = derive(args.q4_archive, args.q1q3_archive)
    except (ReconciliationError, ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        print("ARCC original SEC Q4 chronology BLOCKED:", type(exc).__name__)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps({
        "original_sec_values": report["source_verified_nonaccrual_values"],
        "proven_source_periods": report["distinct_observation_periods"],
        "first_dec2025_sec_asof": report["new_verified_sec_8k_available_at"],
        "index_aics": None, "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
