from src.production_readiness import REQUIRED_BLOCKS, build_production_readiness_report


def _ready_blocks() -> dict[str, dict[str, object]]:
    return {
        name: {
            "status": "ready",
            "owner": f"owner-{name}",
            "metric_gate": f"gate-{name}",
            "evidence": f"evidence-{name}",
        }
        for name in REQUIRED_BLOCKS
    }


def test_production_readiness_blocks_missing_evidence() -> None:
    blocks = _ready_blocks()
    blocks["oos"]["status"] = "blocked"
    result = build_production_readiness_report(
        blocks,
        safety={
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
        },
    )
    assert result["status"] == "blocked"
    assert "oos:blocked" in result["blockers"]
    assert result["human_review_required"] is True


def test_production_readiness_requires_all_safety_flags() -> None:
    result = build_production_readiness_report(
        _ready_blocks(),
        safety={
            "production_weights_changed": False,
            "verdict_mutated": False,
        },
    )
    assert result["status"] == "blocked"
    assert "safety:trades_created" in result["blockers"]
    assert result["trades_created"] is False


def test_production_readiness_can_be_ready_before_human_review() -> None:
    result = build_production_readiness_report(
        _ready_blocks(),
        safety={
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
        },
    )
    assert result["status"] == "ready"
    assert result["research_only"] is False
    assert result["human_review_required"] is True
