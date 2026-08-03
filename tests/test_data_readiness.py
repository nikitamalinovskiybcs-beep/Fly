from src.data_readiness import build_data_readiness_report


def test_data_readiness_blocks_missing_sources() -> None:
    result = build_data_readiness_report(
        {
            "settled_24m_notes": [
                {
                    "note_id": "n1",
                    "basket": ["AAPL", "MSFT"],
                    "as_of": "2024-01-01",
                    "maturity_date": "2026-01-01",
                    "outcome_type": "no_loss",
                    "observations": [{"date": "2025-01-01", "levels": {"AAPL": 1.0}}],
                },
            ],
        },
    )

    assert result["status"] == "blocked"
    assert "bcs_capital_quotes" in result["blockers"]
    assert result["production_weights_changed"] is False


def test_data_readiness_is_ready_only_when_all_sources_are_complete() -> None:
    row = {
        "ticker": "WMT",
        "source": "licensed_or_public",
        "as_of": "2025-01-01",
        "observation_timestamp": "2025-01-01",
        "feature_timestamp": "2025-01-01",
        "level": 1.0,
        "strike": 1.0,
        "tenor": 24,
        "iv": 0.3,
        "license_status": "licensed_or_public",
        "feature_id": "footfall",
    }
    result = build_data_readiness_report(
        {
            "settled_24m_notes": [{
                "note_id": "n1",
                "basket": ["AAPL", "MSFT"],
                "as_of": "2024-01-01",
                "maturity_date": "2026-01-01",
                "outcome_type": "no_loss",
                "observations": [{"date": "2025-01-01", "levels": {"AAPL": 1.0}}],
            }],
            "observation_paths": [row],
            "bcs_capital_quotes": [{
                "quote_id": "q1",
                "quote_timestamp": "2025-01-01",
                "basket": ["AAPL", "MSFT"],
                "barrier": 0.6,
                "coupon_pa": 0.2,
            }],
            "iv_surfaces": [row],
            "alternative_features": [row],
        },
    )

    assert result["status"] == "ready"
    assert result["next_action"] == "run_leakage_safe_oos_validation"
