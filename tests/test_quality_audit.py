"""Regression tests for honest fallbacks and synthetic-data provenance."""

import numpy as np


def test_zero_realized_outcomes_are_pilot_only() -> None:
    from src.commercial_readiness import assess_commercial_readiness

    result = assess_commercial_readiness(
        {"passed": True},
        {"realized_notes": 0, "historical_windows": 50},
    )

    assert result["status"] == "pilot_ready"
    assert result["pilot_ready"] is True
    assert result["production_ready"] is False
    assert "guaranteed returns" in result["blocked_claim"]


def test_incomplete_market_evidence_blocks_live_use() -> None:
    from src.commercial_readiness import assess_commercial_readiness

    result = assess_commercial_readiness(
        {"passed": False},
        {"realized_notes": 0, "historical_windows": 0},
    )

    assert result["status"] == "not_ready"
    assert result["pilot_ready"] is False


def test_market_data_fallback_is_deterministic_and_marked_estimated(monkeypatch) -> None:
    import src.data_module as data_module

    monkeypatch.setattr(data_module, "XFL_AVAILABLE", False)
    monkeypatch.setattr(data_module, "YF_AVAILABLE", False)

    first = data_module.fetch_ticker_data(["TEST"])["TEST"]
    second = data_module.fetch_ticker_data(["TEST"])["TEST"]

    assert first["source"] == "estimated"
    assert first["is_real"] is False
    assert "warning" in first
    np.testing.assert_array_equal(first["returns"], second["returns"])


def test_synthetic_calibration_rows_are_reproducible() -> None:
    from src.accuracy_boost import generate_synthetic_baskets

    settled = [("AAPL/MSFT/GOOG", 2.0, 0), ("AMD/NIO/TSLA", 2.5, 1)]
    first = generate_synthetic_baskets(settled, n_synthetic=10, seed=7)
    second = generate_synthetic_baskets(settled, n_synthetic=10, seed=7)

    assert first == second


def test_random_synthetic_basket_batch_has_requested_size() -> None:
    from src.accuracy_boost import generate_synthetic_baskets

    settled = [("AAPL/MSFT/GOOG", 2.0, 0), ("AMD/NIO/TSLA", 2.5, 1)]
    rows = generate_synthetic_baskets(
        settled,
        n_synthetic=100,
        seed=11,
        random_only=True,
    )

    assert len(rows) == 100
    assert all(len(row) == 3 for row in rows)


def test_neural_score_is_explicitly_a_heuristic() -> None:
    from src.accuracy_boost import neural_score

    assert 50.0 <= neural_score(np.array([0.2, 0.3, 0.8, 1.0, 3.0, 0.1])) <= 100.0
    assert neural_score(np.array([0.2, 0.3, 0.8, 1.0, 3.0, 0.1])) == neural_score(
        np.array([0.2, 0.3, 0.8, 1.0, 3.0, 0.1]),
    )


def test_scheduler_connects_complete_market_data_to_product_agents(monkeypatch) -> None:
    import src.scheduler as scheduler_module

    seen = {}

    def fake_market_data(tickers):
        return {ticker: {"source": "yfinance"} for ticker in tickers}

    def fake_product_search(universe, basket_size, yf_data=None):
        seen["yf_data"] = yf_data
        return {
            "best": {"basket": universe[:basket_size]},
            "n_evaluated": 1,
            "recommendation": "test",
        }

    monkeypatch.setattr("src.data_module.fetch_ticker_data", fake_market_data)
    monkeypatch.setattr(
        "src.structured_product.find_best_structured_product",
        fake_product_search,
    )

    result = scheduler_module.FlyScheduler(
        universe=["AAPL", "MSFT", "GOOGL"],
    )._run_product_search()

    assert result["agents_enabled"] is True
    assert seen["yf_data"]["AAPL"]["source"] == "yfinance"


def test_smart_alternatives_do_not_repeat_placeholder_scores() -> None:
    from src.precompute import compute_smart_alternatives

    result = compute_smart_alternatives(
        ["AAPL", "MSFT", "GOOG"],
        {
            "AAPL": {"source": "estimated", "is_real": False},
            "MSFT": {"source": "estimated", "is_real": False},
            "GOOG": {"source": "estimated", "is_real": False},
        },
        {
            "per_ticker": {
                "AAPL": {"tox": 0.4},
                "MSFT": {"tox": 0.3},
                "GOOG": {"tox": 0.5},
            },
        },
    )

    assert result == []
