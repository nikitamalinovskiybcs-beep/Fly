from src.quant_improvement import build_quant_improvement_proposal


def test_quant_improvement_stays_proposal_only() -> None:
    result = build_quant_improvement_proposal(
        {
            "anchors": {
                "6": {"metrics": {"brier_vs_baseline_pct": -5}},
                "12": {"metrics": {"brier_vs_baseline_pct": -5}},
            },
            "candidate_gates": {"raw": False},
        },
    )
    assert result["selected_candidate"] == "raw"
    assert result["action"] == "continue_research"
    assert result["production_weights_changed"] is False
