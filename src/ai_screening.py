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
        review_targets: list[dict[str, object]] = []
        findings = review.get("findings", [])
        if isinstance(findings, list):
            for finding in findings[:3]:
                if not isinstance(finding, Mapping):
                    continue
                action = finding.get("action", "")
                component = finding.get("component", "")
                if action not in {"REMOVE", "REPLACE"} or not component:
                    continue
                replacement = finding.get("replacement", "")
                target = {
                    "provider": item.get("provider", "unknown"),
                    "hypothesis": f"{action} {component} improves fixed-24m KPI",
                    "change": replacement or f"remove {component} from candidate",
                    "metric_gate": finding.get(
                        "metric_gate",
                        "fixed-24m OOS Brier and log-loss beat baseline",
                    ),
                    "why_it_is_informative": finding.get("reason", ""),
                }
                review_targets.append(target)
        experiments = review.get("next_experiments", [])
        if isinstance(experiments, list):
            for experiment in experiments[:3]:
                if len(review_targets) >= 3:
                    break
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
                        review_targets.append(target)
        targets.extend(review_targets[:3])

    return {
        "status": "targets_available" if targets else "no_targets",
        "target_count": len(targets),
        "targets": targets,
        "action": "run_research_benchmark" if targets else "await_ai_review",
        "production_weights_changed": False,
        "verdict_mutated": False,
    }
