from __future__ import annotations

from src.ai_judge_panel import run_judge_panel


def test_panel_skips_unconfigured_providers() -> None:
    result = run_judge_panel({}, {}, environ={})
    assert result["status"] == "deferred"
    assert result["consensus_verdict"] == "unavailable"
    assert len(result["reviews"]) == 7
    assert result["production_weights_changed"] is False


def test_panel_uses_gemini_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.ai_judge_panel.judge_report",
        lambda report, proposal, api_key: {
            "verdict": "revise",
            "production_weights_changed": False,
        },
    )
    result = run_judge_panel({}, {}, environ={"GEMINI_API_KEY": "configured"})
    assert result["status"] == "completed"
    assert result["consensus_verdict"] == "revise"
    assert result["completed_providers"] == ["google_gemini"]
