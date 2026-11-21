"""Independent, incomplete AICS Research alternative to the legacy +14 panel.

Uses ORIGINAL disclosed 2025 cashflow source rows. This makes a dated
eligibility overlay and never rewrites the legacy AICS data or claims OOS/PIT.
Only a candidate after-original-filed-date research chronology is constructed.
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_publication_policy import legacy_eligibility, research_eligibility

ROOT = Path("aics_data/research")
H2025 = ROOT / "hyperscalers_2025_q1_q3_original_sec_cashflow_2026-11-21.json"
HQ4 = ROOT / "hyperscalers_2025_q4_original_sec_cashflow_2026-11-21.json"
BASELINE = ROOT / "aics_24_month_no_multiplier_coverage_2026-11-21.json"
OUTPUT = ROOT / "aics_24m_hyperscalers_research_first_public_overlay_2026-11-21.json"
Q = Decimal("0.01")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def score(ocf, cash_ppe):
    numerator = Decimal(str(ocf))
    denominator = Decimal(str(cash_ppe))
    if denominator <= 0:
        raise ValueError("Cash PP&E denominator must be positive")
    return str(max(Decimal(0), min(Decimal(100),
              (100 * (1 - numerator / denominator)))).quantize(
              Q, rounding=ROUND_HALF_UP))


def _month_end(month):
    y, m = (int(k) for k in month.split("-"))
    return dt.date(y, m, calendar.monthrange(y, m)[1])


def build(old=None, q123=None, q4=None):
    old = old if old is not None else read(BASELINE)
    q123 = q123 if q123 is not None else read(H2025)
    q4 = q4 if q4 is not None else read(HQ4)
    if (old.get("month_count") != 24 or old.get("node_weights_total") != 1050
            or old.get("new_11_node_full_aics_months") != 0
            or old.get("new_11_node_sp500_spread_months") != 0
            or old.get("certified_aics") is not None
            or q123.get("schema") != "aics-hyperscalers-2025-q1-q3-original-sec-quarterly-cash-gap-v1"
            or q4.get("schema") != "aics-hyperscalers-2025q4-original-sec-first-release-cashgap-v1"
            or q4.get("integrity", {}).get("historical_first_delivery_provider_pit_attested") is not False
            or q123.get("flags", {}).get("independently_historically_pit_attested") is not False):
        raise ValueError("Source or certification gate invalid")
    events = []
    for q in q123["quarter_totals"]:
        rows = [r for r in q123["issuer_quarters"] if r["period"] == q["period"]]
        if len(rows) != 4 or {r["issuer"] for r in rows} != {
                "Microsoft", "Amazon", "Alphabet", "Meta"}:
            raise ValueError("Missing four actual 2025 issuer-quarter inputs")
        source_refs = []
        for r in rows:
            for key in r["source_ids"]:
                src = q123["sources"][key]
                source_refs.append(src)
            if (r["operating_cash_usd_m"] <= 0
                    or r["cash_ppe_usd_m"] <= 0):
                raise ValueError("Invalid issuer source numeric")
        if (sum(r["operating_cash_usd_m"] for r in rows) != q["operating_cash_usd_m"]
                or sum(r["cash_ppe_usd_m"] for r in rows) != q["cash_ppe_usd_m"]
                or q["gap_usd_m"] != q["operating_cash_usd_m"]-q["cash_ppe_usd_m"]):
            raise ValueError("Q1-Q3 source arithmetic mismatch")
        source_rows = [{"filed_at": x["filed_at"],
                        "source_url": x["source_url"]} for x in source_refs]
        events.append(_event(q["period"], q["operating_cash_usd_m"],
                             q["cash_ppe_usd_m"], source_rows))
    q4rows = q4["issuer_rows"]
    if len(q4rows) != 4 or {r["issuer"] for r in q4rows} != {
            "Microsoft", "Amazon", "Alphabet", "Meta"}:
        raise ValueError("Missing Q4 issuer originals")
    if (sum(r["cfo"] for r in q4rows) != q4["totals"]["cfo_usd_m"]
            or sum(r["ppe"] for r in q4rows) != q4["totals"]["cash_ppe_usd_m"]):
        raise ValueError("Q4 source arithmetic mismatch")
    events.append(_event("2025-Q4", q4["totals"]["cfo_usd_m"],
                         q4["totals"]["cash_ppe_usd_m"],
                         [{"filed_at":r["filed_at"], "source_url":r["original_sec_url"]}
                          for r in q4rows]))
    events.sort(key=lambda e:e["research_first_eligible_date_proxy"])
    if [e["quarter"] for e in events] != [
            "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]:
        raise ValueError("Unexpected historical event ordering")
    overlay = []
    added_weight_months = 0
    for m in old["monthly"]:
        if (m.get("full_11_node_aics_no_multiplier") is not None
                or m.get("aics_sp500_normalized_spread") is not None
                or m.get("independent_historical_pit_confirmed") is not False):
            raise ValueError("Baseline attempted historical AICS certification")
        end = _month_end(m["month"])
        available = [e for e in events
                     if dt.date.fromisoformat(e["research_first_eligible_date_proxy"]) <= end]
        active = available[-1] if available else None
        preexisting = "Hyperscalers" in m["latest_eligible_research_scores"]
        added = active is not None and not preexisting
        if added:
            added_weight_months += 100
        overlay.append({
            "month": m["month"],
            "hyperscalers_existing_score_if_any": m["latest_eligible_research_scores"].get("Hyperscalers"),
            "new_research_2025_source_period": active["quarter"] if active else None,
            "new_research_2025_source_available_at_proxy":
                active["research_first_eligible_date_proxy"] if active else None,
            "new_research_2025_candidate_score": active["candidate_gap_score"] if active else None,
            "additional_source_research_node": added,
            "baseline_known_weight": sum({"Private Credit":150,"Insurers":125,"UST 30Y":125,
                                           "Neoclouds":100,"AI Equities":100,"Hyperscalers":100,
                                           "SPV":100,"Repo":100,"Power/Data Centers":50,
                                           "Semiconductors Supply":50,"AI Demand":50}[k]
                                         for k in m["latest_eligible_research_scores"]),
            "additional_source_weight": 100 if added else 0,
            "full_historical_aics": None,
            "aics_sp500_spread": None,
            "independent_pit_certified": False,
        })
    total_weight_months = 24 * 1050
    baseline_weight_months = sum(r["baseline_known_weight"] for r in overlay)
    new_weight_months = baseline_weight_months + added_weight_months
    return {
        "schema": "aics-24m-research-publication-proxy-overlay-v1",
        "asof_research": "2026-11-21",
        "source_policy": "original SEC date-only => next calendar day; not documented exact dissemination timestamp",
        "legacy_original_files_unchanged": True,
        "model_multiplier_applied": False,
        "research_events": events,
        "monthly": overlay,
        "months": len(overlay),
        "new_coverage_source_weight_months": added_weight_months,
        "baseline_research_weight_months": baseline_weight_months,
        "alternative_research_weight_months": new_weight_months,
        "baseline_coverage_pct": str((100*Decimal(baseline_weight_months) /
                                      Decimal(total_weight_months)).quantize(Q)),
        "alternative_coverage_pct": str((100*Decimal(new_weight_months) /
                                         Decimal(total_weight_months)).quantize(Q)),
        "source_timestamp_pit_attested": False,
        "uncertified_stress_model": True,
        "historical_full_aics_months": 0,
        "aics_sp500_spread_months": 0,
        "trades_created": False,
    }


def _event(quarter, ocf, cash_ppe, source_rows):
    if not source_rows:
        raise ValueError("At least one original source is required")
    research, legacy = [], []
    for r in source_rows:
        research.append(research_eligibility(
            source_url=r["source_url"], filed_at=r["filed_at"],
            public_date=r["filed_at"]).eligible_date)
        legacy.append(legacy_eligibility(
            source_url=r["source_url"], filed_at=r["filed_at"]).eligible_date)
    return {
        "quarter": quarter,
        "operating_cash_usd_m": ocf,
        "cash_ppe_usd_m": cash_ppe,
        "cash_gap_usd_m": ocf-cash_ppe,
        "candidate_gap_score": score(ocf,cash_ppe),
        "research_first_eligible_date_proxy": max(research),
        "legacy_first_eligible_plus14": max(legacy),
        "original_source_count": len(source_rows),
        "original_public_time_verified": False,
        "independently_historical_pit_attested": False,
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
