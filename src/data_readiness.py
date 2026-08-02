"""Evidence-source readiness and research-priority reporting."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


SOURCE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "settled_24m_notes": (
        "note_id",
        "basket",
        "as_of",
        "maturity_date",
        "outcome_type",
        "observations",
    ),
    "observation_paths": ("ticker", "observation_timestamp", "level", "source"),
    "bcs_capital_quotes": (
        "quote_id",
        "quote_timestamp",
        "basket",
        "barrier",
        "coupon_pa",
    ),
    "iv_surfaces": ("ticker", "as_of", "strike", "tenor", "iv"),
    "alternative_features": (
        "feature_id",
        "ticker",
        "feature_timestamp",
        "source",
        "license_status",
    ),
}


def build_data_readiness_report(
    records: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    """Report completeness without treating missing data as neutral evidence."""
    sources: dict[str, object] = {}
    blockers: list[str] = []
    for source, required in SOURCE_REQUIREMENTS.items():
        rows = list(records.get(source, []))
        missing_rows = sum(
            1
            for row in rows
            if any(row.get(field) in (None, "", []) for field in required)
        )
        valid_rows = len(rows) - missing_rows
        status = "ready" if valid_rows and missing_rows == 0 else "blocked"
        sources[source] = {
            "status": status,
            "rows": len(rows),
            "valid_rows": valid_rows,
            "invalid_rows": missing_rows,
            "required_fields": list(required),
        }
        if status == "blocked":
            blockers.append(source)
    return {
        "schema_version": "data-readiness-v1",
        "status": "ready" if not blockers else "blocked",
        "sources": sources,
        "blockers": blockers,
        "next_action": (
            "collect_missing_evidence"
            if blockers
            else "run_leakage_safe_oos_validation"
        ),
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
