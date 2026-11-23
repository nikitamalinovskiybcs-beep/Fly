"""Field-level provenance validation for research evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


REQUIRED_FIELDS = (
    "source",
    "source_id",
    "observed_at",
    "dataset_version",
    "evidence_class",
)
VERIFIED_CLASSES = {"verified", "realized", "dealer_verified"}


def validate_field_provenance(
    fields: Mapping[str, Mapping[str, object]],
    *,
    required_fields: Sequence[str] = REQUIRED_FIELDS,
) -> dict[str, object]:
    """Return deterministic blockers without promoting evidence."""
    missing: dict[str, list[str]] = {}
    invalid: dict[str, list[str]] = {}
    for name, metadata in fields.items():
        missing_keys = [
            key for key in required_fields
            if not str(metadata.get(key, "")).strip()
        ]
        invalid_keys = []
        if metadata.get("evidence_class") not in VERIFIED_CLASSES:
            invalid_keys.append("evidence_class")
        if metadata.get("freshness_seconds") is not None:
            freshness = metadata["freshness_seconds"]
            if not isinstance(freshness, (int, float)) or freshness < 0:
                invalid_keys.append("freshness_seconds")
        if missing_keys:
            missing[name] = missing_keys
        if invalid_keys:
            invalid[name] = invalid_keys
    complete = not missing and not invalid and bool(fields)
    return {
        "status": "verified" if complete else "blocked",
        "field_count": len(fields),
        "missing": missing,
        "invalid": invalid,
        "all_verified": complete,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
