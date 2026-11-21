"""Common benchmark harness for Phoenix and independent references."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np

from src.optional_library_adapters import (
    compare_vanilla_call,
    quantlib_quarterly_dates,
)
from src.phoenix_adapters import (
    PhoenixTerms,
    evaluate_worst_of_path,
    run_public_worst_of_challenger,
)
from src.phoenix_engine import (
    GDRIVE_PATH,
    _cache_key,
    simulate_basket,
)


def _synthetic_prices(seed: int = 42, length: int = 600) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    return {
        ticker: 100.0
        * np.exp(np.cumsum(rng.normal(0.0002, volatility, length)))
        for ticker, volatility in (("FIX_A", 0.01), ("FIX_B", 0.015))
    }


def run_universal_benchmark(
    public_repository_root: str,
    public_path_counts: tuple[int, ...] = (1_000, 2_000, 4_000),
) -> dict[str, object]:
    """Run shared payoff, pricing, schedule and convergence checks."""

    terms = PhoenixTerms()
    fixture_path = evaluate_worst_of_path(
        [[0.80, 0.95, 0.55], [0.90, 0.85, 0.70]],
        terms,
    )

    basket = ["FIX_A", "FIX_B"]
    cache_path = Path(GDRIVE_PATH) / f"cache_{_cache_key(basket)}.json"
    cache_path.unlink(missing_ok=True)
    canonical = simulate_basket(
        basket,
        {
            "n_sims": 2_000,
            "horizon_days": 504,
            "obs_days": [63, 126, 189, 252, 315, 378, 441, 504],
        },
        _synthetic_prices(),
    )
    if canonical is None:
        raise RuntimeError("canonical Phoenix fixture did not produce a result")

    public_runs = [
        run_public_worst_of_challenger(
            public_repository_root,
            spots=[100.0, 100.0],
            vols=[0.20, 0.25],
            correlation=[[1.0, 0.40], [0.40, 1.0]],
            terms=terms,
            n_paths=path_count,
            observations_per_year=4,
        )
        for path_count in public_path_counts
    ]
    public_pvs = [float(run["pv"]) for run in public_runs]
    convergence_range = max(public_pvs) - min(public_pvs)
    vanilla = compare_vanilla_call(100.0, 100.0, 1.0, 0.05, 0.20)
    schedule = quantlib_quarterly_dates(date(2025, 3, 24), date(2026, 3, 24))

    return {
        "benchmark_id": "phoenix-universal-benchmark-v1",
        "status": "research_only",
        "fixture": {
            "path_level": {
                "principal": fixture_path.principal,
                "coupon_cashflows": fixture_path.coupon_cashflows,
                "total_payoff": fixture_path.total_payoff,
                "autocalled_at": fixture_path.autocalled_at,
                "knock_in": fixture_path.knock_in,
            },
            "terms": terms.__dict__,
        },
        "canonical_phoenix": {
            "avg_payoff": float(canonical["avg_payoff"]),
            "p_loss": float(canonical["p_loss"]),
            "n_sims": int(canonical["n_sims"]),
        },
        "public_challenger": {
            "runs": public_runs,
            "pv_range_across_path_counts": convergence_range,
        },
        "optional_library_reference": {
            "vanilla_call": {
                "QuantLib": vanilla.quantlib,
                "FinancePy": vanilla.financepy,
                "vollib": vanilla.vollib,
                "max_abs_difference": vanilla.max_abs_difference,
            },
            "quarterly_schedule": schedule,
        },
        "gates": {
            "path_fixture_completed": True,
            "canonical_completed": True,
            "public_challenger_completed": True,
            "vanilla_parity_under_1e-4": vanilla.max_abs_difference < 1e-4,
            "oos_accuracy": None,
            "verified_outcome_comparison": None,
            "production_promotion": False,
        },
        "safety_flags": {
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
        },
    }
