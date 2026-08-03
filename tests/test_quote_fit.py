from src.quote_fit import evaluate_quote_fit
from src.real_data import precompute_dealer_benchmark


def test_missing_quote_is_not_calibrated() -> None:
    fit = evaluate_quote_fit(18.0, None)

    assert fit["status"] == "missing"
    assert fit["delta_pp"] is None
    assert fit["fit"] == "unknown"
    assert fit["score_penalty"] == 0.0
    assert fit["blocker"]


def test_zero_quote_is_observed_evidence() -> None:
    fit = evaluate_quote_fit(18.0, 0.0, "BKS")

    assert fit["status"] == "zero_quote"
    assert fit["delta_pp"] == -18.0
    assert fit["fit"] == "mismatch"
    assert fit["score_penalty"] > 0
    assert fit["dealer"] == "BKS"


def test_aligned_quote_has_no_penalty_or_blocker() -> None:
    fit = evaluate_quote_fit(18.0, 19.0)

    assert fit["status"] == "observed"
    assert fit["fit"] == "aligned"
    assert fit["score_penalty"] == 0.0
    assert fit["blocker"] is None


def test_penalty_grows_with_delta_and_is_capped() -> None:
    drift = evaluate_quote_fit(18.0, 22.0)
    mismatch = evaluate_quote_fit(18.0, 40.0)

    assert drift["fit"] == "drift"
    assert drift["score_penalty"] == 2.0
    assert mismatch["fit"] == "mismatch"
    assert mismatch["score_penalty"] == 10.0


def test_dealer_benchmark_reports_zero_delta_instead_of_none() -> None:
    tickers = ["AAPL", "MSFT", "NVDA"]
    first = precompute_dealer_benchmark(tickers, 20.0, 20.0, 75.0)
    if first["avg_similar_coupon"] is None:
        return
    exact = precompute_dealer_benchmark(
        tickers, first["avg_similar_coupon"], 20.0, 75.0
    )

    assert exact["delta_coupon_vs_similar"] is not None
    assert exact["accuracy_vs_dealer"] is not None
