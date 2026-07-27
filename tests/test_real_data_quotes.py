from src.real_data import dealer_quote_summary


def test_dealer_quote_summary_reports_observed_sample() -> None:
    summary = dealer_quote_summary()

    assert summary["status"] == "observed"
    assert summary["total_quotes"] >= summary["valid_quotes"]
    assert summary["valid_quotes"] > 0
    assert summary["coupon_median"] is not None
