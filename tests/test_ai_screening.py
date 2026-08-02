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
