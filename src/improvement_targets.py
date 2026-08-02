"""Rank measurable improvement targets from Phoenix evidence reports."""

from __future__ import annotations

from collections.abc import Mapping


def build_improvement_targets(
    replay: Mapping,
    benchmark: Mapping | None = None,
) -> dict:
    """Return prioritized targets without mutating model or production state."""
    summary = replay.get("summary", {})
    oos = replay.get("oos_calibration_research", {})
    targets: list[dict] = []

    brier = float(summary.get("brier", 0.0))
    baseline_brier = float(summary.get("empirical_baseline_brier", 0.0))
    if baseline_brier and brier > baseline_brier:
        targets.append(
            {
                "id": "beat_empirical_brier",
                "priority": "critical",
                "current": brier,
                "target": round(baseline_brier * 0.95, 6),
                "unit": "brier",
                "action": "regime_aware_oos_calibration",
            }
        )

    probability_gap = float(summary.get("mean_absolute_probability_gap", 0.0))
    if probability_gap > 0.10:
        targets.append(
            {
                "id": "reduce_probability_gap",
                "priority": "high",
                "current": probability_gap,
                "target": 0.10,
                "unit": "absolute_probability",
                "action": "sector_and_regime_calibration",
            }
        )

    if int(oos.get("oos_observations", 0)) < 20:
        targets.append(
            {
                "id": "increase_oos_observations",
                "priority": "critical",
                "current": int(oos.get("oos_observations", 0)),
                "target": 20,
                "unit": "realized_or_replay_observations",
                "action": "collect_chronological_outcomes",
            }
        )

    if benchmark:
        ece = float(benchmark.get("ece", 0.0))
        if ece > 0.05:
            targets.append(
                {
                    "id": "reduce_ece",
                    "priority": "high",
                    "current": ece,
                    "target": 0.05,
                    "unit": "expected_calibration_error",
                    "action": "recalibrate_probabilities",
                }
            )

    coverage = float(replay.get("universe_with_data", 0)) / max(
        1, int(replay.get("universe_requested", 1)),
    )
    if coverage < 1.0:
        targets.append(
            {
                "id": "complete_market_data_coverage",
                "priority": "medium",
                "current": round(coverage, 4),
                "target": 1.0,
                "unit": "coverage_ratio",
                "action": "secondary_source_fallback_and_quality_gate",
            }
        )

    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    targets.sort(key=lambda item: priority_order[item["priority"]])
    return {
        "source": "evidence_target_planner",
        "status": "proposal",
        "targets": targets,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "gate": "targets require new chronological OOS evidence before apply",
    }
