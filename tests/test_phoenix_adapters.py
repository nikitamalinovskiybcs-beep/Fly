import pytest

from src.phoenix_adapters import PhoenixTerms, evaluate_worst_of_path


def test_memory_coupon_and_worst_of_principal():
    terms = PhoenixTerms(
        notional=100.0,
        coupon=0.05,
        coupon_barrier=0.7,
        autocall_barrier=1.0,
        knock_in_barrier=0.6,
    )
    result = evaluate_worst_of_path(
        [
            [0.65, 0.75, 0.55],
            [0.9, 0.8, 0.8],
        ],
        terms,
    )

    assert result.coupon_cashflows == (0.0, 10.0, 0.0)
    assert result.principal == pytest.approx(55.0)
    assert result.knock_in is True
    assert result.autocalled_at is None
    assert result.total_payoff == pytest.approx(65.0)


def test_autocall_terminates_path_at_observation():
    terms = PhoenixTerms(
        notional=100.0,
        coupon=0.05,
        coupon_barrier=0.7,
        autocall_barrier=1.0,
        knock_in_barrier=0.6,
    )
    result = evaluate_worst_of_path(
        [
            [0.8, 1.05, 0.2],
            [0.9, 1.1, 0.2],
        ],
        terms,
    )

    assert result.autocalled_at == 1
    assert result.principal == pytest.approx(100.0)
    assert result.total_payoff == pytest.approx(110.0)
    assert result.knock_in is False


def test_rejects_ragged_paths():
    with pytest.raises(ValueError, match="same observation count"):
        evaluate_worst_of_path([[1.0, 1.0], [1.0]], PhoenixTerms())
