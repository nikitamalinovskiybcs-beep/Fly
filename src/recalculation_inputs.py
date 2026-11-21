"""Input profiles for reproducible Phoenix note recalculation."""

from __future__ import annotations

from collections.abc import Mapping


RECALCULATION_FIELDS = (
    "note_id",
    "launch_date",
    "maturity_date",
    "basket",
    "initial_levels",
    "barrier",
    "strike",
    "coupon_pa",
    "observation_dates",
    "observation_paths",
    "autocall_schedule",
    "memory_coupon",
)


def build_recalculation_profile(
    record: Mapping[str, object],
    assumptions: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Classify every recalculation input as real, assumed, or missing."""
    assumptions = assumptions or {}
    sources = record.get("_sources", {})
    sources = sources if isinstance(sources, Mapping) else {}
    fields: dict[str, object] = {}
    missing: list[str] = []
    assumed: list[str] = []
    observed: list[str] = []

    for field in RECALCULATION_FIELDS:
        if record.get(field) not in (None, "", []):
            fields[field] = record[field]
            source = str(sources.get(field, "unverified"))
            if source in {"realized", "verified", "dealer_verified"}:
                observed.append(field)
            else:
                assumed.append(field)
        elif field in assumptions:
            fields[field] = assumptions[field]
            assumed.append(field)
        else:
            missing.append(field)

    if missing:
        status = "blocked"
        mode = "insufficient_inputs"
    elif observed and not assumed:
        status = "ready"
        mode = "evidence_backed"
    else:
        status = "ready"
        mode = "assumption_based"

    return {
        "status": status,
        "mode": mode,
        "fields": fields,
        "observed_fields": observed,
        "assumed_fields": assumed,
        "missing_fields": missing,
        "recalculable": status == "ready",
        "requires_disclosure": bool(assumed),
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
