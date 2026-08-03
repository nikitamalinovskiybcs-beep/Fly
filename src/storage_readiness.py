"""Readiness checks for Phoenix storage backends."""

from __future__ import annotations

from collections.abc import Mapping


def build_storage_readiness(statuses: Mapping[str, object]) -> dict[str, object]:
    """Require local persistence and report optional cloud backend status."""
    local_ready = statuses.get("sqlite") is True or statuses.get("duckdb") is True
    configured_cloud = [
        name
        for name in ("supabase", "firebase", "clickhouse", "r2", "redis")
        if statuses.get(name) is True
    ]
    return {
        "status": "ready" if local_ready else "blocked",
        "local_persistence": local_ready,
        "configured_cloud_backends": configured_cloud,
        "optional_cloud_backends_missing": [
            name
            for name in ("supabase", "firebase", "clickhouse", "r2", "redis")
            if statuses.get(name) is not True
        ],
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
