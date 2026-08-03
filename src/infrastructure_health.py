"""Unified, machine-readable infrastructure health status."""

from __future__ import annotations

from typing import Mapping


def build_infrastructure_health(
    *,
    data: Mapping[str, object],
    cache: Mapping[str, object],
    storage: Mapping[str, object],
    runtime: Mapping[str, object],
    model: Mapping[str, object],
) -> dict[str, object]:
    """Combine subsystem checks without performing network calls."""
    checks = {
        "data": data.get("passed") is True,
        "cache": cache.get("healthy") is True,
        "storage": storage.get("healthy") is True,
        "runtime": runtime.get("healthy") is True,
        "production_safety": model.get("production_safety") is True,
        "promotion_gate": model.get("promotion_gate") is True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "schema_version": "infrastructure-health-v1",
        "status": "healthy" if not failed else "attention_required",
        "checks": checks,
        "failed_checks": failed,
        "source": "infrastructure_health",
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
