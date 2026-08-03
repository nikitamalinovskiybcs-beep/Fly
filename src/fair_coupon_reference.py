"""Independent pathwise fair-coupon reference for research benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np


@dataclass(frozen=True)
class FairCouponTerms:
    notional: float
    maturity_years: float
    observations_per_year: int
    autocall_barriers: tuple[float, ...]
    coupon_barriers: tuple[float, ...]
    knock_in_barrier: float
    risk_free_rate: float
    issuer_spread: float
    memory_coupon: bool = True


@dataclass(frozen=True)
class FairCouponEstimate:
    fair_coupon: float
    principal_pv: float
    coupon_annuity_pv: float
    standard_error: float
    n_paths: int


def simulate_correlated_gbm(
    spots: np.ndarray,
    vols: np.ndarray,
    dividends: np.ndarray,
    correlation: np.ndarray,
    rate: float,
    maturity_years: float,
    observations_per_year: int,
    n_paths: int,
    seed: int,
) -> np.ndarray:
    """Return normalized paths with shape (paths, observations, assets)."""

    if n_paths <= 0 or observations_per_year <= 0:
        raise ValueError("path count and observations_per_year must be positive")
    assets = len(spots)
    if len(vols) != assets or len(dividends) != assets:
        raise ValueError("asset inputs must have equal lengths")
    if correlation.shape != (assets, assets):
        raise ValueError("correlation shape must match asset count")
    chol = np.linalg.cholesky(correlation)
    observations = int(maturity_years * observations_per_year)
    dt = 1.0 / observations_per_year
    rng = np.random.default_rng(seed)
    shocks = rng.standard_normal((n_paths, observations, assets))
    correlated = shocks @ chol.T
    drift = (rate - dividends - 0.5 * vols**2) * dt
    increments = drift + vols * sqrt(dt) * correlated
    return np.exp(np.cumsum(increments, axis=1))


def decompose_path_cashflows(
    normalized_paths: np.ndarray,
    terms: FairCouponTerms,
) -> tuple[np.ndarray, np.ndarray]:
    """Return discounted principal and coupon annuity for every path."""

    if normalized_paths.ndim != 3:
        raise ValueError("normalized_paths must be three-dimensional")
    observations = normalized_paths.shape[1]
    if len(terms.autocall_barriers) != observations:
        raise ValueError("autocall barrier schedule length mismatch")
    if len(terms.coupon_barriers) != observations:
        raise ValueError("coupon barrier schedule length mismatch")

    worst = normalized_paths.min(axis=2)
    discount_rate = terms.risk_free_rate + terms.issuer_spread
    dt = 1.0 / terms.observations_per_year
    principal = np.zeros(len(normalized_paths))
    annuity = np.zeros(len(normalized_paths))
    alive = np.ones(len(normalized_paths), dtype=bool)
    missed = np.zeros(len(normalized_paths), dtype=int)

    for index in range(observations):
        discount = np.exp(-discount_rate * (index + 1) * dt)
        level = worst[:, index]
        paid = alive & (level >= terms.coupon_barriers[index])
        annuity[paid] += (missed[paid] + 1) * discount
        missed[paid] = 0
        missed[alive & ~paid] += 1

        called = alive & (level >= terms.autocall_barriers[index])
        principal[called] = terms.notional * discount
        alive[called] = False

    final = worst[:, -1]
    final_discount = np.exp(-discount_rate * terms.maturity_years)
    principal[alive] = np.where(
        final[alive] < terms.knock_in_barrier,
        terms.notional * final[alive] * final_discount,
        terms.notional * final_discount,
    )
    return principal, annuity


def estimate_fair_coupon(
    normalized_paths: np.ndarray,
    terms: FairCouponTerms,
) -> FairCouponEstimate:
    """Solve fair coupon analytically from pathwise PV decomposition."""

    principal, annuity = decompose_path_cashflows(normalized_paths, terms)
    mean_principal = float(principal.mean())
    mean_annuity = float(annuity.mean())
    if mean_annuity <= 0:
        raise ValueError("coupon annuity is zero; fair coupon is undefined")
    fair_coupon = (terms.notional - mean_principal) / mean_annuity
    residual = principal + fair_coupon * annuity - terms.notional
    standard_error = float(
        residual.std(ddof=1) / (sqrt(len(residual)) * mean_annuity)
    )
    return FairCouponEstimate(
        fair_coupon=fair_coupon,
        principal_pv=mean_principal,
        coupon_annuity_pv=mean_annuity,
        standard_error=standard_error,
        n_paths=len(normalized_paths),
    )
