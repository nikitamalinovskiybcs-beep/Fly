from src.research_priorities import rank_research_candidates


def test_research_priorities_rank_high_information_low_cost_first() -> None:
    result = rank_research_candidates(
        [
            {"id": "satellite", "information_gain": 9, "feasibility": 3, "safety": 8, "cost": 8},
            {"id": "settled_notes", "information_gain": 10, "feasibility": 8, "safety": 10, "cost": 2},
        ],
    )

    assert result[0]["id"] == "settled_notes"
    assert result[0]["decision"] == "research_only"
