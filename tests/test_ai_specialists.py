import pytest

from src.ai_specialists import run_specialist, specialist_registry


def test_quant_specialist_blocks_incomplete_evidence() -> None:
    result = run_specialist("quant_payoff", {"p_ki": 0.2})
    assert result["status"] == "blocked"
    assert "missing:payoff_state_machine" in result["blockers"]
    assert result["production_weights_changed"] is False


def test_calibration_specialist_requires_fixed_24m_baseline() -> None:
    result = run_specialist(
        "calibration_oos",
        {
            "term_months": 12,
            "anchors": (6, 12),
            "baseline_metric": 0.2,
            "model_metric": 0.1,
            "brier": 0.1,
            "log_loss": 0.2,
            "ece": 0.05,
        },
    )
    assert result["status"] == "blocked"
    assert "fixed-24m-required" in result["blockers"]
    assert "baseline-not-beaten" in result["blockers"]


def test_complete_calibration_review_is_research_only() -> None:
    result = run_specialist(
        "calibration_oos",
        {
            "term_months": 24,
            "anchors": (6, 12, 18, 24),
            "baseline_metric": 0.2,
            "model_metric": 0.3,
            "brier": 0.1,
            "log_loss": 0.2,
            "ece": 0.05,
        },
    )
    assert result["status"] == "ready_for_research"
    assert result["research_only"] is True
    assert result["verdict_mutated"] is False


def test_registry_enables_only_first_two_roles() -> None:
    registry = specialist_registry()
    assert [item["enabled"] for item in registry] == [
        True,
        True,
        False,
        False,
        False,
    ]


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown specialist role"):
        run_specialist("marketing", {})
