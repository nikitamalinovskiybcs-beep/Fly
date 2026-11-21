"""Evidence-gated planner for selecting the next quant research candidate."""

from __future__ import annotations

from collections.abc import Mapping


CANDIDATE_KEYS = {
    "raw": "metrics",
    "calibrated": "calibrated_metrics",
    "quant": "quant_metrics",
    "duration_transfer": "duration_transfer_metrics",
    "path_quant": "path_quant_metrics",
    "regime_quant": "regime_quant_metrics",
}


def build_quant_improvement_proposal(report: Mapping) -> dict:
    """Rank candidates without mutating production configuration."""
    scores: dict[str, float] = {}
    for candidate, metric_key in CANDIDATE_KEYS.items():
        values = [
            float(
                anchor.get(metric_key, {}).get(
                    "brier_vs_baseline_pct",
                    -100.0,
                ),
            )
            for anchor in report.get("anchors", {}).values()
        ]
        scores[candidate] = sum(values) / len(values) if values else -100.0
    best = max(scores, key=scores.get, default="raw")
    gate = bool(report.get("candidate_gates", {}).get(best, False))
    return {
        "status": "proposal",
        "selected_candidate": best,
        "candidate_scores": {key: round(value, 2) for key, value in scores.items()},
        "candidate_gate_passed": gate,
        "action": "create_pr_for_review" if gate else "continue_research",
        "production_weights_changed": False,
        "verdict_mutated": False,
        "reason": (
            "candidate passed all 24-month anchors"
            if gate
            else "no candidate passed all 24-month anchors"
        ),
    }
