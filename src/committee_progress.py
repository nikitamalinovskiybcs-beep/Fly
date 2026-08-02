"""Evidence-based 0-100 progress score for the AI improvement committee."""

from __future__ import annotations

from collections.abc import Mapping


DIMENSION_WEIGHTS = {
    "formula": 20,
    "risk": 15,
    "data": 15,
    "payoff": 15,
    "agents": 10,
    "reliability": 10,
    "tests_ci": 10,
    "safety": 5,
}


def _score(checks: Mapping[str, bool], names: tuple[str, ...]) -> float:
    if not names:
        return 0.0
    return sum(bool(checks.get(name)) for name in names) / len(names)


def build_progress_score(
    *,
    benchmark: Mapping,
    health: Mapping,
    structure: Mapping,
    evidence: Mapping | None = None,
) -> dict[str, object]:
    """Score implementation progress, not investment quality or return."""
    evidence = evidence or {}
    candidate_gates = benchmark.get("candidate_gates", {})
    dimension_checks = {
        "formula": {
            "candidate_gate": any(bool(value) for value in candidate_gates.values()),
            "fixed_24m_contract": benchmark.get("product_term_months") == 24,
        },
        "risk": {
            "health": health.get("checks", {}).get("benchmark_gate") is False
            or health.get("status") in {"healthy", "attention_required"},
            "stress_artifact": bool(evidence.get("stress_artifact")),
        },
        "data": {
            "health": bool(health.get("checks", {}).get("data_quality")),
            "provenance": bool(evidence.get("provenance_gate")),
        },
        "payoff": {
            "contract_tests": bool(evidence.get("payoff_tests")),
            "monotonic_observations": bool(evidence.get("observation_validation")),
        },
        "agents": {
            "ablation": bool(evidence.get("agent_ablation")),
        },
        "reliability": {
            "structure_passed": bool(structure.get("passed")),
            "no_syntax_errors": not bool(structure.get("syntax_errors")),
        },
        "tests_ci": {
            "focused_tests": bool(evidence.get("focused_tests")),
            "ci_passed": bool(evidence.get("ci_passed")),
        },
        "safety": {
            "weights_unchanged": health.get("production_weights_changed") is False,
            "verdict_unchanged": health.get("verdict_mutated") is False,
        },
    }
    scores = {
        name: round(
            _score(checks, tuple(checks.keys())) * DIMENSION_WEIGHTS[name],
            2,
        )
        for name, checks in dimension_checks.items()
    }
    total = round(sum(scores.values()), 2)
    return {
        "score_0_to_100": total,
        "dimension_weights": DIMENSION_WEIGHTS,
        "dimension_scores": scores,
        "dimension_checks": dimension_checks,
        "interpretation": (
            "implementation_progress_only; not a market-performance score"
        ),
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
