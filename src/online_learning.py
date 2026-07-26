"""Guarded online-learning policy for realized structured-note outcomes."""

from statistics import mean, pstdev
from typing import Dict, List


MIN_REALIZED_OBSERVATIONS = 5
MAX_ACCURACY_DRIFT = 12.0


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
    from src.self_learning_agents import MetaAgent

    history = [
        item for item in feedback
        if item.get("source") == "realized"
        and item.get("learning_eligible") is True
        and item.get("agent_accuracies")
    ]
    MetaAgent().update_weights(history)
    return {"status": "updated", "gate": gate}
