#!/usr/bin/env python3
"""SEC +14d ARCC as-of research panel from corrected original Q4/Q1/Q2/Q3 exhibits.

Corrections: original ARCC 2026-02-04 8-K EX-99.1 proves Dec 2025
source was AICS-eligible 2026-02-18. The Dec 2024 comparison in the
same exhibit first appears in 2026 and is NEVER backdated to 2024.
Verified original source figures != historical live archive, node score,
independent 24-month OOS, or representative Private Credit breadth.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

OUT = Path("docs/audit/aics_arcc_verified_asof_panel_2026-11-19.json")
DURABLE = Path("aics_data/research/arcc_q4_sec_corrected_nonaccrual_sources_2026-11-18.json")
SCHEMA = "aics-arcc-q4-exhibit-corrected-sec-asof-source-research-v1"
SOURCE_PERIODS = {
    "2024-12-31": ("2026-02-04", "2026-02-18", "RETROSPECTIVE_PRIOR_YEAR_COMPARATIVE_IN_2025Q4_8K"),
    "2025-12-31": ("2026-02-04", "2026-02-18", "CURRENT_QUARTER_AUTHENTIC_2025Q4_8K"),
    "2026-03-31": ("2026-04-28", "2026-05-12", "CURRENT_QUARTER_AUTHENTIC_SEC_EXHIBIT"),
    "2026-06-30": ("2026-07-29", "2026-08-12", "CURRENT_QUARTER_AUTHENTIC_SEC_EXHIBIT"),
    "2026-09-30": ("2026-10-27", "2026-11-10", "CURRENT_QUARTER_AUTHENTIC_SEC_EXHIBIT"),
}


class PanelError(ValueError):
    pass


def _number(value: object) -> Decimal:
    if not isinstance(value, str):
        raise PanelError("source percentage not official original numeric text")
    try:
        x = Decimal(value)
    except InvalidOperation:
        raise PanelError("invalid original source decimal") from None
    if not x.is_finite() or not 0 <= x <= 100:
        raise PanelError("nonfinite or impossible original source percent")
    return x


def _date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        raise PanelError("invalid original source date") from None


def _hash64(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch("[a-f0-9]{64}", value) is not None


def build(verified: dict, cutoff: dt.date, durable: dict) -> dict:
    if (
        verified.get("schema_version") != SCHEMA
        or verified.get("raw_original_html_documents_rehashed") != 6
        or verified.get("distinct_observation_periods") != 5
        or verified.get("source_verified_nonaccrual_values") != 10
        or verified.get("retrospective_2024_value_visible_in_2024") is not False
        or verified.get("SEC_14_calendar_day_rule_enforced") is not True
        or verified.get("synthetic_rows_created") != 0
        or verified.get("historical_24m_pit_attested") is not False
        or verified.get("independent_24m_oos") is not False
        or verified.get("one_issuer_not_entire_private_credit_node") is not True
        or verified.get("private_credit_node_score") is not None
        or verified.get("index_aics") is not None
        or verified.get("promotion") != "BLOCKED"
        or durable.get("schema_version") != "aics-arcc-q4-sec-corrected-durable-source-panel-v1"
        or durable.get("confirmed_source_values") != 10
        or durable.get("synthetic_market_rows") != 0
        or durable.get("promotion") != "BLOCKED"
        or durable.get("index_aics") is not None
        or durable.get("new_verified_2025q4_model_available_at") != "2026-02-18"
        or durable.get("complete_24_month_market_pit") is not False
        or durable.get("independent_24_month_predictive_oos") is not False
    ):
        raise PanelError("untrusted original SEC timeline or scoring claims")
    if durable.get("reverified_timeline_report_sha256") != "38e6c0bb5ba64ed2edb1a76728cca3e74c455dfc1104e5b66cce2f9def79a5d1":
        raise PanelError("corrected timeline source receipt changed")
    vpro = verified.get("source_artifact_provenance")
    if not isinstance(vpro, dict) or vpro.get("q4_zip_id") != 14476018751 or vpro.get("q1q3_zip_id") != 14474764347:
        raise PanelError("SEC original artifact identity drift")
    for tag, sha in (("q4", "q4_zip_sha256"), ("q1q3", "q1q3_zip_sha256")):
        if not _hash64(vpro.get(sha)) or durable.get("source_archives", {}).get(tag, {}).get("archive_sha256") != vpro[sha]:
            raise PanelError("source archive SHA mismatch")
    a = verified.get("source_verified_disclosed_periods")
    b = durable.get("observed_source_periods")
    if not isinstance(a, list) or not isinstance(b, list) or len(a) != 5 or len(b) != 5:
        raise PanelError("requires all 5 source-observed periods")
    source_rows = {}
    durable_rows = {}
    for item in a:
        day = item.get("period_end")
        if day not in SOURCE_PERIODS or day in source_rows:
            raise PanelError("unknown or duplicate original period")
        source_rows[day] = item
    for item in b:
        day = item.get("period_end")
        if day not in SOURCE_PERIODS or day in durable_rows:
            raise PanelError("unknown or duplicate durable period")
        durable_rows[day] = item
    if set(source_rows) != set(SOURCE_PERIODS) or set(durable_rows) != set(SOURCE_PERIODS):
        raise PanelError("missing original period")
    observations = []
    for period in SOURCE_PERIODS:
        d = source_rows[period]
        r = durable_rows[period]
        filed_expected, available_expected, evidence = SOURCE_PERIODS[period]
        filed = _date(d.get("source_filed_at"))
        available = _date(d.get("aics_eligible_date_after_sec_14d"))
        if (filed.isoformat() != filed_expected
                or available.isoformat() != available_expected
                or available != filed + dt.timedelta(days=14)
                or _date(period) > filed
                or r.get("source_filed_at") != filed_expected
                or r.get("available_at") != available_expected
                or d.get("evidence_kind") != evidence or r.get("evidence_kind") != evidence
                or d.get("independent_original_sec_value_verified") is not True
                or d.get("independent_historical_publication_time_attested") is not False
                or d.get("model_eligible") is not False
                or r.get("model_eligible") is not False
                or not _hash64(d.get("source_html_sha256"))
                or r.get("source_sha256") != d.get("source_html_sha256")
                or r.get("source_url") != d.get("source_url")
                or not d.get("source_url", "").startswith("https://www.sec.gov/Archives/edgar/data/1287750/")):
            raise PanelError("SEC +14 source, evidence identity or historical look-ahead")
        cost = _number(d["nonaccrual_amortized_cost_pct"])
        fair = _number(d["nonaccrual_fair_value_pct"])
        if cost != _number(r["cost_pct"]) or fair != _number(r["fair_value_pct"]):
            raise PanelError("original SEC numeric source receipts disagree")
        if available > cutoff:
            continue
        observations.append({
            "period_end": period, "SEC_filed_at": filed_expected,
            "available_at": available_expected,
            "cost_nonaccrual_pct": str(cost), "fair_value_nonaccrual_pct": str(fair),
            "source_html_sha256": d["source_html_sha256"],
            "availability_basis": evidence,
            "source_is_verified_original": True,
            "independent_live_time_release_archive_attested": False,
            "score_eligible": False,
        })
    last = observations[-1] if observations else None
    return {
        "schema_version": "aics-arcc-verified-sec-available-at-research-panel-v2",
        "research_cutoff": cutoff.isoformat(),
        "original_q4_sec_archive_sha256": vpro["q4_zip_sha256"],
        "original_q1q3_sec_archive_sha256": vpro["q1q3_zip_sha256"],
        "corrected_source_timeline_sha256": durable["reverified_timeline_report_sha256"],
        "verified_observations_available_by_cutoff": len(observations),
        "verified_values_available_by_cutoff": len(observations) * 2,
        "source_observations": observations,
        "latest_known_original_sec_period": last["period_end"] if last else None,
        "latest_known_nonaccrual_cost_pct": last["cost_nonaccrual_pct"] if last else None,
        "latest_known_nonaccrual_fair_value_pct": last["fair_value_nonaccrual_pct"] if last else None,
        "retrospective_2024_values_visible_in_2024": False,
        "SEC_embargo_calendar_days": 14,
        "synthetic_financial_observations": 0,
        "full_historical_pit_attested": False,
        "independent_24m_oos": False,
        "private_credit_node_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--verified", type=Path, required=True)
    p.add_argument("--durable", type=Path, default=DURABLE)
    p.add_argument("--as-of", default="2026-11-18")
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    try:
        result = build(json.loads(args.verified.read_text(encoding="utf-8")),
                       _date(args.as_of),
                       json.loads(args.durable.read_text(encoding="utf-8")))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("ARCC corrected SEC source panel BLOCKED:", type(exc).__name__)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "periods_available": result["verified_observations_available_by_cutoff"],
        "values_available": result["verified_values_available_by_cutoff"],
        "first_period": result["source_observations"][0]["period_end"] if result["source_observations"] else None,
        "latest": result["latest_known_original_sec_period"],
        "index_aics": None, "promotion": "BLOCKED"
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
