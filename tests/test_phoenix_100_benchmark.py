from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from src.optional_library_adapters import quantlib_quarterly_dates
from src.phoenix_adapters import PhoenixTerms, evaluate_worst_of_path


def _oracle(
    performances: list[list[float]],
    terms: PhoenixTerms,
) -> tuple[float, tuple[float, ...], int | None, bool]:
    worst = [
        min(asset[observation] for asset in performances)
        for observation in range(len(performances[0]))
    ]
    coupons: list[float] = []
    missed = 0
    for observation, level in enumerate(worst[:-1]):
        if level >= terms.coupon_barrier:
            coupons.append(terms.notional * terms.coupon * (missed + 1))
            missed = 0
        else:
            coupons.append(0.0)
            missed += 1
        if level >= terms.autocall_barrier:
            return terms.notional, tuple(coupons), observation, False
    final = worst[-1]
    if final >= terms.coupon_barrier:
        coupons.append(terms.notional * terms.coupon * (missed + 1))
    else:
        coupons.append(0.0)
    knock_in = final < terms.knock_in_barrier
    principal = terms.notional * final if knock_in else terms.notional
    return principal, tuple(coupons), None, knock_in


def _valid_cases() -> list[tuple[str, str, object]]:
    cases: list[tuple[str, str, object]] = []
    terms = PhoenixTerms()
    for index in range(20):
        final = 0.50 + index * 0.025
        path = [[0.72, 0.82, final], [0.88, 0.76, 0.90]]
        cases.append((f"payoff-{index:02d}", "valid", (path, terms)))
    for index in range(15):
        missed = index % 4
        first = [0.60] * missed + [0.75, 0.80]
        path = [first, [0.90] * len(first)]
        cases.append((f"memory-{index:02d}", "valid", (path, terms)))
    for index in range(15):
        trigger = index % 3
        levels = [0.80, 0.80, 0.80]
        levels[trigger] = 1.05
        path = [levels, [0.90, 0.90, 0.90]]
        cases.append((f"autocall-{index:02d}", "valid", (path, terms)))
    for index in range(15):
        final = 0.40 + index * 0.04
        path = [[0.75, 0.75, final], [0.90, 0.90, 0.95]]
        cases.append((f"knock-in-{index:02d}", "valid", (path, terms)))
    for index in range(10):
        weak_asset = 0.50 + index * 0.04
        path = [[0.90, 0.90, 0.90], [0.80, 0.80, weak_asset]]
        cases.append((f"worst-of-{index:02d}", "valid", (path, terms)))
    return cases


def _invalid_cases() -> list[tuple[str, str, object]]:
    terms = PhoenixTerms()
    return [
        (f"stress-{index:02d}", "invalid", payload)
        for index, payload in enumerate(
            [
                ([], terms),
                ([[1.0], [1.0, 1.0]], terms),
                ([[1.0, 1.0]], replace(terms, notional=0.0)),
                ([[1.0, 1.0]], replace(terms, coupon=-0.01)),
                ([[1.0, 1.0]], replace(terms, notional=-1.0)),
                ([[1.0, 1.0]], replace(terms, notional=0.0)),
                ([], replace(terms, notional=-1.0)),
                ([[1.0, 1.0], [1.0]], terms),
                ([[1.0]], replace(terms, coupon=-1.0)),
                ([], replace(terms, coupon=-1.0)),
            ]
        )
    ]


SCENARIOS = _valid_cases() + _invalid_cases()
SCENARIOS += [
    (f"date-{index:02d}", "date", index + 1)
    for index in range(10)
]
SCENARIOS += [
    (f"safety-{index:02d}", "safety", index)
    for index in range(5)
]
assert len(SCENARIOS) == 100


@pytest.mark.parametrize("case_id, family, payload", SCENARIOS, ids=[case[0] for case in SCENARIOS])
def test_mistral_assisted_100_case_benchmark(case_id, family, payload):
    if family == "valid":
        performances, terms = payload
        expected_principal, expected_coupons, expected_autocall, expected_ki = _oracle(
            performances, terms
        )
        result = evaluate_worst_of_path(performances, terms)
        assert result.principal == pytest.approx(expected_principal), case_id
        assert result.coupon_cashflows == pytest.approx(expected_coupons), case_id
        assert result.autocalled_at == expected_autocall, case_id
        assert result.knock_in is expected_ki, case_id
    elif family == "invalid":
        performances, terms = payload
        with pytest.raises(ValueError):
            evaluate_worst_of_path(performances, terms)
    elif family == "date":
        years = payload
        schedule = quantlib_quarterly_dates(
            date(2025, 3, 24),
            date(2025 + years, 3, 24),
        )
        assert schedule[0] == "2025-03-24", case_id
        assert schedule[-1] == f"{2025 + years:04d}-03-24", case_id
        assert len(schedule) == years * 4 + 1, case_id
    else:
        assert {
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
        }["production_weights_changed"] is False
