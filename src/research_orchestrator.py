"""Unified research-only orchestration for Phoenix evidence workflows."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from src.data_readiness import build_data_readiness_report


Stage = Callable[[Mapping[str, object]], Mapping[str, object]]


def _stage_status(stage: Mapping[str, object], default: str = "blocked") -> str:
    value = stage.get("status")
    return str(value) if value is not None else default


def run_research_pipeline(
    records: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    calculation: Stage,
    committee: Stage,
    fact_check: Stage,
    oos: Stage,
    safety: Stage,
) -> dict[str, object]:
    """Run the complete research pipeline without mutating production state."""
    context: dict[str, object] = {
        "records": records,
        "research_only": True,
    }
    stages: dict[str, object] = {}

    readiness = build_data_readiness_report(records)
    stages["data_readiness"] = readiness
    context["data_readiness"] = readiness

    calculation_result = dict(calculation(context))
    stages["calculation"] = calculation_result
    context["calculation"] = calculation_result

    committee_result = dict(committee(context))
    stages["committee"] = committee_result
    context["committee"] = committee_result

    fact_check_result = dict(fact_check(context))
    stages["fact_check"] = fact_check_result
    context["fact_check"] = fact_check_result

    oos_result = dict(oos(context))
    stages["oos"] = oos_result
    context["oos"] = oos_result

    safety_result = dict(safety(context))
    stages["safety"] = safety_result
    context["safety"] = safety_result

    blocking_stages = [
        name
        for name, result in stages.items()
        if _stage_status(result) not in {"ready", "completed", "passed"}
    ]
    promotion_status = "blocked" if blocking_stages else "research_candidate"
    return {
        "schema_version": "research-pipeline-v1",
        "status": promotion_status,
        "stage_order": list(stages),
        "stages": stages,
        "blocking_stages": blocking_stages,
        "research_only": True,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
