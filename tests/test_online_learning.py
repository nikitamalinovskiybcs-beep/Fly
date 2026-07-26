from src.online_learning import assess_learning_gate, apply_guarded_learning


def _feedback(source: str, eligible: bool = True, accuracy: float = 80.0) -> dict:
    return {
        "source": source,
        "learning_eligible": eligible,
        "agent_accuracies": {"sentiment": accuracy, "alpha": accuracy - 2},
    }


def test_paper_feedback_cannot_train() -> None:
    feedback = [_feedback("paper") for _ in range(10)]

    gate = assess_learning_gate(feedback)

    assert gate["passed"] is False
    assert gate["reason"] == "insufficient_realized_observations"
    assert apply_guarded_learning(feedback)["status"] == "blocked"


def test_realized_feedback_passes_after_minimum_sample() -> None:
    feedback = [_feedback("realized") for _ in range(5)]

    gate = assess_learning_gate(feedback)

    assert gate["passed"] is True
    assert gate["reason"] == "realized_only_calibration"


def test_drift_blocks_weight_update() -> None:
    feedback = [_feedback("realized", accuracy=80) for _ in range(5)]
    feedback[-3:] = [_feedback("realized", accuracy=45) for _ in range(3)]

    gate = assess_learning_gate(feedback)

    assert gate["passed"] is False
    assert gate["reason"] == "calibration_drift"
