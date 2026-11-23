from src.continuous_improvement import build_cycle_plan


def test_cycle_stops_after_plateau() -> None:
    history = [
        {"target_id": "brier", "result": "no_improvement"},
        {"target_id": "brier", "result": "no_improvement"},
        {"target_id": "brier", "result": "no_improvement"},
    ]
    result = build_cycle_plan(
        [{"id": "brier", "priority": "critical", "action": "calibrate"}],
        history,
    )
    assert result["status"] == "plateau"
    assert result["production_weights_changed"] is False


def test_cycle_proposes_pr_without_mutation() -> None:
    result = build_cycle_plan(
        [{"id": "brier", "priority": "critical", "action": "calibrate"}],
    )
    assert result["action"] == "create_pr_for_review"
    assert result["verdict_mutated"] is False
