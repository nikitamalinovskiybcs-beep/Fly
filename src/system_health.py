"""Cross-system health report for research and paper workflows."""

from __future__ import annotations

from collections.abc import Mapping


def build_system_health(
    *,
    data_quality: Mapping,
    structure_audit: Mapping,
    benchmark: Mapping,
    safety: Mapping | None = None,
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
    return {
        "status": "healthy" if all(checks.values()) else "attention_required",
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
