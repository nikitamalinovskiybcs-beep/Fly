"""Regression tests for honest fallbacks and synthetic-data provenance."""

import numpy as np


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
