#!/usr/bin/env python3
"""Compare original SEC non-accrual disclosures for ARCC and OBDC without pooling.

Never infer a market stress score from two selected BDCs or add/average
non-accrual percentages with different denominator definitions. Period-end
is not a public-release timestamp; SEC candidate available_at = filed_at+14d.
No synthetic rows, retrospective look-ahead, or 24m OOS certification.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

ARCC_SOURCE = Path("aics_data/research/arcc_q4_sec_corrected_nonaccrual_sources_2026-11-18.json")
OBDC_SOURCE = Path("aics_data/research/obdc_original_nonaccrual_source_receipt_2026-11-19.json")
OUT = Path("docs/audit/aics_private_credit_two_bdc_verified_asof_research_2026-11-19.json")

ARCC_DATES = {
    "2024-12-31": ("2026-02-04", "2026-02-18"),
    "2025-12-31": ("2026-02-04", "2026-02-18"),
    "2026-03-31": ("2026-04-28", "2026-05-12"),
    "2026-06-30": ("2026-07-29", "2026-08-12"),
    "2026-09-30": ("2026-10-27", "2026-11-10"),
}
OBDC_DATES = {
    "2026-03-31": ("2026-05-06", "2026-05-20"),
    "2026-06-30": ("2026-08-05", "2026-08-19"),
    "2026-09-30": ("2026-11-04", "2026-11-18"),
}


class ComparisonError(ValueError):
    pass


def _date(value: object) -> dt.date:
    if not isinstance(value, str):
        raise ComparisonError("invalid SEC date type")
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise ComparisonError("invalid SEC date format") from None


def _sha(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch("[a-f0-9]{64}", value) is not None


def _percent(value: object) -> Decimal:
    if not isinstance(value, str):
        raise ComparisonError("not source original numeric percent")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ComparisonError("invalid source percentage") from None
    if not number.is_finite() or not 0 <= number <= 100:
        raise ComparisonError("source percentage out of range")
    return number


def _check_arcc(raw: dict) -> list[dict]:
    if (raw.get("schema_version") != "aics-arcc-q4-sec-corrected-durable-source-panel-v1"
            or raw.get("confirmed_source_values") != 10
            or raw.get("source_periods") != 5
            or raw.get("node_weight") != 150
            or raw.get("synthetic_market_rows") != 0
            or raw.get("complete_24_month_market_pit") is not False
            or raw.get("independently_verified_release_time_archive") is not False
            or raw.get("independent_24_month_predictive_oos") is not False
            or raw.get("index_aics") is not None
            or raw.get("private_credit_node_stress_score") is not None
            or raw.get("promotion") != "BLOCKED"
            or not _sha(raw.get("reverified_timeline_report_sha256"))):
        raise ComparisonError("ARCC original source receipt not independently safe")
    sources = raw.get("observed_source_periods")
    if not isinstance(sources, list) or len(sources) != 5:
        raise ComparisonError("missing ARCC SEC reporting periods")
    out = []
    for record in sources:
        period = record.get("period_end")
        if period not in ARCC_DATES:
            raise ComparisonError("unknown ARCC original period")
        filing, available = ARCC_DATES[period]
        if (record.get("source_filed_at") != filing
                or record.get("available_at") != available
                or record.get("model_eligible") is not False
                or not _sha(record.get("source_sha256"))
                or not record.get("source_url", "").startswith(
                    "https://www.sec.gov/Archives/edgar/data/1287750/")):
            raise ComparisonError("ARCC source provenance or +14 date changed")
        out.append({
            "issuer": "ARCC", "period_end": period,
            "filed_at": filing, "available_at": available,
            "cost_pct": _percent(record.get("cost_pct")),
            "fair_pct": _percent(record.get("fair_value_pct")),
            "source_html_sha256": record["source_sha256"],
            "source_url": record["source_url"],
            "retrospective_comparative_only": period == "2024-12-31",
        })
    if len({r["period_end"] for r in out}) != 5:
        raise ComparisonError("duplicated ARCC periods")
    return out


def _check_obdc(raw: dict) -> list[dict]:
    if (raw.get("schema_version") != "aics-obdc-original-sec-nonaccrual-permanent-receipt-v1"
            or raw.get("issuer") != "OBDC"
            or raw.get("issuer_cik") != "0001655888"
            or raw.get("original_html_file_count") != 6
            or raw.get("source_period_count") != 3
            or raw.get("independent_original_sha_recheck") is not True
            or raw.get("historical_release_pit_independently_attested") is not False
            or raw.get("untouched_24m_oos") is not False
            or raw.get("synthetic_rows") != 0
            or raw.get("private_credit_score") is not None
            or raw.get("aics_index") is not None
            or raw.get("promotion") != "BLOCKED"
            or not _sha(raw.get("source_actions_archive_sha256"))):
        raise ComparisonError("OBDC original source receipt not independently safe")
    sources = raw.get("original_periods")
    if not isinstance(sources, list) or len(sources) != 3:
        raise ComparisonError("missing OBDC original SEC quarters")
    out = []
    for record in sources:
        period = record.get("period_end")
        if period not in OBDC_DATES:
            raise ComparisonError("unknown OBDC quarter")
        filing, available = OBDC_DATES[period]
        if (record.get("filed_at") != filing or record.get("available_at") != available
                or not _sha(record.get("index_sha256"))
                or not _sha(record.get("exhibit_sha256"))):
            raise ComparisonError("OBDC source provenance or +14 SEC date changed")
        out.append({
            "issuer": "OBDC", "period_end": period,
            "filed_at": filing, "available_at": available,
            "cost_pct": _percent(record.get("cost_pct")),
            "fair_pct": _percent(record.get("fair_pct")),
            "source_html_sha256": record["exhibit_sha256"],
            "source_accession": record["accession"],
            "retrospective_comparative_only": False,
        })
    if len({r["period_end"] for r in out}) != 3:
        raise ComparisonError("duplicated OBDC period")
    return out


def compare(arcc: dict, obdc: dict, as_of: dt.date) -> dict:
    first = _check_arcc(arcc)
    second = _check_obdc(obdc)
    for item in first + second:
        period, filed, available = (_date(item[k]) for k in
                                    ("period_end", "filed_at", "available_at"))
        if available != filed + dt.timedelta(days=14) or period > filed:
            raise ComparisonError("SEC available_at or reporting period look-ahead")
    eligible = [x for x in first + second if _date(x["available_at"]) <= as_of]
    by_issuer: dict[str, list[dict]] = {
        ticker: sorted((x for x in eligible if x["issuer"] == ticker),
                       key=lambda x: x["period_end"])
        for ticker in ("ARCC", "OBDC")
    }
    period_values = {
        ticker: {r["period_end"]: r for r in rows}
        for ticker, rows in by_issuer.items()
    }
    aligned = []
    for period in sorted(set(ARCC_DATES) & set(OBDC_DATES)):
        if period not in period_values["ARCC"] or period not in period_values["OBDC"]:
            continue
        a, b = period_values["ARCC"][period], period_values["OBDC"][period]
        aligned.append({
            "period_end": period,
            "ARCC_cost_pct": str(a["cost_pct"]),
            "ARCC_fair_pct": str(a["fair_pct"]),
            "OBDC_cost_pct": str(b["cost_pct"]),
            "OBDC_fair_pct": str(b["fair_pct"]),
            "ARCC_minus_OBDC_cost_percentage_points": str(a["cost_pct"] - b["cost_pct"]),
            "ARCC_minus_OBDC_fair_percentage_points": str(a["fair_pct"] - b["fair_pct"]),
            "both_filings_available_at": max(a["available_at"], b["available_at"]),
        })
    historical = []
    for ticker, rows in by_issuer.items():
        historical.extend([{
            **{k: (str(v) if isinstance(v, Decimal) else v) for k, v in item.items()},
            "original_live_historical_source_archive_attested": False,
            "node_score_eligible": False,
        } for item in rows])
    latest_aligned = aligned[-1] if aligned else None
    return {
        "schema_version": "aics-privatecredit-two-bdc-original-sec-asof-research-v1",
        "as_of": as_of.isoformat(), "research_only": True,
        "verified_original_sec_issuers": sorted(by_issuer),
        "total_source_periods_original": 8,
        "original_nonaccrual_values_total": 16,
        "asof_visible_original_values": len(historical) * 2,
        "asof_visible_by_issuer": {
            ticker: len(rows) * 2 for ticker, rows in by_issuer.items()
        },
        "source_observations_by_issuer": historical,
        "same_quarter_comparisons": aligned,
        "latest_comparable_period": latest_aligned["period_end"] if latest_aligned else None,
        "latest_comparison": latest_aligned,
        "underlying_original_sources": {
            "ARCC_Q4_Q1Q3_report_sha256": arcc["reverified_timeline_report_sha256"],
            "OBDC_original_sec_artifact_zip_sha256": obdc["source_actions_archive_sha256"],
        },
        "SEC_embargo_calendar_days": 14,
        "cross_issuer_aggregation_or_average_performed": False,
        "issuer_weights_not_derived_from_future_exposures": True,
        "market_sector_representativeness_verified": False,
        "synthetic_observations_created": 0,
        "historical_pit_release_attested": False,
        "untouched_24_month_predictive_oos": False,
        "private_credit_node_score": None,
        "index_aics": None, "promotion": "BLOCKED",
        "limitations": [
            "ARCC/OBDC are only two listed BDCs; they do not represent the full private credit or AI-credit sector.",
            "Current-capture SEC originals establish issuer filing dates but not independent historical feed vintages.",
            "No averaging of loan cost versus fair-value denominator; no AICS 0–100 score.",
            "The 2024 ARCC comparative appeared in a February 2026 original SEC exhibit: it is excluded for any 2024 as-of date.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default="2026-11-19")
    p.add_argument("--arcc", type=Path, default=ARCC_SOURCE)
    p.add_argument("--obdc", type=Path, default=OBDC_SOURCE)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    try:
        result = compare(json.loads(args.arcc.read_text(encoding="utf-8")),
                         json.loads(args.obdc.read_text(encoding="utf-8")),
                         _date(args.as_of))
    except (OSError, ComparisonError, ValueError, KeyError, TypeError) as exc:
        print("AICS private credit cross-issuer BLOCKED:", type(exc).__name__)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "issuers": len(result["verified_original_sec_issuers"]),
        "visible_values": result["asof_visible_original_values"],
        "latest_aligned_q": result["latest_comparable_period"],
        "stress_score": None, "aics_index": None,
        "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
