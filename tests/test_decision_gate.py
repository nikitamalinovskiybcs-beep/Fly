from src.decision_gate import build_decision_gate


def test_missing_quote_fit_blocks_good_verdict() -> None:
    result = build_decision_gate(
        {
            "p_ki": 20,
            "empirical_pki": {"p_ki_empirical": 18},
            "recommendation": {"action": "BUY"},
            "score": 82,
            "sl_agents": {"signal_disagreement": 0.1},
        },
        {"best": {"basket": ["A", "B", "C"]}},
        {"passed": True},
    )
    assert result["verdict"] == "CAUTION"
    assert "dealer_quote_fit_missing" in result["reasons"]


def test_large_pki_gap_is_visible() -> None:
    result = build_decision_gate(
        {
            "p_ki": 70,
            "empirical_pki": {"p_ki_empirical": 10},
            "recommendation": {"action": "HOLD"},
            "score": 72,
            "sl_agents": {"signal_disagreement": 0.1},
        },
        {"best": {"dealer_quote_fit": {"observed": True}}},
        {"passed": True},
    )
    assert result["verdict"] == "CAUTION"
    assert "model_empirical_pki_gap_above_25pct" in result["reasons"]
