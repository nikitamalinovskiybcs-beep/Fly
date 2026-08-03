from src.recalculation_inputs import build_recalculation_profile


def test_recalculation_profile_blocks_missing_contract_fields() -> None:
    result = build_recalculation_profile({"note_id": "n1"})

    assert result["status"] == "blocked"
    assert "basket" in result["missing_fields"]
    assert result["recalculable"] is False


def test_recalculation_profile_discloses_assumptions() -> None:
    result = build_recalculation_profile(
        {
            "note_id": "n1",
            "launch_date": "2025-01-01",
            "maturity_date": "2027-01-01",
            "basket": ["AAPL", "MSFT"],
            "initial_levels": {"AAPL": 100, "MSFT": 100},
            "observation_dates": ["2025-04-01"],
            "observation_paths": [{"AAPL": 100, "MSFT": 100}],
        },
        {
            "barrier": 0.65,
            "strike": 1.0,
            "coupon_pa": 0.2,
            "autocall_schedule": [],
            "memory_coupon": True,
        },
    )

    assert result["status"] == "ready"
    assert result["mode"] == "assumption_based"
    assert result["requires_disclosure"] is True
    assert "barrier" in result["assumed_fields"]
