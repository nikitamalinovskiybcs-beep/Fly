"""Guarded online-learning policy for realized structured-note outcomes."""

import json
from statistics import mean, pstdev
from pathlib import Path
from typing import Dict, List

from src.self_learning_agents import MetaAgent


MIN_REALIZED_OBSERVATIONS = 5
MAX_ACCURACY_DRIFT = 12.0


def load_realized_feedback(path: Path | None = None) -> List[Dict]:
    """Load persisted feedback without including non-realized sources."""
    if path is None:
        from src.outcome_engine import REALIZED_FEEDBACK_PATH

        path = REALIZED_FEEDBACK_PATH
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    return [item for item in payload if isinstance(item, dict)]


def assess_learning_gate(feedback: List[Dict]) -> Dict:
    """Decide whether realized feedback is safe to use for weight updates."""
    eligible = [
        item for item in feedback
        if item.get("source") == "realized"
        and item.get("learning_eligible") is True
        and item.get("agent_accuracies")
    ]
    if len(eligible) < MIN_REALIZED_OBSERVATIONS:
        return {
            "passed": False,
            "status": "blocked",
            "reason": "insufficient_realized_observations",
            "observations": len(eligible),
        }

    values = [
        float(accuracy)
        for item in eligible
        for accuracy in item["agent_accuracies"].values()
    ]
    if not values:
        return {
            "passed": False,
            "status": "blocked",
            "reason": "missing_agent_labels",
            "observations": len(eligible),
        }
    recent = [
        float(accuracy)
        for item in eligible[-3:]
        for accuracy in item["agent_accuracies"].values()
    ]
    drift = abs(mean(recent) - mean(values))
    if drift > MAX_ACCURACY_DRIFT:
        return {
            "passed": False,
            "status": "blocked",
            "reason": "calibration_drift",
            "observations": len(eligible),
            "drift": round(drift, 3),
        }
    return {
        "passed": True,
        "status": "approved",
        "reason": "realized_only_calibration",
        "observations": len(eligible),
        "accuracy_mean": round(mean(values), 3),
        "accuracy_std": round(pstdev(values), 3),
        "drift": round(drift, 3),
    }


def apply_guarded_learning(feedback: List[Dict]) -> Dict:
    """Update Meta weights only after the realized-data gate passes."""
    gate = assess_learning_gate(feedback)
    if not gate["passed"]:
        return {"status": "blocked", "gate": gate}
    return {
        "status": "candidate",
        "gate": gate,
        "reason": "out_of_sample_gate_required",
    }


def apply_out_of_sample_learning(
    feedback: List[Dict],
    out_of_sample_gate: Dict,
) -> Dict:
    """Publish new weights only after realized and OOS gates pass."""
    gate = assess_learning_gate(feedback)
    if not gate["passed"]:
        return {"status": "blocked", "gate": gate}
    if not out_of_sample_gate.get("passed", False):
        return {
            "status": "blocked",
            "gate": gate,
            "out_of_sample_gate": out_of_sample_gate,
            "reason": "out_of_sample_gate_failed",
        }
    history = [
        item for item in feedback
        if item.get("source") == "realized"
        and item.get("learning_eligible") is True
        and item.get("agent_accuracies")
    ]
    agent = MetaAgent()
    before = dict(agent.weights)
    agent.update_weights(history)
    after = dict(agent.weights)
    return {
        "status": "updated",
        "gate": gate,
        "out_of_sample_gate": out_of_sample_gate,
        "weight_deltas": {
            name: round(float(after.get(name, 0.0) - before.get(name, 0.0)), 6)
            for name in after
        },
    }
