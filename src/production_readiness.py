"""Production-readiness gates for the whole Phoenix system."""

from __future__ import annotations

from collections.abc import Mapping


REQUIRED_BLOCKS = (
    "data",
    "payoff",
    "risk",
    "calibration",
    "oos",
    "committee",
    "storage",
    "operations",
)

READY_STATUSES = {"ready", "completed", "passed"}


def build_production_readiness_report(
    blocks: Mapping[str, Mapping[str, object]],
    *,
    safety: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return an explicit production gate without mutating live state."""
    safety_values = safety or {}
    blockers: list[str] = []
    block_report: dict[str, object] = {}

    for block_name in REQUIRED_BLOCKS:
        block = blocks.get(block_name, {})
        status = str(block.get("status", "missing"))
        block_report[block_name] = {
            "status": status,
            "owner": str(block.get("owner", "unassigned")),
            "metric_gate": str(block.get("metric_gate", "unspecified")),
            "evidence": str(block.get("evidence", "missing")),
        }
        if status not in READY_STATUSES:
            blockers.append(f"{block_name}:{status}")

    for flag in (
        "production_weights_changed",
        "verdict_mutated",
        "trades_created",
    ):
        if safety_values.get(flag) is not False:
            blockers.append(f"safety:{flag}")

    return {
        "schema_version": "production-readiness-v1",
        "status": "ready" if not blockers else "blocked",
        "blocks": block_report,
        "blockers": blockers,
        "human_review_required": True,
        "research_only": bool(blockers),
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
