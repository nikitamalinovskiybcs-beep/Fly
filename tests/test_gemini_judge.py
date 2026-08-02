from __future__ import annotations

import json

import pytest

from src.gemini_judge import _extract_json, build_judge_prompt, judge_report


def test_extract_json_accepts_markdown_fence() -> None:
    assert _extract_json("```json\n{\"verdict\": \"revise\"}\n```") == {
        "verdict": "revise",
    }


def test_prompt_includes_evidence_and_safety_rule() -> None:
    prompt = build_judge_prompt({"anchors": {"6": {}}}, {"action": "continue_research"})
    assert "continue_research" in prompt
    assert "No candidate may be promoted" in prompt


def test_prompt_requests_independent_brainstorm_proposals() -> None:
    prompt = build_judge_prompt(
        {
            "review_type": "phoenix_improvement_brainstorm",
            "count": 100,
            "proposals": [],
        },
        {},
    )
    assert "at least five independent proposals" in prompt
    assert "do not just return yes/no" in prompt


def test_judge_report_is_production_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "verdict": "revise",
                                            "summary": "Keep researching.",
                                        },
                                    ),
                                },
                            ],
                        },
                    },
                ],
            }

    monkeypatch.setattr("src.gemini_judge.requests.post", lambda *args, **kwargs: Response())
    result = judge_report({}, {}, "test-key")
    assert result["provider"] == "google_gemini"
    assert result["production_weights_changed"] is False
    assert result["verdict_mutated"] is False
