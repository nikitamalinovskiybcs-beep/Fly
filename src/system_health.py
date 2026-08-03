"""Cross-system health report for research and paper workflows."""

from __future__ import annotations

from collections.abc import Mapping

from src.infrastructure_health import build_infrastructure_health


def build_system_health(
    *,
    data_quality: Mapping,
    structure_audit: Mapping,
    benchmark: Mapping,
    safety: Mapping | None = None,
    production_readiness: Mapping | None = None,
) -> dict[str, object]:
    """Aggregate independent health checks without changing any decision."""
    safety = safety or {}
    checks = {
        "data_quality": bool(data_quality.get("passed")),
        "structure": bool(structure_audit.get("passed")),
        "benchmark_gate": bool(benchmark.get("promotion_gate", {}).get("eligible")),
        "production_safety": all(
            safety.get(flag) is False
            for flag in (
                "production_weights_changed",
                "verdict_mutated",
                "trades_created",
            )
            if flag in safety
        ),
    }
    if production_readiness is not None:
        checks["production_readiness"] = production_readiness.get("status") == "ready"
    infrastructure = build_infrastructure_health(
        data={"passed": checks["data_quality"]},
        cache={"healthy": True},
        storage={"healthy": True},
        runtime={"healthy": checks["structure"]},
        model={
            "production_safety": checks["production_safety"],
            "promotion_gate": checks["benchmark_gate"],
        },
    )
    return {
        "schema_version": "system-health-v2",
        "status": "healthy" if all(checks.values()) else "attention_required",
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "infrastructure": infrastructure,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
