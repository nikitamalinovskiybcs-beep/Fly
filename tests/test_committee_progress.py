from src.committee_progress import build_progress_score


def test_progress_score_is_bounded_and_separates_market_gate() -> None:
    result = build_progress_score(
        benchmark={
            "product_term_months": 24,
            "candidate_gates": {"raw": False},
        },
        health={
            "status": "attention_required",
            "checks": {"data_quality": True},
            "production_weights_changed": False,
            "verdict_mutated": False,
        },
        structure={"passed": True, "syntax_errors": []},
        evidence={"provenance_gate": True, "payoff_tests": True},
    )
    assert 0 <= result["score_0_to_100"] <= 100
    assert result["interpretation"].startswith("implementation_progress")
    assert result["production_weights_changed"] is False
