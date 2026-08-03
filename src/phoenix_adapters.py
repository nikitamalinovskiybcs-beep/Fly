"""Isolated adapters for comparing Phoenix payoff semantics and references."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class PhoenixTerms:
    """Contract terms used by a deterministic path-level payoff reference."""

    notional: float = 1.0
    coupon: float = 0.065
    coupon_barrier: float = 0.65
    autocall_barrier: float = 1.0
    knock_in_barrier: float = 0.65
    memory_coupon: bool = True


@dataclass(frozen=True)
class PayoffResult:
    """Auditable result for one realized performance path."""

    principal: float
    coupon_cashflows: tuple[float, ...]
    total_payoff: float
    worst_final: float
    autocalled_at: int | None
    knock_in: bool


def evaluate_worst_of_path(
    performances: Sequence[Sequence[float]],
    terms: PhoenixTerms,
) -> PayoffResult:
    """Evaluate a discrete worst-of Phoenix path.

    ``performances`` is asset-by-observation and must include the final
    observation. Coupon and autocall checks use the worst asset at each
    observation. This adapter is intentionally independent of the Monte Carlo
    engine and is used for fixture-level comparisons.
    """

    if not performances or not performances[0]:
        raise ValueError("performances must contain at least one observation")
    observation_count = len(performances[0])
    if any(len(asset) != observation_count for asset in performances):
        raise ValueError("all assets must have the same observation count")
    if terms.notional <= 0 or terms.coupon < 0:
        raise ValueError("notional must be positive and coupon non-negative")

    worst = tuple(
        min(asset[observation] for asset in performances)
        for observation in range(observation_count)
    )
    unpaid = 0
    coupons: list[float] = []
    autocalled_at: int | None = None

    for observation, level in enumerate(worst[:-1]):
        if level >= terms.coupon_barrier:
            paid_periods = unpaid + 1 if terms.memory_coupon else 1
            coupons.append(terms.notional * terms.coupon * paid_periods)
            unpaid = 0
        elif terms.memory_coupon:
            unpaid += 1
            coupons.append(0.0)
        else:
            coupons.append(0.0)

        if level >= terms.autocall_barrier:
            autocalled_at = observation
            principal = terms.notional
            return PayoffResult(
                principal=principal,
                coupon_cashflows=tuple(coupons),
                total_payoff=principal + sum(coupons),
                worst_final=level,
                autocalled_at=autocalled_at,
                knock_in=False,
            )

    worst_final = worst[-1]
    knock_in = worst_final < terms.knock_in_barrier
    principal = terms.notional * worst_final if knock_in else terms.notional
    if worst_final >= terms.coupon_barrier:
        paid_periods = unpaid + 1 if terms.memory_coupon else 1
        coupons.append(terms.notional * terms.coupon * paid_periods)
    else:
        coupons.append(0.0)

    return PayoffResult(
        principal=principal,
        coupon_cashflows=tuple(coupons),
        total_payoff=principal + sum(coupons),
        worst_final=worst_final,
        autocalled_at=autocalled_at,
        knock_in=knock_in,
    )


@dataclass(frozen=True)
class ChallengerStatus:
    """Availability and evidence status for an external challenger."""

    name: str
    repository: str
    license: str
    test_status: str
    integration_status: str
    evidence_class: str = "synthetic_research"


PUBLIC_CHALLENGERS: tuple[ChallengerStatus, ...] = (
    ChallengerStatus(
        name="autocallable-pricer",
        repository="https://github.com/ShrishDhuria/autocallable-pricer",
        license="MIT",
        test_status="10 passed in isolated checkout",
        integration_status="reference_only",
    ),
    ChallengerStatus(
        name="structured-products-analytics",
        repository="https://github.com/sanyalelizabet/structured-products-analytics",
        license="review_required",
        test_status="740 passed, 1 xfailed in isolated checkout",
        integration_status="reference_only",
    ),
)
