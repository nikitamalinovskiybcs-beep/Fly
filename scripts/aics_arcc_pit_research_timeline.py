#!/usr/bin/env python3
"""Conservative ARCC non-accrual availability timeline from reverified SEC bytes.

No fabricated observations, backdating of an unavailable issuer news shell,
source-to-score calibration, or certified AICS. This timeline derives solely
from the independent SEC original-value verification already in the repo.
As-of date eligibility != contemporaneous historical publication attestation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

FROM_VERIFIED = Path("docs/audit/aics_arcc_primary_sec_nonaccrual_verified_2026-11-18.json")
OUT = Path("docs/audit/aics_arcc_conservative_pit_timeline_2026-11-18.json")
PERIODS = ("2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30")
EVAL_DATES = (
    "2026-02-18", "2026-05-11", "2026-05-12", "2026-08-11",
    "2026-08-12", "2026-11-09", "2026-11-10", "2026-11-18",
)
METRICS = (
    ("nonaccrual_amortized_cost_pct", "nonaccrual_amortized_cost_percent"),
    ("nonaccrual_fair_value_pct", "nonaccrual_fair_value_percent"),
)
EXPECTED_DOCUMENTS = {
    "2026-03-31": ("2026-04-28", "2026-05-12"),
    "2026-06-30": ("2026-07-29", "2026-08-12"),
    "2026-09-30": ("2026-10-27", "2026-11-10"),
}
RAW_SHA = re.compile(r"^[0-9a-f]{64}$")


class EvidenceGateError(ValueError):
    pass


def _date(s: str) -> dt.date:
    if not isinstance(s, str):
        raise EvidenceGateError("missing exact ISO date")
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise EvidenceGateError("invalid exact ISO date") from None


def _pct(s: str) -> Decimal:
    if not isinstance(s, str):
        raise EvidenceGateError("source percentage must be a decimal string")
    try:
        n = Decimal(s)
    except InvalidOperation:
        raise EvidenceGateError("invalid source percentage") from None
    if not n.is_finite() or not Decimal("0") <= n <= Decimal("100"):
        raise EvidenceGateError("percentage outside domain")
    return n


def build(verified: dict) -> dict:
    if (
        verified.get("schema_version")
            != "aics-arcc-sec-primary-nonaccrual-independent-raw-verification-v1"
        or verified.get("research_as_of") != "2026-11-18"
        or verified.get("independently_verified_source_transcription_values") != 8
        or verified.get("verified_sec_exhibit_originals") != 3
        or verified.get("original_source_html_rehashed") != 4
        or verified.get("dec_2025_prior_values_independent_sec_crosschecks") != 3
        or verified.get("earlier_february_issuer_release_PIT_attested") is not False
        or verified.get("historical_24mo_PIT_complete") is not False
        or verified.get("independent_24mo_predictive_OOS") is not False
        or verified.get("index_aics") is not None
        or verified.get("private_credit_node_stress_score") is not None
        or verified.get("promotion") != "BLOCKED"
        or not RAW_SHA.fullmatch(str(verified.get("primary_original_archive_sha256", "")))
    ):
        raise EvidenceGateError("original verification provenance or promotion gate failed")
    original_records = verified.get("source_values")
    if not isinstance(original_records, list) or len(original_records) != 4:
        raise EvidenceGateError("not exactly four original-verification periods")
    indexed = {r["period_end"]: r for r in original_records}
    if set(indexed) != set(PERIODS) or len(indexed) != len(original_records):
        raise EvidenceGateError("duplicate, missing, or extra quarterly disclosures")

    baseline = indexed[PERIODS[0]]
    if not (
        baseline["earliest_verified_sec_filed_at"] == "2026-04-28"
        and baseline["earliest_verified_sec_available_at"] == "2026-05-12"
        and baseline["research_csv_claimed_issuer_available_at"] == "2026-02-18"
        and baseline["earlier_issuer_release_original_bytes_confirmed"] is False
        and baseline["retrospectively_corrobated_by_sec_exhibits_count"] == 3
    ):
        raise EvidenceGateError("previous issuer release was silently backdated")
    q1_sha = indexed["2026-03-31"]["SEC_source_sha256"]
    if not RAW_SHA.fullmatch(q1_sha):
        raise EvidenceGateError("missing first available SEC source hash")

    disclosures = []
    for period in PERIODS:
        data = indexed[period]
        if period == PERIODS[0]:
            filed = baseline["earliest_verified_sec_filed_at"]
            available = baseline["earliest_verified_sec_available_at"]
            source_url = indexed["2026-03-31"]["SEC_exhibit_url"]
            sha = q1_sha
            evidence_kind = "DEC_2025_PRIOR_PERIOD_COMPARATIVE_IN_LATER_SEC_EXHIBIT"
        else:
            filed, available = EXPECTED_DOCUMENTS[period]
            if (
                data.get("SEC_filed_at") != filed
                or data.get("SEC_available_at") != available
                or data.get("original_verified") is not True
                or data.get("released_historical_PIT_certified") is not False
            ):
                raise EvidenceGateError("misdated or promoted SEC document")
            source_url = data["SEC_exhibit_url"]
            sha = data["SEC_source_sha256"]
            evidence_kind = "CURRENT_PERIOD_SEC_EXHIBIT"
        if not (
            isinstance(source_url, str)
            and source_url.startswith("https://www.sec.gov/Archives/edgar/data/1287750/")
            and RAW_SHA.fullmatch(sha)
            and _date(period) <= _date(filed)
            and _date(filed) + dt.timedelta(days=14) == _date(available)
            and _date(available) <= dt.date(2026, 11, 18)
        ):
            raise EvidenceGateError("invalid SEC reference, original hash or 14-day embargo")
        for metric, field in METRICS:
            value = _pct(data[field])
            disclosures.append({
                "entity": "ARCC",
                "node": "Private Credit",
                "metric_id": metric,
                "observation_date": period,
                "verified_sec_original_filed_at": filed,
                "conservative_available_at": available,
                "value_pct": str(value),
                "first_confirmed_source_url": source_url,
                "source_html_sha256": sha,
                "evidence_kind": evidence_kind,
                "original_value_verified_against_sec_html": True,
                "earliest_historical_release_pit_independently_attested": False,
                "score_eligible": False,
            })

    snapshots = []
    for cutoff_s in EVAL_DATES:
        cutoff = _date(cutoff_s)
        eligible = [r for r in disclosures
                    if _date(r["conservative_available_at"]) <= cutoff
                    and _date(r["observation_date"]) <= cutoff]
        latest = {}
        for metric, _ in METRICS:
            mrows = sorted((r for r in eligible if r["metric_id"] == metric),
                           key=lambda r: r["observation_date"])
            latest_record = mrows[-1] if mrows else None
            prev_record = mrows[-2] if len(mrows) > 1 else None
            latest[metric] = {
                "period_end": latest_record["observation_date"] if latest_record else None,
                "value_pct": latest_record["value_pct"] if latest_record else None,
                "change_from_previous_visible_quarter_pp": (
                    str(_pct(latest_record["value_pct"]) - _pct(prev_record["value_pct"]))
                    if latest_record and prev_record else None
                ),
            }
        snapshots.append({
            "historical_eval_date": cutoff_s,
            "eligible_verified_value_count": len(eligible),
            "earliest_provable_value_date": min(
                (r["conservative_available_at"] for r in eligible), default=None
            ),
            "latest_visible_metrics": latest,
            "pit_attribution": "CONSERVATIVE_SEC_14D_CANDIDATE_NOT_INDEPENDENT_HISTORICAL_ATTESTATION",
            "aics_private_credit_score": None,
        })

    if len(disclosures) != 8 or len(snapshots) != 8:
        raise EvidenceGateError("incomplete original evidence or PIT scenario")
    by_metric = {metric: [r for r in disclosures if r["metric_id"] == metric]
                 for metric, _ in METRICS}
    changes = {}
    for metric, records in by_metric.items():
        vals = [_pct(r["value_pct"]) for r in records]
        changes[metric] = {
            "periods": list(PERIODS),
            "observed_quarterly_values_pct": [str(v) for v in vals],
            "sequential_changes_percentage_points": [
                str(vals[i] - vals[i - 1]) for i in range(1, len(vals))
            ],
            "first_to_last_change_percentage_points": str(vals[-1] - vals[0]),
            "latest_verified_value_pct": str(vals[-1]),
        }
    return {
        "schema_version": "aics-arcc-conservative-sec-release-timeline-research-v1",
        "research_as_of": "2026-11-18",
        "primary_original_zip_sha256": verified["primary_original_archive_sha256"],
        "original_artifact_id": verified["primary_archive_artifact_id"],
        "raw_sec_documents_independently_rehashed": 3,
        "original_verified_metric_values": 8,
        "periods": list(PERIODS),
        "disclosures": disclosures,
        "historical_asof_scenarios": snapshots,
        "metrics": changes,
        "baseline_issuer_feb_2026_pit_proven": False,
        "first_conservative_baseline_sec_available_at": "2026-05-12",
        "source_pit_historical_release_independently_attested": False,
        "private_credit_sector_representative": False,
        "untouched_24_month_oos": False,
        "synthetic_market_rows": 0,
        "private_credit_node_stress_score": None,
        "aics_index": None,
        "promotion": "BLOCKED",
        "notes": [
            "All eight economic values match original SEC HTML; Dec 2025 values are retrospective comparative figures.",
            "The 2026-02-18 user-entered issuer-publication claim is NOT proven by fetched original HTML.",
            "SEC filing dates +14 days are the mandatory model availability gate, not independent historical publication attestation.",
            "This is 1 BDC covering 4 periods, not a representative 24-month Private Credit market stress signal.",
            "No look-ahead, synthetic fills, trading instruction, node score or certified AICS is produced.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verified", type=Path, default=FROM_VERIFIED)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    try:
        data = build(json.loads(args.verified.read_text(encoding="utf-8")))
    except (EvidenceGateError, KeyError, ValueError, OSError) as exc:
        print("ARCC historical SEC timeline BLOCKED:", type(exc).__name__)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps({
        "original_values": data["original_verified_metric_values"],
        "asof_scenarios": len(data["historical_asof_scenarios"]),
        "conservative_baseline_available": data["first_conservative_baseline_sec_available_at"],
        "latest_cost_pct": data["metrics"]["nonaccrual_amortized_cost_pct"]["latest_verified_value_pct"],
        "latest_fair_pct": data["metrics"]["nonaccrual_fair_value_pct"]["latest_verified_value_pct"],
        "score": None, "aics": None, "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
