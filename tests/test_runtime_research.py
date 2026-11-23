from src.runtime_research import build_runtime_research_status


def test_runtime_research_exposes_blockers_without_mutation() -> None:
    result = build_runtime_research_status(
        {"evidence_gate": {"passed": False}},
        {},
    )

    assert result["status"] == "blocked"
    assert "data_readiness" in result["blocking_stages"]
    assert "fact_check" in result["blocking_stages"]
    assert result["production_weights_changed"] is False
    assert result["verdict_mutated"] is False
    assert result["trades_created"] is False
