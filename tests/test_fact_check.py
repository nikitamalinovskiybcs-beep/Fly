from src.fact_check import build_fact_check_report


def test_fact_check_blocks_unverified_claims() -> None:
    result = build_fact_check_report(
        [
            {"claim_id": "c1", "claim": "quote is a settled outcome", "evidence_ids": ["q1"]},
            {"claim_id": "c2", "claim": "missing evidence", "evidence_ids": []},
        ],
        {"q1": {"verified": False}},
    )

    assert result["status"] == "blocked"
    assert result["unsupported_or_unverified"] == ["c1", "c2"]


def test_fact_check_passes_verified_claims() -> None:
    result = build_fact_check_report(
        [{"claim_id": "c1", "claim": "source verified", "evidence_ids": ["e1"]}],
        {"e1": {"verified": True}},
    )

    assert result["status"] == "passed"
