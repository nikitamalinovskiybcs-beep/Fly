from src.data_quality import (
    compare_price_sources,
    validate_learning_provenance,
    validate_market_snapshot,
    validate_macro_snapshot,
)


def test_compare_price_sources_flags_large_gap() -> None:
    result = compare_price_sources(
        {"AAPL": [100.0, 101.0]},
        {"AAPL": [100.0, 110.0]},
        max_relative_gap=0.02,
    )
    assert result["passed"] is False
    assert result["checks"]["AAPL"]["overlap"] == 2


def test_validate_macro_snapshot_rejects_invalid_vix() -> None:
    result = validate_macro_snapshot({"vix": 250})
    assert result["passed"] is False
    assert "vix_out_of_range" in result["issues"]


def test_macro_snapshot_accepts_free_source_metadata() -> None:
    result = validate_macro_snapshot(
        {
            "vix": 18,
            "rate_10y": 4.2,
            "rate_2y": 4.0,
            "fed_rate": 4.5,
            "source": "fred_partial",
        }
    )
    assert result["passed"] is True


def test_learning_provenance_blocks_replay_rows() -> None:
    result = validate_learning_provenance(
        [
            {
                "source": "historical_replay",
                "as_of": "2025-01-01",
                "status": "realized",
                "learning_eligible": True,
            },
        ],
    )
    assert result["passed"] is False
    assert "row_0_non_independent_source" in result["issues"]


def test_market_snapshot_requires_fresh_positive_prices() -> None:
    result = validate_market_snapshot(
        {"prices": {"AAPL": 100, "MSFT": -1}, "as_of": "not-a-date"},
    )
    assert result["passed"] is False
    assert "MSFT_non_positive_price" in result["issues"]
    assert "invalid_as_of" in result["issues"]
