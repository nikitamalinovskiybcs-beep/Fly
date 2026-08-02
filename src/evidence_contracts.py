"""Strict evidence contracts for Phoenix research data."""

from __future__ import annotations

from typing import Mapping


def _required(record: Mapping[str, object], fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if record.get(field) in (None, "", [])]


def validate_fixed_24m_outcome(record: Mapping[str, object]) -> dict[str, object]:
    """Validate a realized or paper 24-month outcome record."""
    errors = _required(
        record,
        (
            "note_id",
            "basket",
            "as_of",
            "maturity_date",
            "outcome_type",
            "source",
            "observations",
        ),
    )
    if record.get("term_months") != 24:
        errors.append("term_months_must_equal_24")
    if not isinstance(record.get("basket"), list) or len(record.get("basket", [])) < 2:
        errors.append("basket_must_have_at_least_two_symbols")
    if record.get("source") not in {"realized", "paper", "historical_replay"}:
        errors.append("source_must_be_realized_paper_or_historical_replay")
    return {"valid": not errors, "errors": errors, "evidence_type": "fixed_24m_outcome"}


def validate_bcs_quote(record: Mapping[str, object]) -> dict[str, object]:
    """Validate one timestamped BCS Capital dealer quote observation."""
    errors = _required(
        record,
        ("quote_id", "quote_timestamp", "basket", "barrier", "coupon_pa"),
    )
    if record.get("dealer") != "BCS Capital":
        errors.append("dealer_must_be_bcs_capital")
    if record.get("term_months") != 24:
        errors.append("term_months_must_equal_24")
    if not isinstance(record.get("basket"), list) or len(record.get("basket", [])) < 2:
        errors.append("basket_must_have_at_least_two_symbols")
    return {"valid": not errors, "errors": errors, "evidence_type": "bcs_quote"}


def validate_alternative_feature(record: Mapping[str, object]) -> dict[str, object]:
    """Reject alternative features that are post-outcome or unlicensed."""
    errors = _required(record, ("feature_id", "ticker", "feature_timestamp", "source"))
    if record.get("license_status") != "licensed_or_public":
        errors.append("source_must_be_licensed_or_public")
    feature_time = record.get("feature_timestamp")
    outcome_time = record.get("outcome_timestamp")
    if outcome_time and feature_time and str(feature_time) > str(outcome_time):
        errors.append("feature_timestamp_after_outcome")
    return {
        "valid": not errors,
        "errors": errors,
        "evidence_type": "alternative_feature",
    }
