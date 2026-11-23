"""Isolated adapters for comparing Phoenix payoff semantics and references."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
from typing import Sequence

import numpy as np


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


def run_public_worst_of_challenger(
    repository_root: str,
    spots: Sequence[float],
    vols: Sequence[float],
    correlation: Sequence[Sequence[float]],
    terms: PhoenixTerms,
    rate: float = 0.0,
    maturity_years: float = 2.0,
    observations_per_year: int = 4,
    n_paths: int = 2_000,
    seed: int = 42,
) -> dict[str, float | int | str]:
    """Run the isolated public worst-of pricer through an explicit adapter.

    The repository is supplied by the caller and is never copied into Phoenix.
    This function is research-only and intentionally returns the external
    implementation's PV and standard error as separate evidence.
    """

    root = Path(repository_root)
    module_path = root / "worstof_pricer.py"
    if not module_path.exists():
        raise FileNotFoundError(f"public challenger not found: {module_path}")
    if len(spots) != len(vols):
        raise ValueError("spots and vols must have the same length")
    if len(spots) != len(correlation):
        raise ValueError("correlation dimension must match asset count")

    spec = importlib.util.spec_from_file_location(
        "phoenix_public_worstof_pricer",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load public challenger: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    assets = [
        module.Asset(f"asset_{index}", float(spot), float(vol), 0.0)
        for index, (spot, vol) in enumerate(zip(spots, vols))
    ]
    market = module.MultiMarket(
        assets=assets,
        rate=float(rate),
        corr=np.asarray(correlation, dtype=float),
    )
    product = module.WorstOfAutocallable(
        strikes=[float(spot) for spot in spots],
        notional=float(terms.notional),
        maturity_years=float(maturity_years),
        obs_per_year=int(observations_per_year),
        autocall_barrier=float(terms.autocall_barrier),
        coupon_barrier=float(terms.coupon_barrier),
        ki_barrier=float(terms.knock_in_barrier),
        coupon=float(terms.coupon),
    )
    pv, standard_error = module.price(
        market,
        product,
        n_paths=int(n_paths),
        seed=int(seed),
    )
    return {
        "source": "public_autocallable_pricer",
        "pv": float(pv),
        "standard_error": float(standard_error),
        "n_paths": int(n_paths),
        "seed": int(seed),
    }
