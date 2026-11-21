from src.ai_screening import build_screening_target_plan


def test_screening_plan_extracts_bounded_targets() -> None:
    panel = {
        "reviews": [
            {
                "provider": "ollama:qwen2.5:7b",
                "status": "completed",
                "review": {
                    "next_experiments": [
                        {"hypothesis": "tail dependence", "change": "t-copula"},
                        {"hypothesis": "barrier bias", "change": "bridge"},
                        {"hypothesis": "calibration", "change": "isotonic"},
                        {"hypothesis": "ignored", "change": "fourth"},
                    ],
                },
            },
        ],
    }
    result = build_screening_target_plan(panel)
    assert result["target_count"] == 3
    assert result["action"] == "run_research_benchmark"
    assert result["production_weights_changed"] is False


def test_formula_findings_become_bounded_targets() -> None:
    result = build_screening_target_plan(
        {
            "reviews": [
                {
                    "provider": "groq",
                    "status": "completed",
                    "review": {
                        "findings": [
                            {
                                "action": "REPLACE",
                                "component": "p_loss",
                                "replacement": "calibrated p_loss",
                                "reason": "not calibrated",
                                "metric_gate": "fixed-24m OOS gate",
                            },
                            {"action": "KEEP", "component": "audit trail"},
                        ],
                    },
                },
            ],
        },
    )
    assert result["target_count"] == 1
    assert result["targets"][0]["change"] == "calibrated p_loss"


def test_system_prioritized_findings_use_fixed_anchor_gate() -> None:
    result = build_screening_target_plan(
        {
            "reviews": [
                {
                    "provider": "openrouter",
                    "status": "completed",
                    "review": {
                        "prioritized_findings": [
                            {
                                "action": "REPLACE",
                                "component": "calibration",
                                "replacement": "walk-forward calibration",
                                "metric_gate": "accuracy above 75%",
                            },
                        ],
                    },
                },
            ],
        },
    )
    assert result["target_count"] == 1
    assert "fixed-24m OOS" in result["targets"][0]["metric_gate"]
