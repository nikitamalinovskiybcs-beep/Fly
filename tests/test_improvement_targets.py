from src.improvement_targets import build_improvement_targets


def test_target_planner_prioritizes_baseline_gap_without_mutation() -> None:
    result = build_improvement_targets(
        {
            "universe_requested": 80,
            "universe_with_data": 78,
            "summary": {
                "brier": 0.10,
                "empirical_baseline_brier": 0.08,
                "mean_absolute_probability_gap": 0.20,
            },
            "oos_calibration_research": {"oos_observations": 8},
        },
        {"ece": 0.12},
    )
    assert result["targets"][0]["id"] == "beat_empirical_brier"
    assert result["production_weights_changed"] is False
    assert result["verdict_mutated"] is False
