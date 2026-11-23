"""Evidence-gated improvement cycle planning.

The planner can run repeatedly, but it never edits production weights or
creates trades. It stops when targets are met or progress plateaus.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def build_cycle_plan(
    targets: Iterable[Mapping],
    history: Iterable[Mapping] = (),
    plateau_limit: int = 3,
) -> dict:
    target_list = list(targets)
    history_list = list(history)
    if not target_list:
        return {
            "status": "target_met",
            "action": "stop",
            "reason": "all evidence targets are satisfied",
            "production_weights_changed": False,
        }

    target = target_list[0]
    target_id = str(target.get("id", "unknown"))
    failures = sum(
        1
        for item in history_list
        if item.get("target_id") == target_id
        and item.get("result") == "no_improvement"
    )
    if failures >= plateau_limit:
        return {
            "status": "plateau",
            "action": "stop_and_review",
            "target_id": target_id,
            "reason": f"{plateau_limit} consecutive cycles without improvement",
            "production_weights_changed": False,
        }

    return {
        "status": "proposal",
        "action": "create_pr_for_review",
        "target_id": target_id,
        "priority": target.get("priority"),
        "requested_change": target.get("action"),
        "iteration": len(history_list) + 1,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "evidence_gate": "same frozen replay plus chronological OOS must improve",
    }
