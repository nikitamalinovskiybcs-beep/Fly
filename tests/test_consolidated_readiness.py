from src.consolidated_readiness import evaluate_readiness


def complete_evidence() -> dict[str, object]:
    return {
        "term_months": 24,
        "anchors": (6, 12, 18, 24),
        "provenance_complete": True,
        "baseline_beaten": True,
    }


def complete_committee() -> dict[str, object]:
    return {
        "quorum": True,
        "completed_votes": 3,
        "approval_votes": 3,
        "unavailable": [{"provider": "ollama", "status": "timeout"}],
        "dissent": [{"provider": "groq", "verdict": "revise"}],
    }


def test_missing_fixed_24m_and_provenance_blocks_readiness() -> None:
    result = evaluate_readiness(
        {"term_months": 12, "provenance_complete": False},
        {"quorum": False},
    )
    assert result["status"] == "blocked"
    assert "fixed-24m-required" in result["blockers"]
    assert "provenance-incomplete" in result["blockers"]
    assert result["production_approval"] is False


def test_complete_controls_are_research_ready_not_production_approved() -> None:
    result = evaluate_readiness(complete_evidence(), complete_committee())
    assert result["status"] == "research_ready"
    assert result["production_approval"] is False
    assert result["conditions_precedent"]


def test_unavailable_and_dissent_remain_visible() -> None:
    result = evaluate_readiness(complete_evidence(), complete_committee())
    lineage = result["committee_lineage"]
    assert lineage["unavailable"][0]["provider"] == "ollama"
    assert lineage["dissent"][0]["verdict"] == "revise"


def test_safety_flags_are_explicit_and_false() -> None:
    result = evaluate_readiness(complete_evidence(), complete_committee())
    assert result["safety_flags"] == {
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
