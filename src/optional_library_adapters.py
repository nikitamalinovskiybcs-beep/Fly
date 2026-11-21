"""Optional adapters for independent library sanity checks.

These adapters are challengers only. They do not alter the canonical Phoenix
engine or promote any library output to production evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import exp, sqrt


@dataclass(frozen=True)
class VanillaPriceComparison:
    """Common vanilla call fixture across optional libraries."""

    quantlib: float
    financepy: float
    vollib: float

    @property
    def max_abs_difference(self) -> float:
        values = (self.quantlib, self.financepy, self.vollib)
        return max(values) - min(values)


def quantlib_quarterly_dates(start: date, end: date) -> tuple[str, ...]:
    """Build an unadjusted quarterly schedule with QuantLib conventions."""

    import QuantLib as ql

    schedule = ql.Schedule(
        ql.Date(start.day, start.month, start.year),
        ql.Date(end.day, end.month, end.year),
        ql.Period(3, ql.Months),
        ql.NullCalendar(),
        ql.Unadjusted,
        ql.Unadjusted,
        ql.DateGeneration.Forward,
        False,
    )
    return tuple(
        f"{item.year():04d}-{item.month():02d}-{item.dayOfMonth():02d}"
        for item in schedule
    )


def compare_vanilla_call(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    volatility: float,
) -> VanillaPriceComparison:
    """Compare a simple European call across QuantLib, FinancePy and vollib."""

    import QuantLib as ql
    from financepy.models.black_scholes import BlackScholes
    from financepy.utils.global_types import OptionTypes
    from vollib.black_scholes import black_scholes

    forward = spot * exp(rate * time_to_expiry)
    discount = exp(-rate * time_to_expiry)
    quantlib_value = ql.BlackCalculator(
        ql.PlainVanillaPayoff(ql.Option.Call, strike),
        forward,
        volatility * sqrt(time_to_expiry),
        discount,
    ).value()
    financepy_value = BlackScholes(volatility).value(
        spot,
        time_to_expiry,
        strike,
        rate,
        0.0,
        OptionTypes.EUROPEAN_CALL,
    )
    vollib_value = black_scholes(
        "c",
        spot,
        strike,
        time_to_expiry,
        rate,
        volatility,
    )
    return VanillaPriceComparison(
        quantlib=float(quantlib_value),
        financepy=float(financepy_value),
        vollib=float(vollib_value),
    )


def optional_library_status() -> dict[str, str]:
    """Return import status without making optional dependencies mandatory."""

    libraries = {
        "QuantLib": "QuantLib",
        "FinancePy": "financepy",
        "vollib": "vollib",
        "finmath-lib": "finmath",
        "OpenGamma Strata": "com.opengamma.strata",
    }
    statuses: dict[str, str] = {}
    for name, module_name in libraries.items():
        try:
            __import__(module_name)
        except ImportError:
            statuses[name] = "unavailable"
        else:
            statuses[name] = "available"
    return statuses
