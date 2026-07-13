"""Best-structured-product optimizer.

Ties the rest of the system together toward the core goal: given a universe of
underlyings, find the single best structured product (basket + barrier + tenor)
by a risk-adjusted objective. Reuses the real, calibrated models:

- ``compute_toxicity`` / ``compute_p_loss`` (logistic model on 50 settled notes)
- ``predict_dealer_coupon`` (OLS on 828 dealer quotes)

and — when available — the 8-agent self-learning cascade to nudge the score.

Everything here is deterministic and network-free (yf_data is optional), so it
is fully unit-testable without hitting the market.
"""

from __future__ import annotations

import itertools
import logging
from typing import Dict, List, Optional

from src.real_data import compute_p_loss, compute_toxicity, predict_dealer_coupon

logger = logging.getLogger(__name__)

BARRIERS = [0.55, 0.60, 0.65, 0.70, 0.75]
TENORS = [12, 18, 24, 36]


def score_product(
    basket: List[str], barrier: float, tenor_months: int,
) -> Dict[str, float]:
    """Risk-adjusted score for one concrete product configuration.

    Objective = expected coupon carry net of loss probability and toxicity.
    Higher is better.
    """
    tox = compute_toxicity(basket)["avg_tox"]
    p_loss = compute_p_loss(basket, term_months=tenor_months)["p_loss"]
    coupon = predict_dealer_coupon(
        basket, term_months=tenor_months, prot_bar=barrier,
    )["predicted_coupon"]

    # Lower barrier → lower knock-in risk (protection deeper), scaled proxy.
    barrier_penalty = max(0.0, (barrier - 0.55)) * 12.0
    # Expected carry net of loss, minus toxicity and barrier risk penalties.
    objective = coupon * (1.0 - p_loss) - p_loss * 40.0 - tox * 8.0 - barrier_penalty

    return {
        "barrier": round(barrier * 100),
        "tenor_months": tenor_months,
        "coupon": round(coupon, 1),
        "p_loss_pct": round(p_loss * 100, 1),
        "avg_tox": round(tox, 3),
        "objective": round(objective, 2),
    }


def best_config_for_basket(basket: List[str]) -> Dict[str, float]:
    """Grid-search barrier × tenor for the best configuration of one basket."""
    best: Optional[Dict[str, float]] = None
    for barrier in BARRIERS:
        for tenor in TENORS:
            cfg = score_product(basket, barrier, tenor)
            if best is None or cfg["objective"] > best["objective"]:
                best = cfg
    return best or {}


def _agent_adjustment(basket: List[str], yf_data: Optional[Dict]) -> float:
    """Optional nudge from the 8-agent cascade (capped, safe on failure)."""
    if not yf_data:
        return 0.0
    try:
        from src.self_learning_agents import run_all_self_learning_agents
        res = run_all_self_learning_agents(
            tickers=basket, yf_data=yf_data, features={}, base_score=70.0,
        )
        if not res.get("guardian_ok", True):
            return 0.0
        return float(max(-5.0, min(5.0, res.get("total_adjustment", 0.0))))
    except Exception as exc:
        logger.info("Agent cascade skipped in product search: %s", exc)
        return 0.0


def find_best_structured_product(
    universe: List[str],
    basket_size: int = 3,
    yf_data: Optional[Dict] = None,
    max_candidates: int = 200,
    top_n: int = 5,
) -> Dict:
    """Search a universe for the best structured product.

    Args:
        universe: Candidate underlyings.
        basket_size: Number of underlyings per basket.
        yf_data: Optional live data dict enabling the agent cascade nudge.
        max_candidates: Cap on baskets evaluated (combinatorial guard).
        top_n: How many ranked products to return.

    Returns:
        Dict with the winning product and a ranked leaderboard.
    """
    universe = [t for t in dict.fromkeys(universe) if t]  # dedupe, keep order
    if len(universe) < basket_size:
        return {"error": "universe_too_small", "n": len(universe)}

    combos = list(itertools.combinations(universe, basket_size))
    if len(combos) > max_candidates:
        combos = combos[:max_candidates]

    ranked: List[Dict] = []
    for combo in combos:
        basket = list(combo)
        cfg = best_config_for_basket(basket)
        if not cfg:
            continue
        adj = _agent_adjustment(basket, yf_data)
        cfg = dict(cfg)
        cfg["basket"] = basket
        cfg["agent_adjustment"] = round(adj, 2)
        cfg["final_objective"] = round(cfg["objective"] + adj, 2)
        ranked.append(cfg)

    if not ranked:
        return {"error": "no_valid_products"}

    ranked.sort(key=lambda c: c["final_objective"], reverse=True)
    best = ranked[0]

    return {
        "best": best,
        "leaderboard": ranked[:top_n],
        "n_evaluated": len(ranked),
        "recommendation": (
            f"Лучший продукт: {' / '.join(best['basket'])} · "
            f"барьер {best['barrier']}% · срок {best['tenor_months']}мес · "
            f"купон ~{best['coupon']:.0f}% · P(loss) {best['p_loss_pct']:.0f}%"
        ),
    }
