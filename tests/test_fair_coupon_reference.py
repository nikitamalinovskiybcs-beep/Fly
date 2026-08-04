import numpy as np
import pytest

from src.fair_coupon_reference import (
    FairCouponTerms,
    estimate_fair_coupon,
    simulate_correlated_gbm,
)


def _terms() -> FairCouponTerms:
    return FairCouponTerms(
        notional=100.0,
        maturity_years=1.0,
        observations_per_year=2,
        autocall_barriers=(1.0, 1.0),
        coupon_barriers=(0.7, 0.7),
        knock_in_barrier=0.6,
        risk_free_rate=0.03,
        issuer_spread=0.01,
    )


def test_pathwise_fair_coupon_decomposition():
    paths = np.array(
        [
            [[0.8, 0.9], [0.8, 0.9]],
            [[0.8, 0.9], [0.5, 0.9]],
        ]
    )
    result = estimate_fair_coupon(paths, _terms())

    assert result.principal_pv > 0
    assert result.coupon_annuity_pv > 0
    assert result.fair_coupon > 0
    assert result.n_paths == 2


def test_correlated_gbm_is_reproducible():
    kwargs = {
        "spots": np.array([100.0, 100.0]),
        "vols": np.array([0.2, 0.25]),
        "dividends": np.array([0.01, 0.02]),
        "correlation": np.array([[1.0, 0.4], [0.4, 1.0]]),
        "rate": 0.03,
        "maturity_years": 1.0,
        "observations_per_year": 2,
        "n_paths": 100,
        "seed": 42,
    }
    assert np.array_equal(simulate_correlated_gbm(**kwargs), simulate_correlated_gbm(**kwargs))


def test_rejects_zero_annuity():
    paths = np.ones((2, 1, 2))
    terms = FairCouponTerms(
        notional=100.0,
        maturity_years=0.5,
        observations_per_year=2,
        autocall_barriers=(2.0,),
        coupon_barriers=(2.0,),
        knock_in_barrier=0.6,
        risk_free_rate=0.03,
        issuer_spread=0.01,
    )
    with pytest.raises(ValueError, match="annuity"):
        estimate_fair_coupon(paths, terms)
