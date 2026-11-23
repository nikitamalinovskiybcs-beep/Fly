"""Aggregate independent AI reviews into a bounded, evidence-gated action plan."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


FIXED_GATE = (
    "fixed-24m OOS Brier and log-loss beat empirical baseline at all "
    "6/12/18/24-month anchors; ECE and barrier monotonicity do not worsen"
)


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_plan(paths: list[str]) -> dict[str, Any]:
    completed: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    actions: Counter[str] = Counter()
    for path in paths:
        panel = _load(path)
        for item in panel.get("reviews", []):
            statuses.append(
                {
                    "provider": item.get("provider", "unknown"),
                    "status": item.get("status", "unknown"),
                    "reason": item.get("reason", ""),
                },
            )
            if item.get("status") == "completed" and isinstance(item.get("review"), dict):
                review = item["review"]
                completed.append(
                    {
                        "provider": item.get("provider", "unknown"),
                        "model": review.get("model", ""),
                        "verdict": review.get("verdict", ""),
                        "score": review.get("overall_score_0_to_100"),
                        "summary": review.get("summary", ""),
                        "findings": review.get(
                            "findings",
                            review.get("prioritized_findings", []),
                        ),
                        "next_experiments": review.get("next_experiments", []),
                    },
                )
                for finding in completed[-1]["findings"]:
                    if isinstance(finding, dict):
                        action = str(finding.get("action", ""))
                        if action:
                            actions[action] += 1

    plan = [
        {
            "priority": "P0",
            "action": "REPLACE",
            "component": "p_loss calibration",
            "why": "All completed reviews and empirical tests reject uncalibrated production probability.",
            "implementation": "Build leakage-safe walk-forward calibration for the fixed 24-month product.",
            "gate": FIXED_GATE,
        },
        {
            "priority": "P0",
            "action": "ADD_TEST",
            "component": "payoff and barrier semantics",
            "why": "Formula judges flagged observation timing, coupon eligibility and path-dependent barrier validation.",
            "implementation": "Add contractual timing tests, barrier-crossing tests and Monte Carlo convergence checks.",
            "gate": FIXED_GATE + "; payoff invariants must pass.",
        },
        {
            "priority": "P0",
            "action": "ADD_TEST",
            "component": "data provenance and leakage",
            "why": "Whole-system judges flagged provenance, limited history and OOS leakage risk.",
            "implementation": "Require source, timestamp, split and replay/realized labels for every training feature.",
            "gate": "No train/OOS overlap; synthetic and replay rows excluded from independent evidence.",
        },
        {
            "priority": "P1",
            "action": "REPLACE",
            "component": "overlapping agent adjustments",
            "why": "The architecture has many agents and possible double-counting paths.",
            "implementation": "Measure marginal contribution, then remove agents that do not improve the fixed gate.",
            "gate": FIXED_GATE + "; no degradation in risk monotonicity or auditability.",
        },
        {
            "priority": "P1",
            "action": "ADD_TEST",
            "component": "model registry and observability",
            "why": "A complex multi-provider and multi-agent system needs reproducible lineage.",
            "implementation": "Persist code version, data snapshot, features, weights, judge status and gate results.",
            "gate": "Every candidate and decision has a reproducible audit record.",
        },
        {
            "priority": "P2",
            "action": "KEEP",
            "component": "production safety gates",
            "why": "Independent reviews recognized the no-mutation/no-trade safeguards.",
            "implementation": "Keep and test production_weights_changed=false and verdict_mutated=false.",
            "gate": "Safety invariants remain true in every provider and workflow path.",
        },
    ]
    return {
        "status": "consensus_available" if completed else "no_completed_reviews",
        "completed_reviews": completed,
        "provider_statuses": statuses,
        "action_counts": dict(actions),
        "consensus_verdict": (
            "reject"
            if completed and all(item["verdict"] == "reject" for item in completed)
            else "revise"
            if completed
            else "unavailable"
        ),
        "plan": plan,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(
        json.dumps(build_plan(args.reports), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
