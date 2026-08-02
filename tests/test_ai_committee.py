from src.ai_committee import deliberate


def test_committee_requires_quorum_and_preserves_dissent() -> None:
    result = deliberate(
        {
            "reviews": [
                {
                    "provider": "groq",
                    "status": "completed",
                    "review": {
                        "proposals": [
                            {
                                "title": "Calibrate p_loss",
                                "component": "p_loss",
                                "change": "walk-forward calibration",
                            },
                        ],
                    },
                },
                {
                    "provider": "openrouter",
                    "status": "completed",
                    "review": {
                        "proposals": [
                            {
                                "title": "Calibrate p_loss",
                                "component": "p_loss",
                                "change": "walk-forward calibration",
                            },
                        ],
                    },
                },
                {
                    "provider": "qwen",
                    "status": "deferred",
                    "reason": "timeout",
                },
            ],
        },
    )
    assert result["status"] == "consensus_available"
    assert result["decisions"][0]["decision"] == "research_approved"
    assert result["completed_reviewers"] == ["groq", "openrouter"]
    assert result["production_weights_changed"] is False


def test_committee_safety_veto_blocks_unsafe_proposal() -> None:
    result = deliberate(
        {
            "reviews": [
                {
                    "provider": "a",
                    "status": "completed",
                    "review": {
                        "proposals": [
                            {
                                "title": "Auto trade",
                                "component": "executor",
                                "change": "create trades automatically",
                            },
                        ],
                    },
                },
                {
                    "provider": "b",
                    "status": "completed",
                    "review": {
                        "proposals": [
                            {
                                "title": "Auto trade",
                                "component": "executor",
                                "change": "create trades automatically",
                            },
                        ],
                    },
                },
            ],
        },
    )
    assert result["decisions"][0]["decision"] == "blocked_safety"
