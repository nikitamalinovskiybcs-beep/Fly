from src.evidence_contracts import (
    validate_alternative_feature,
    validate_bcs_quote,
    validate_fixed_24m_outcome,
)


def test_fixed_24m_contract_rejects_wrong_term() -> None:
    result = validate_fixed_24m_outcome(
        {
            "note_id": "n1",
            "basket": ["AAPL", "MSFT"],
            "as_of": "2024-01-01",
            "maturity_date": "2026-01-01",
            "outcome_type": "no_loss",
            "source": "realized",
            "observations": [],
            "term_months": 12,
        },
    )

    assert result["valid"] is False
    assert "term_months_must_equal_24" in result["errors"]


def test_bcs_contract_requires_only_bcs_capital() -> None:
    result = validate_bcs_quote(
        {
            "quote_id": "q1",
            "dealer": "Other",
            "quote_timestamp": "2026-01-01T00:00:00Z",
            "basket": ["AAPL", "MSFT"],
            "barrier": 0.60,
            "coupon_pa": 0.20,
            "term_months": 24,
        },
    )

    assert result["valid"] is False
    assert "dealer_must_be_bcs_capital" in result["errors"]


def test_alternative_feature_rejects_post_outcome_data() -> None:
    result = validate_alternative_feature(
        {
            "feature_id": "footfall",
            "ticker": "WMT",
            "feature_timestamp": "2026-02-01",
            "outcome_timestamp": "2026-01-01",
            "source": "vendor",
            "license_status": "licensed_or_public",
        },
    )

    assert result["valid"] is False
    assert "feature_timestamp_after_outcome" in result["errors"]
