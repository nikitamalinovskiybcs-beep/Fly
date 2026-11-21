"""Evidence-gated adaptive calibration proposals for realized note outcomes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from src.math_evaluation import brier_score, expected_calibration_error, log_loss


MIN_OBSERVATIONS = 20
MIN_OOS_OBSERVATIONS = 8
AUDIT_PATH = Path("data/calibration_agent/audit.json")


def _realized_probability_rows(notes: Iterable[Mapping]) -> list[tuple[float, int]]:
    rows: list[tuple[float, int]] = []
    for note in notes:
        outcome = note.get("outcome", {})
        metadata = note.get("metadata", {})
        if (
            note.get("status") != "realized"
            or outcome.get("source") != "realized"
            or not outcome.get("learning_eligible")
        ):
            continue
        probability = metadata.get("predicted_autocall_prob")
        if probability is None:
            continue
        actual = int(outcome.get("outcome_type") == "autocall")
        rows.append((float(probability), actual))
    return rows


def _metrics(probabilities: list[float], outcomes: list[int]) -> dict[str, float]:
    return {
        "brier": round(brier_score(probabilities, outcomes), 6),
        "log_loss": round(log_loss(probabilities, outcomes), 6),
        "ece": round(expected_calibration_error(probabilities, outcomes), 6),
    }


def _candidate_probability(probability: float, prior: float, strength: float) -> float:
    return min(1.0, max(0.0, strength * probability + (1.0 - strength) * prior))


def build_calibration_proposal(
    notes: Iterable[Mapping],
    minimum_observations: int = MIN_OBSERVATIONS,
) -> dict:
    """Evaluate a shrinkage calibration candidate without changing production state."""
    rows = _realized_probability_rows(notes)
    if len(rows) < minimum_observations:
        return {
            "status": "blocked",
            "reason": "insufficient_realized_probability_observations",
            "observations": len(rows),
            "minimum_observations": minimum_observations,
        }

    split = max(1, int(len(rows) * 0.6))
    train = rows[:split]
    test = rows[split:]
    prior = sum(actual for _, actual in train) / len(train)
    strengths = [round(value / 10, 1) for value in range(5, 11)]
    scored = []
    for strength in strengths:
        probabilities = [
            _candidate_probability(probability, prior, strength)
            for probability, _ in train
        ]
        scored.append(
            (
                brier_score(probabilities, [actual for _, actual in train]),
                strength,
            )
        )
    train_brier, strength = min(scored)

    test_probabilities = [
        _candidate_probability(probability, prior, strength)
        for probability, _ in test
    ]
    test_outcomes = [actual for _, actual in test]
    baseline_probabilities = [prior] * len(test)
    candidate_metrics = _metrics(test_probabilities, test_outcomes)
    baseline_metrics = _metrics(baseline_probabilities, test_outcomes)
    passed = (
        len(test) >= MIN_OOS_OBSERVATIONS
        and candidate_metrics["brier"] <= baseline_metrics["brier"]
    )
    return {
        "status": "proposal" if passed else "blocked",
        "reason": "oos_brier_improvement" if passed else "oos_gate_failed",
        "observations": len(rows),
        "oos_observations": len(test),
        "prior": round(prior, 6),
        "strength": strength,
        "train_brier": round(train_brier, 6),
        "candidate_oos": candidate_metrics,
        "baseline_oos": baseline_metrics,
        "apply_action": "create_pr_for_review" if passed else "no_change",
        "production_weights_changed": False,
    }


def run_calibration_cycle(
    notes: Iterable[Mapping],
    audit_path: Path = AUDIT_PATH,
) -> dict:
    """Run one auditable cycle and persist the proposal or block reason."""
    proposal = build_calibration_proposal(notes)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "calibration_agent",
        **proposal,
    }
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    history: list[dict] = []
    if audit_path.exists():
        try:
            loaded = json.loads(audit_path.read_text())
            if isinstance(loaded, list):
                history = loaded
        except (OSError, ValueError):
            history = []
    history.append(record)
    audit_path.write_text(json.dumps(history[-100:], indent=2))
    return record
