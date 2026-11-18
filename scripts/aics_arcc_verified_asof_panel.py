#!/usr/bin/env python3
"""Build ARCC SEC +14 day as-of research panel from independently verified originals.

Do NOT use issuer 2026-02-18 candidate date for December 2025. Earlier
historical observations may be learned only when an original SEC filing has
actually passed the 14-calendar-day embargo. No invented or forward-filled
months; this is a four-period BDC research panel, NOT 24m OOS or a score.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

OUT = Path("docs/audit/aics_arcc_verified_asof_panel_2026-11-19.json")
VERIFIED_SCHEMA = "aics-arcc-sec-primary-nonaccrual-independent-raw-verification-v1"


class PanelError(ValueError):
    pass


def build(verified: dict, cutoff: dt.date) -> dict:
    if (verified.get("schema_version") != VERIFIED_SCHEMA
            or verified.get("original_source_html_rehashed") != 4
            or verified.get("verified_sec_exhibit_originals") != 3
            or verified.get("independently_verified_source_transcription_values") != 8
            or verified.get("earliest_verified_dec2025_disclosure_PIT_from_original") != "2026-05-12"
            or verified.get("earlier_february_issuer_release_PIT_attested") is not False
            or verified.get("historical_24mo_PIT_complete") is not False
            or verified.get("synthetic_financial_observations") != 0
            or verified.get("private_credit_node_stress_score") is not None
            or verified.get("index_aics") is not None
            or verified.get("promotion") != "BLOCKED"):
        raise PanelError("original SEC verification or PIT research constraints violated")
    src = verified.get("source_values")
    if not isinstance(src, list) or len(src) != 4:
        raise PanelError("four original verified SEC periods required")
    observations = []
    for item in src:
        period = dt.date.fromisoformat(item["period_end"])
        is_baseline = period == dt.date(2025, 12, 31)
        if is_baseline:
            if (item.get("earlier_issuer_release_original_bytes_confirmed") is not False
                    or item.get("earliest_verified_sec_available_at") != "2026-05-12"):
                raise PanelError("unsafe backdated 2025 baseline")
            filed = dt.date.fromisoformat(item["earliest_verified_sec_filed_at"])
            available = dt.date.fromisoformat(item["earliest_verified_sec_available_at"])
        else:
            if item.get("original_verified") is not True or item.get("released_historical_PIT_certified") is not False:
                raise PanelError("non-original or falsely PIT-certified SEC exhibit")
            filed = dt.date.fromisoformat(item["SEC_filed_at"])
            available = dt.date.fromisoformat(item["SEC_available_at"])
        if available != filed + dt.timedelta(days=14) or filed <= period:
            raise PanelError("SEC 14-day embargo or reporting chronology failed")
        if period > cutoff or available > cutoff:
            continue
        cost = Decimal(item["nonaccrual_amortized_cost_percent"])
        fair = Decimal(item["nonaccrual_fair_value_percent"])
        if not all(x.is_finite() and 0 <= x <= 100 for x in (cost, fair)):
            raise PanelError("invalid original SEC non-accrual percent")
        observations.append({
            "period_end": period.isoformat(), "SEC_filed_at": filed.isoformat(),
            "available_at": available.isoformat(),
            "cost_nonaccrual_pct": str(cost), "fair_value_nonaccrual_pct": str(fair),
            "availability_basis": "earliest_verified_later_SEC_restatement" if is_baseline else "original_SEC_exhibit_plus_14d",
            "source_is_verified_original": True,
            "independent_original_release_time_attested": False,
        })
    observations.sort(key=lambda x: x["period_end"])
    if len({x["period_end"] for x in observations}) != len(observations):
        raise PanelError("duplicate original source period")
    for i, x in enumerate(observations):
        if i and x["period_end"] <= observations[i-1]["period_end"]:
            raise PanelError("source periods out of order")
    latest_known = None
    for x in observations:
        if latest_known is None or (x["available_at"], x["period_end"]) > (latest_known["available_at"], latest_known["period_end"]):
            latest_known = x
    return {
        "schema_version": "aics-arcc-verified-sec-available-at-research-panel-v1",
        "research_cutoff": cutoff.isoformat(),
        "original_sec_source_archive_sha256": verified["primary_original_archive_sha256"],
        "source_verification_workflow_artifact": 14476205791,
        "verified_observations_available_by_cutoff": len(observations),
        "source_observations": observations,
        "latest_known_original_sec_period": latest_known["period_end"] if latest_known else None,
        "latest_known_nonaccrual_cost_pct": latest_known["cost_nonaccrual_pct"] if latest_known else None,
        "latest_known_nonaccrual_fair_value_pct": latest_known["fair_value_nonaccrual_pct"] if latest_known else None,
        "february_2026_unverified_claim_used": False,
        "SEC_embargo_calendar_days": 14,
        "synthetic_financial_observations": 0,
        "full_historical_pit_attested": False,
        "independent_24m_oos": False,
        "private_credit_node_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verified", type=Path, required=True)
    parser.add_argument("--as-of", default="2026-11-18")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    try:
        result = build(json.loads(args.verified.read_text(encoding="utf-8")),
                       dt.date.fromisoformat(args.as_of))
    except (PanelError, ValueError, KeyError, OSError) as exc:
        print("ARCC as-of research BLOCKED:", type(exc).__name__)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"eligible_periods": result["verified_observations_available_by_cutoff"],
                      "last_period": result["latest_known_original_sec_period"],
                      "score": None, "promotion": "BLOCKED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
