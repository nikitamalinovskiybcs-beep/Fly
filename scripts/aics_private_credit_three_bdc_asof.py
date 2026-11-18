#!/usr/bin/env python3
"""Three BDC original SEC source-derived Private Credit comparison, not a score.

ARCC 2026 Q1-Q3, OBDC 2026 Q1-Q3 and BXSL 2026 Q3; no
interpolation or cross-issuer averaging. SEC +14 is mandatory and a
filing period is never a market timestamp.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from decimal import Decimal
from pathlib import Path

from scripts.aics_private_credit_cross_issuer_research import (
    ARCC_SOURCE, OBDC_SOURCE, compare, ComparisonError,
)

BXSL = Path("aics_data/research/bxsl_original_nonaccrual_source_receipt_2026-11-19.json")
OUT = Path("docs/audit/aics_private_credit_three_bdcs_asof_2026-11-19.json")


def check_bxsl(source: dict) -> dict:
    if (
        source.get("schema_version") != "aics-bxsl-original-sec-q3-permanent-source-receipt-v1"
        or source.get("issuer") != "BXSL"
        or source.get("cik") != "0001736035"
        or source.get("sec_accession") != "0001213900-26-115721"
        or source.get("source_filed_at") != "2026-11-04"
        or source.get("source_available_at") != "2026-11-18"
        or source.get("period_end") != "2026-09-30"
        or source.get("raw_originals_rehashed") != 3
        or source.get("source_values_verified") != 2
        or source.get("different_metric_denominators") is not True
        or source.get("same_cost_footnote_disclosed_twice") is not True
        or source.get("original_realtime_release_feed_attested") is not False
        or source.get("independent_24m_oos") is not False
        or source.get("synthetic_observations_created") != 0
        or source.get("node_score") is not None
        or source.get("index_aics") is not None
        or source.get("promotion") != "BLOCKED"
    ):
        raise ComparisonError("BXSL original-source receipt not eligible for even research")
    for k in (
        "source_archive_zip_sha256", "source_archive_manifest_sha256",
        "source_index_html_sha256", "source_8k_html_sha256",
        "source_exhibit_html_sha256",
    ):
        if not isinstance(source.get(k), str) or not re.fullmatch("[a-f0-9]{64}", source[k]):
            raise ComparisonError("original BXSL SHA provenance missing")
    cost = Decimal(source["nonaccrual_amortized_cost_pct"])
    fair = Decimal(source["nonaccrual_fair_value_pct"])
    if not cost.is_finite() or not fair.is_finite() or cost != Decimal("2.8") or fair != Decimal("2.1"):
        raise ComparisonError("BXSL original nonaccrual values changed")
    if dt.date.fromisoformat(source["source_available_at"]) != (
        dt.date.fromisoformat(source["source_filed_at"]) + dt.timedelta(days=14)
    ):
        raise ComparisonError("BXSL filing embargo invalid")
    return {
        "issuer": "BXSL", "period_end": source["period_end"],
        "source_filed_at": source["source_filed_at"],
        "available_at": source["source_available_at"],
        "nonaccrual_cost_pct": str(cost),
        "nonaccrual_fair_pct": str(fair),
        "source_exhibit_sha256": source["source_exhibit_html_sha256"],
        "denominators_explicitly_different": True,
        "independently_attested_live_release_time": False,
        "node_score_eligible": False,
    }


def build(arcc: dict, obdc: dict, bxsl: dict, asof: dt.date) -> dict:
    original_two = compare(arcc, obdc, asof)
    third = check_bxsl(bxsl)
    bxsl_visible = asof >= dt.date.fromisoformat(third["available_at"])
    q3matrix = {
        row["issuer"]: row for row in original_two["source_observations_by_issuer"]
        if row["period_end"] == "2026-09-30"
    }
    if bxsl_visible:
        q3matrix["BXSL"] = third
    if set(q3matrix) - {"ARCC", "OBDC", "BXSL"}:
        raise ComparisonError("unknown original SEC issuer")
    matrix = [{
        "issuer": issuer,
        "nonaccrual_cost_pct": (
            x["nonaccrual_cost_pct"] if issuer == "BXSL" else x["cost_pct"]
        ),
        "nonaccrual_fair_pct": (
            x["nonaccrual_fair_pct"] if issuer == "BXSL" else x["fair_pct"]
        ),
        "SEC_available_at": x["available_at"],
        "reporting_period_end": "2026-09-30",
        "issuer_nonaccrual_rates_not_pooled": True,
    } for issuer, x in sorted(q3matrix.items())]
    counts = dict(original_two["asof_visible_by_issuer"])
    counts["BXSL"] = 2 if bxsl_visible else 0
    return {
        "schema_version": "aics-private-credit-three-bdc-original-sec-asof-research-v1",
        "as_of": asof.isoformat(),
        "proven_original_sec_issuers": ["ARCC", "BXSL", "OBDC"],
        "source_filing_periods_across_issuers": 9,
        "genuine_source_nonaccrual_values_across_issuers": 18,
        "source_values_visible_by_asof": sum(counts.values()),
        "source_values_visible_per_issuer": counts,
        "2026Q3_nonaccrual_source_matrix": matrix,
        "original_source_zip_sha256s": {
            **original_two["underlying_original_sources"],
            "BXSL_2026Q3_original_3_html_zip_sha256": bxsl["source_archive_zip_sha256"],
        },
        "SEC_available_at_filed_at_plus_calendar_days": 14,
        "issuer_percentages_aggregated": False,
        "issuer_weights_calibrated_or_posthoc_created": False,
        "source_raw_content_replaced_with_synthetic": False,
        "synthetic_observations_created": 0,
        "independent_contemporaneous_feed_PIT": False,
        "untouched_24_month_predictive_oos": False,
        "private_credit_node_score": None,
        "aics_index": None,
        "promotion": "BLOCKED",
        "important": (
            "3 original SEC issuers are verified research evidence, not a representative "
            "Private Credit stress index. Third issuer BXSL has only Q3 2026."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default="2026-11-19")
    p.add_argument("--arcc", type=Path, default=ARCC_SOURCE)
    p.add_argument("--obdc", type=Path, default=OBDC_SOURCE)
    p.add_argument("--bxsl", type=Path, default=BXSL)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    try:
        d = build(
            json.loads(a.arcc.read_text(encoding="utf-8")),
            json.loads(a.obdc.read_text(encoding="utf-8")),
            json.loads(a.bxsl.read_text(encoding="utf-8")),
            dt.date.fromisoformat(a.as_of),
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "kind": type(exc).__name__}))
        return 2
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "issuers": len(d["proven_original_sec_issuers"]),
        "source_periods": d["source_filing_periods_across_issuers"],
        "values": d["source_values_visible_by_asof"],
        "private_credit_stress": None, "AICS": None,
        "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
