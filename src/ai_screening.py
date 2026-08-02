"""Convert AI judge suggestions into bounded, research-only KPI targets."""

from __future__ import annotations

from collections.abc import Mapping


def build_screening_target_plan(panel: Mapping[str, object]) -> dict[str, object]:
    targets: list[dict[str, object]] = []
    for item in panel.get("reviews", []):
        if not isinstance(item, Mapping) or item.get("status") != "completed":
            continue
        review = item.get("review")
        if not isinstance(review, Mapping):
            continue
        experiments = review.get("next_experiments", [])
        if not isinstance(experiments, list):
            continue
        for experiment in experiments[:3]:
            if isinstance(experiment, Mapping):
                target = {
                    "provider": item.get("provider", "unknown"),
                    "hypothesis": experiment.get("hypothesis", ""),
                    "change": experiment.get("change", ""),
                    "metric_gate": experiment.get("metric_gate", ""),
                    "why_it_is_informative": experiment.get(
                        "why_it_is_informative",
                        "",
                    ),
                }
                if target["hypothesis"] or target["change"]:
                    targets.append(target)

    return {
        "status": "targets_available" if targets else "no_targets",
        "target_count": len(targets),
        "targets": targets,
        "action": "run_research_benchmark" if targets else "await_ai_review",
        "production_weights_changed": False,
        "verdict_mutated": False,
    }
