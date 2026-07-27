"""Single entry point for the complete Phoenix decision pipeline."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.data_module import fetch_ticker_data
from src.outcome_engine import StructuredNoteSpec, simulate_stress_suite
from src.precompute import precompute_all
from src.structured_product import find_best_structured_product


DEFAULT_PRODUCT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "JPM", "XOM",
]


def run_full_analysis(
    tickers: List[str],
    product_preferences: Optional[Dict[str, int | float]] = None,
) -> Dict:
    """Run data, scoring, agents, product selection, and stress in order."""
    preferences = product_preferences or {}
    target_barrier = preferences.get("barrier_pct")
    target_tenor = preferences.get("tenor_months")
    coupon_frequency = int(preferences.get("coupon_frequency_months", 3))
    basket = list(dict.fromkeys(tickers))
    data = precompute_all(basket)
    universe = list(dict.fromkeys(basket + DEFAULT_PRODUCT_UNIVERSE))
    market_data = fetch_ticker_data(universe, period="2y")
    evidence_gate = {
        "passed": all(
            market_data.get(ticker, {}).get("is_real") is True
            for ticker in universe
        ),
        "real_tickers": [
            ticker for ticker in universe
            if market_data.get(ticker, {}).get("is_real") is True
        ],
        "missing_tickers": [
            ticker for ticker in universe
            if market_data.get(ticker, {}).get("is_real") is not True
        ],
    }
    stages = {
        "market_data": "complete" if market_data else "unavailable",
        "phoenix": "complete",
        "agents": "enabled" if data.get("evidence_gate", {}).get("passed") else "diagnostic",
        "product": "pending",
        "outcomes": "pending",
    }
    real_universe = [
        ticker for ticker in universe
        if market_data.get(ticker, {}).get(
            "is_real",
            market_data.get(ticker, {}).get("source") in {"xfinlink", "yfinance"},
        )
        and market_data.get(ticker, {}).get("source")
        not in {"estimated", "fallback_defaults"}
    ]
    product = find_best_structured_product(
        real_universe,
        basket_size=3,
        yf_data=market_data,
        max_candidates=80,
        target_barrier_pct=target_barrier,
        target_tenor_months=target_tenor,
    )
    best = product.get("best", {})
    stages["product"] = "complete" if best else product.get("error", "blocked")
    stress = {}
    if best:
        spec = StructuredNoteSpec(
            basket=list(best["basket"]),
            barrier=float(best.get("barrier", 60)) / 100.0,
            coupon_rate=(
                float(best.get("coupon", 0.0)) / 100.0
                / (12.0 / max(coupon_frequency, 1))
            ),
            term_months=int(best.get("tenor_months", 24)),
        )
        stress = simulate_stress_suite(spec, n_paths=250)
        stages["outcomes"] = "stress_complete"
    else:
        stages["outcomes"] = "waiting_for_product"
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
        "market_data": market_data,
        "evidence_gate": evidence_gate,
        "product": product,
        "stress": stress,
        "stages": stages,
    }
