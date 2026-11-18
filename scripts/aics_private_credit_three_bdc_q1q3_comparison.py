#!/usr/bin/env python3
"""Observed SEC non-accrual values: ARCC, OBDC, BXSL in 2026 Q1/Q2/Q3.

Never pool fair-value and amortized-cost denominators; never invent 24 months.
SEC disclosure cutoff is original filing +14 calendar days. Current captures
of original SEC HTML do not independently attest historical delivery feeds.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from decimal import Decimal
from pathlib import Path

from scripts.aics_private_credit_three_bdc_asof import (
    ARCC_SOURCE, OBDC_SOURCE, BXSL, build as legacy_three_bdc, ComparisonError,
)

Q1Q2 = Path("aics_data/research/bxsl_q1_q2_original_nonaccrual_source_receipt_2026-11-19.json")
OUT = Path("docs/audit/aics_private_credit_3bdc_3quarter_source_panel_2026-11-19.json")
EXPECTED_BXSL = {
    "2026-03-31": ("2026-05-07", "2026-05-21", "4.7", "3.1", "0001213900-26-053022"),
    "2026-06-30": ("2026-08-06", "2026-08-20", "3.6", "1.8", "0001213900-26-085889"),
}
QUARTERS = ("2026-03-31", "2026-06-30", "2026-09-30")
ISSUERS = ("ARCC", "BXSL", "OBDC")


def _sha(raw):
    return isinstance(raw, str) and re.fullmatch("[a-f0-9]{64}", raw) is not None


def _source_bxsl_q1q2(receipt: dict) -> list[dict]:
    if (
        receipt.get("schema_version") != "aics-bxsl-original-sec-q1q2-independent-raw-receipt-v1"
        or receipt.get("issuer") != "BXSL"
        or receipt.get("sec_cik") != "0001736035"
        or receipt.get("source_actions_run_id") != 44418371941
        or receipt.get("source_actions_artifact_id") != 14480427253
        or receipt.get("original_html_documents_independently_rehashed") != 6
        or receipt.get("independent_archive_sha_verified") is not True
        or receipt.get("quarter_periods") != 2
        or receipt.get("verified_original_disclosed_nonaccrual_values") != 4
        or receipt.get("SEC_available_at_filed_at_plus_days") != 14
        or receipt.get("cost_vs_fair_denominators_not_interchangeable") is not True
        or receipt.get("live_historical_release_feed_independently_attested") is not False
        or receipt.get("independent_24m_oos") is not False
        or receipt.get("synthetic_financial_observations") != 0
        or receipt.get("private_credit_node_stress_score") is not None
        or receipt.get("index_aics") is not None
        or receipt.get("promotion") != "BLOCKED"
        or not _sha(receipt.get("source_archive_zip_sha256"))
        or not _sha(receipt.get("source_archive_manifest_sha256"))
    ):
        raise ComparisonError("BXSL earlier originals receipt incomplete or unsafe")
    x = receipt.get("source_periods")
    if not isinstance(x, list) or len(x) != 2:
        raise ComparisonError("requires two genuine Q1/Q2 original disclosures")
    found = {}
    for item in x:
        date = item.get("period_end")
        if date not in EXPECTED_BXSL or date in found:
            raise ComparisonError("duplicate, missing or unfamiliar BXSL original period")
        filed, available, cost, fair, accession = EXPECTED_BXSL[date]
        if (item.get("filed_at") != filed or item.get("available_at") != available
                or item.get("sec_accession") != accession
                or dt.date.fromisoformat(available) != dt.date.fromisoformat(filed) + dt.timedelta(days=14)):
            raise ComparisonError("SEC 14-day embargo or original accession mismatch")
        if (Decimal(item.get("cost_pct")) != Decimal(cost)
                or Decimal(item.get("fair_pct")) != Decimal(fair)
                or not _sha(item.get("original_file_sha256", {}).get("index"))
                or not _sha(item.get("original_file_sha256", {}).get("filing"))
                or not _sha(item.get("original_file_sha256", {}).get("exhibit"))
                or not item.get("exhibit_url", "").startswith(
                    "https://www.sec.gov/Archives/edgar/data/1736035/")):
            raise ComparisonError("source original rates or SHA mismatch")
        if (set(item.get("original_file_sha256", {})) != {"index", "filing", "exhibit"}
                or set(item.get("original_file_bytes", {})) != {"index", "filing", "exhibit"}):
            raise ComparisonError("original SEC file inventory mismatch")
        if any(n < 250 for n in item["original_file_bytes"].values()):
            raise ComparisonError("original SEC document unexpectedly short")
        found[date] = {
            "issuer": "BXSL", "period_end": date,
            "cost_pct": str(Decimal(cost)), "fair_pct": str(Decimal(fair)),
            "filed_at": filed, "available_at": available,
            "source_exhibit_html_sha256": item["original_file_sha256"]["exhibit"],
            "score_eligible": False, "source_release_feed_PIT_attested": False,
        }
    if set(found) != set(EXPECTED_BXSL):
        raise ComparisonError("original BXSL quarterly source incomplete")
    return [found[d] for d in sorted(found)]


def build(arcc: dict, obdc: dict, bxsl_q3: dict, bxsl_q1q2: dict,
          as_of: dt.date) -> dict:
    old = legacy_three_bdc(arcc, obdc, bxsl_q3, as_of)
    earlier = _source_bxsl_q1q2(bxsl_q1q2)
    current = old["2026Q3_nonaccrual_source_matrix"]
    source_rows: dict[tuple[str, str], dict] = {}
    for item in current:
        issuer = item["issuer"]
        date = item["reporting_period_end"]
        if date != "2026-09-30" or issuer not in ISSUERS:
            raise ComparisonError("original Q3 panel unknown issuer or period")
        source_rows[(issuer, date)] = {
            "issuer": issuer, "period_end": date,
            "cost_pct": item["nonaccrual_cost_pct"],
            "fair_pct": item["nonaccrual_fair_pct"],
            "available_at": item["SEC_available_at"],
        }
    for item in old.get("source_values_visible_per_issuer", {}):
        if item not in ISSUERS:
            raise ComparisonError("unrecognized original SEC issuer")
    # The old comparison is authoritative for ARCC & OBDC earlier dated
    # quarters; it uses the actual source receipts and +14 calendar days.
    # Reconstruct only from original inputs, not from future-facing Q3 rows.
    from scripts.aics_private_credit_cross_issuer_research import compare
    two = compare(arcc, obdc, as_of)
    for row in two["source_observations_by_issuer"]:
        key = (row["issuer"], row["period_end"])
        if row["period_end"] not in QUARTERS:
            continue
        if key in source_rows:
            if (
                row["available_at"] != source_rows[key]["available_at"]
                or Decimal(row["cost_pct"]) != Decimal(source_rows[key]["cost_pct"])
                or Decimal(row["fair_pct"]) != Decimal(source_rows[key]["fair_pct"])
            ):
                raise ComparisonError("Q3 source different between independent verified receipts")
        source_rows[key] = {
            "issuer": row["issuer"], "period_end": row["period_end"],
            "cost_pct": row["cost_pct"], "fair_pct": row["fair_pct"],
            "available_at": row["available_at"],
        }
    for item in earlier:
        if dt.date.fromisoformat(item["available_at"]) > as_of:
            continue
        key = (item["issuer"], item["period_end"])
        if key in source_rows:
            raise ComparisonError("duplicate original BXSL quarter")
        source_rows[key] = {
            "issuer": item["issuer"], "period_end": item["period_end"],
            "cost_pct": item["cost_pct"], "fair_pct": item["fair_pct"],
            "available_at": item["available_at"],
        }
    for row in source_rows.values():
        if row["available_at"] > as_of.isoformat():
            raise ComparisonError("later SEC filing leaked before as-of")
    rows = []
    for quarter in QUARTERS:
        recs = [source_rows[(issuer, quarter)] for issuer in ISSUERS
                if (issuer, quarter) in source_rows]
        fully_visible = len(recs) == 3
        rows.append({
            "quarter_end": quarter,
            "visible_issuer_count": len(recs),
            "three_way_ready_at_this_asof": fully_visible,
            "last_original_SEC_available_at": max((x["available_at"] for x in recs), default=None),
            "source_observations": recs,
            "issuer_averaged_nonaccrual": None,
            "posthoc_market_weighted_score": None,
        })
    q3 = rows[-1]
    return {
        "schema_version": "aics-private-credit-3issuer-3quarter-real-sec-asof-research-v1",
        "as_of": as_of.isoformat(),
        "issuer_universe": list(ISSUERS),
        "original_issuer_periods_all_sources": 11,
        "original_separately_reported_numeric_values_all_sources": 22,
        "asof_visible_quarter_values": len(source_rows) * 2,
        "three_way_comparison_quarters_available": sum(x["three_way_ready_at_this_asof"] for x in rows),
        "three_quarter_issuer_panel": rows,
        "earliest_complete_three_issuer_2026_q1_date": "2026-05-21",
        "earliest_complete_three_issuer_2026_q2_date": "2026-08-20",
        "earliest_complete_three_issuer_2026_q3_date": "2026-11-18",
        "source_original_archive_zips_sha256": {
            **old["original_source_zip_sha256s"],
            "BXSL_2026Q1Q2_original_6_html_zip_sha256": bxsl_q1q2["source_archive_zip_sha256"],
        },
        "SEC_available_at_calendar_lag_days": 14,
        "cross_issuer_rate_averages": None,
        "issuer_exposure_weights": None,
        "synthetic_rows": 0,
        "original_realtime_feed_PIT_attested": False,
        "heldout_24_month_predictive_oos": False,
        "private_credit_node_stress_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
        "limitations": [
            "Three public BDCs are not the whole AI infrastructure private credit market.",
            "Only Q1 Q2 Q3 2026 three-way matched disclosure quarters; no 24-month untouched OOS.",
            "Cost and fair-value non-accrual use separate denominators, and cross-issuer averages are prohibited.",
            "Issuer filing date plus 14d is not independent contemporaneous data-feed timestamp attestation.",
            "ARCC 2024 comparative visible only with a 2026 filing; excluded from 2024 PIT.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default="2026-11-19")
    p.add_argument("--arcc", type=Path, default=ARCC_SOURCE)
    p.add_argument("--obdc", type=Path, default=OBDC_SOURCE)
    p.add_argument("--bxsl-q3", type=Path, default=BXSL)
    p.add_argument("--bxsl-q1q2", type=Path, default=Q1Q2)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    try:
        d = build(
            json.loads(args.arcc.read_text(encoding="utf-8")),
            json.loads(args.obdc.read_text(encoding="utf-8")),
            json.loads(args.bxsl_q3.read_text(encoding="utf-8")),
            json.loads(args.bxsl_q1q2.read_text(encoding="utf-8")),
            dt.date.fromisoformat(args.as_of),
        )
    except (OSError, KeyError, ValueError, TypeError) as exc:
        print(json.dumps({"promotion": "BLOCKED", "error": type(exc).__name__}))
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "issuers": len(d["issuer_universe"]),
        "issuer_periods": d["original_issuer_periods_all_sources"],
        "original_values": d["original_separately_reported_numeric_values_all_sources"],
        "three_way_quarters_visible": d["three_way_comparison_quarters_available"],
        "AICS": None, "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
