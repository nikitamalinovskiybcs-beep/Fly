"""Deterministic specialist checks for the research-only AI committee."""

from __future__ import annotations

from collections.abc import Mapping


SPECIALIST_ROLES = (
    "quant_payoff",
    "calibration_oos",
    "data_provenance",
    "security_compliance",
    "code_operations",
)


def run_specialist(
    role: str,
    evidence: Mapping[str, object],
) -> dict[str, object]:
    if role not in SPECIALIST_ROLES:
        raise ValueError(f"unknown specialist role: {role}")

    required = {
        "quant_payoff": (
            "payoff_state_machine",
            "p_ki",
            "p_autocall",
            "monte_carlo_convergence",
        ),
        "calibration_oos": (
            "term_months",
            "anchors",
            "baseline_metric",
            "model_metric",
            "brier",
            "log_loss",
            "ece",
        ),
    }.get(role, ())
    blockers = [
        f"missing:{field}"
        for field in required
        if field not in evidence
    ]
    if role == "calibration_oos":
        if evidence.get("term_months") != 24:
            blockers.append("fixed-24m-required")
        if tuple(evidence.get("anchors", ())) != (6, 12, 18, 24):
            blockers.append("anchors-required:6,12,18,24")
        if (
            "baseline_metric" in evidence
            and "model_metric" in evidence
            and float(evidence["model_metric"]) <= float(evidence["baseline_metric"])
        ):
            blockers.append("baseline-not-beaten")

    return {
        "role": role,
        "status": "blocked" if blockers else "ready_for_research",
        "blockers": blockers,
        "evidence_fields": sorted(str(key) for key in evidence),
        "research_only": True,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }


def specialist_registry() -> list[dict[str, object]]:
    return [
        {
            "role": role,
            "enabled": role in {"quant_payoff", "calibration_oos"},
            "promotion_allowed": False,
            "human_review_required": True,
        }
        for role in SPECIALIST_ROLES
    ]
