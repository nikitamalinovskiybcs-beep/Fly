from scripts.validate_release_gate import validate_release_gate


def test_release_gate_requires_health_and_safety_artifacts() -> None:
    result = validate_release_gate(
        {
            "status": "healthy",
            "checks": {"production_safety": True},
        },
        {
            "mode": "research_only",
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
            "requires_human_review_for_merge": True,
        },
    )

    assert result["passed"] is True


def test_release_gate_blocks_mutated_safety_artifact() -> None:
    result = validate_release_gate(
        {
            "status": "healthy",
            "checks": {"production_safety": True},
        },
        {
            "mode": "research_only",
            "production_weights_changed": True,
            "verdict_mutated": False,
            "trades_created": False,
            "requires_human_review_for_merge": True,
        },
    )

    assert result["status"] == "blocked"
