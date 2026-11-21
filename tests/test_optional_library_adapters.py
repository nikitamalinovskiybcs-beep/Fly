from datetime import date

import pytest

from src.optional_library_adapters import (
    compare_vanilla_call,
    optional_library_status,
    quantlib_quarterly_dates,
)


def test_optional_library_status_is_explicit():
    status = optional_library_status()
    assert status["QuantLib"] == "available"
    assert status["FinancePy"] == "available"
    assert status["vollib"] == "available"
    assert status["finmath-lib"] in {"available", "unavailable"}
    assert status["OpenGamma Strata"] in {"available", "unavailable"}


def test_quantlib_schedule_is_quarterly():
    assert quantlib_quarterly_dates(date(2025, 3, 24), date(2026, 3, 24)) == (
        "2025-03-24",
        "2025-06-24",
        "2025-09-24",
        "2025-12-24",
        "2026-03-24",
    )


def test_vanilla_call_challengers_agree():
    result = compare_vanilla_call(
        spot=100.0,
        strike=100.0,
        time_to_expiry=1.0,
        rate=0.05,
        volatility=0.2,
    )

    assert result.max_abs_difference < 1e-5
    assert result.quantlib == pytest.approx(10.4506, abs=1e-3)
