import json

from src.ai_consensus_plan import build_plan


def test_consensus_plan_preserves_safety_and_fixed_gate(tmp_path) -> None:
    report = tmp_path / "panel.json"
    report.write_text(
        json.dumps(
            {
                "reviews": [
                    {
                        "provider": "test",
                        "status": "completed",
                        "review": {
                            "verdict": "reject",
                            "findings": [
                                {"action": "REMOVE", "component": "p_loss"},
                            ],
                        },
                    },
                ],
            },
        ),
        encoding="utf-8",
    )
    result = build_plan(
        [str(report)],
    )
    assert result["consensus_verdict"] == "reject"
    assert result["production_weights_changed"] is False
    assert result["verdict_mutated"] is False
    assert "fixed-24m OOS" in result["plan"][0]["gate"]
