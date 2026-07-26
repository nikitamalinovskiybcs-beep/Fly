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


def _split_objectives(cfg: Dict[str, float]) -> Dict[str, float]:
    """Stress-split one model output to detect fragile recommendations.

    This is a deterministic model-split guard, not a claim of live
    out-of-sample performance. Real settled-note outcomes can replace these
    assumptions when they accumulate.
    """
    scenarios = {
        "train": (1.00, 0.00, 0.00),
        "validation": (0.97, 0.015, 0.005),
        "test": (0.92, 0.035, 0.010),
    }
    values = {}
    for name, (coupon_factor, loss_shift, tox_shift) in scenarios.items():
        coupon = cfg["coupon"] * coupon_factor
        loss = min(1.0, cfg["p_loss_pct"] / 100.0 + loss_shift)
        toxicity = min(1.0, cfg["avg_tox"] + tox_shift)
        values[name] = round(
            coupon * (1.0 - loss)
            - loss * 40.0
            - toxicity * 8.0
            - max(0.0, (cfg["barrier"] / 100.0 - 0.55)) * 12.0,
            2,
        )
    return values


def _baseline_comparison(
    universe: List[str],
    basket_size: int,
    best: Dict[str, float],
    yf_data: Optional[Dict] = None,
) -> Dict:
    """Compare the selected product against transparent no-agent baselines."""
    baseline_basket = universe[:basket_size]
    baseline = best_config_for_basket(baseline_basket, yf_data=yf_data)
    no_agent = float(best["objective"])
    return {
        "baseline_basket": baseline_basket,
        "baseline_objective": round(float(baseline.get("objective", 0.0)), 2),
        "selected_vs_baseline": round(
            float(best["final_objective"]) - float(baseline.get("objective", 0.0)),
            2,
        ),
        "agent_lift": round(float(best["agent_adjustment"]), 2),
        "no_agent_objective": round(no_agent, 2),
    }


def _market_adjustment(
    basket: List[str], yf_data: Optional[Dict],
) -> Dict[str, float]:
    """Translate observed market risk into an auditable objective adjustment."""
    if not yf_data or any(
        not yf_data.get(t)
        or (
            yf_data[t].get("is_real") is False
            and yf_data[t].get("source") not in {"xfinlink", "yfinance"}
        )
        or yf_data[t].get("source") in {"estimated", "fallback_defaults"}
        for t in basket
    ):
        return {
            "market_iv": 0.0,
            "market_beta": 0.0,
            "market_trend": 0.0,
            "market_adjustment": 0.0,
        }

    infos = [yf_data[t] for t in basket]
    avg_iv = sum(float(info.get("iv30", 30.0)) for info in infos) / len(infos)
    avg_beta = sum(float(info.get("beta", 1.0)) for info in infos) / len(infos)
    avg_trend = sum(float(info.get("ema200_pct", 0.0)) for info in infos) / len(infos)
    vol_penalty = max(0.0, avg_iv - 30.0) * 0.15
    beta_penalty = max(0.0, avg_beta - 1.0) * 2.0
    trend_bonus = max(-2.0, min(2.0, avg_trend * 0.05))
    return {
        "market_iv": round(avg_iv, 1),
        "market_beta": round(avg_beta, 2),
        "market_trend": round(avg_trend, 1),
        "market_adjustment": round(trend_bonus - vol_penalty - beta_penalty, 2),
    }


def score_product(
    basket: List[str], barrier: float, tenor_months: int,
    yf_data: Optional[Dict] = None,
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
    market = _market_adjustment(basket, yf_data)
    objective += market["market_adjustment"]

    return {
        "barrier": round(barrier * 100),
        "tenor_months": tenor_months,
        "coupon": round(coupon, 1),
        "p_loss_pct": round(p_loss * 100, 1),
        "avg_tox": round(tox, 3),
        **market,
        "objective": round(objective, 2),
    }


def best_config_for_basket(
    basket: List[str], yf_data: Optional[Dict] = None,
) -> Dict[str, float]:
    """Grid-search barrier × tenor for the best configuration of one basket."""
    best: Optional[Dict[str, float]] = None
    for barrier in BARRIERS:
        for tenor in TENORS:
            cfg = score_product(basket, barrier, tenor, yf_data=yf_data)
            if best is None or cfg["objective"] > best["objective"]:
                best = cfg
    return best or {}


def _agent_adjustment(basket: List[str], yf_data: Optional[Dict]) -> float:
    """Optional nudge from the 8-agent cascade (capped, safe on failure)."""
    return _agent_report(basket, yf_data).get("total_adjustment", 0.0)


def _agent_features(basket: List[str], yf_data: Dict) -> Dict[str, float]:
    """Build the small feature vector consumed by the alpha agent."""
    infos = [yf_data.get(t, {}) for t in basket]
    if not infos:
        return {}

    pe_values = [
        float(info.get("pe", 30.0))
        for info in infos
        if isinstance(info.get("pe", 30.0), (int, float))
    ]
    avg_pe = sum(pe_values) / len(pe_values) if pe_values else 30.0
    avg_iv = sum(float(info.get("iv30", 30.0)) for info in infos) / len(infos)
    avg_hist_vol = sum(
        float(info.get("hist_vol", info.get("real_1y", 25.0)))
        for info in infos
    ) / len(infos)
    avg_return = sum(float(info.get("return_1m", 0.0)) for info in infos) / len(infos)
    sectors = [info.get("sector", "") for info in infos]
    same_sector = sum(
        1 for i in range(len(sectors)) for j in range(i + 1, len(sectors))
        if sectors[i] and sectors[i] == sectors[j]
    )
    pair_count = max(1, len(infos) * (len(infos) - 1) // 2)

    return {
        "tox_norm": sum(
            float(info.get("toxicity", info.get("tox_norm", 0.5)))
            for info in infos
        ) / len(infos),
        "fund_norm": max(0.0, min(1.0, 1.0 / (1.0 + avg_pe / 30.0))),
        "vol_norm": max(0.0, min(1.0, avg_iv / 60.0)),
        "macro_norm": max(0.0, min(1.0, 0.5 + avg_return * 2.0)),
        "corr_norm": max(0.0, min(1.0, same_sector / pair_count)),
        "pki_norm": max(0.0, min(1.0, 0.5 + avg_return)),
        "hist_vol_norm": max(0.0, min(1.0, avg_hist_vol / 60.0)),
    }


def _agent_report(basket: List[str], yf_data: Optional[Dict]) -> Dict:
    """Run agents with non-empty features and return auditable contributions."""
    if not yf_data:
        return {"total_adjustment": 0.0, "agents_with_signal": []}
    try:
        from src.self_learning_agents import run_all_self_learning_agents
        res = run_all_self_learning_agents(
            tickers=basket,
            yf_data=yf_data,
            features=_agent_features(basket, yf_data),
            base_score=70.0,
        )
        if not res.get("guardian_ok", True):
            return {
                "total_adjustment": 0.0,
                "agents_with_signal": res.get("agents_with_signal", []),
                "agent_contributions": res.get("agent_contributions", {}),
                "confidence": res.get("confidence", 0.5),
                "degraded": True,
            }
        return {
            "total_adjustment": float(
                max(-5.0, min(5.0, res.get("total_adjustment", 0.0)))
            ),
            "agents_with_signal": res.get("agents_with_signal", []),
            "agent_contributions": res.get("agent_contributions", {}),
            "confidence": res.get("confidence", 0.5),
        }
    except Exception as exc:
        logger.info("Agent cascade skipped in product search: %s", exc)
        return {"total_adjustment": 0.0, "agents_with_signal": []}


def find_best_structured_product(
    universe: List[str],
    basket_size: int = 3,
    yf_data: Optional[Dict] = None,
    max_candidates: int = 200,
    top_n: int = 5,
    require_real_data: bool = False,
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

    if require_real_data:
        universe = [
            ticker for ticker in universe
            if yf_data
            and yf_data.get(ticker, {}).get(
                "is_real",
                yf_data.get(ticker, {}).get("source") in {"xfinlink", "yfinance"},
            )
            and yf_data.get(ticker, {}).get("source") not in {"estimated", "fallback_defaults"}
        ]
        if len(universe) < basket_size:
            return {
                "error": "insufficient_real_market_data",
                "available_real_tickers": len(universe),
                "required_tickers": basket_size,
            }

    combos = list(itertools.combinations(universe, basket_size))
    if len(combos) > max_candidates:
        combos = combos[:max_candidates]

    ranked: List[Dict] = []
    for combo in combos:
        basket = list(combo)
        cfg = best_config_for_basket(basket, yf_data=yf_data)
        if not cfg:
            continue
        agent_report = _agent_report(basket, yf_data)
        adj = float(agent_report.get("total_adjustment", 0.0))
        cfg = dict(cfg)
        cfg["basket"] = basket
        cfg["agent_adjustment"] = round(adj, 2)
        cfg["agents_with_signal"] = agent_report.get("agents_with_signal", [])
        cfg["agent_contributions"] = agent_report.get("agent_contributions", {})
        cfg["agent_confidence"] = round(
            float(agent_report.get("confidence", 0.5)), 2
        )
        cfg["split_objectives"] = _split_objectives(cfg)
        cfg["worst_split_objective"] = min(cfg["split_objectives"].values())
        cfg["final_objective"] = round(
            min(cfg["objective"] + adj, cfg["worst_split_objective"] + adj),
            2,
        )
        ranked.append(cfg)

    if not ranked:
        return {"error": "no_valid_products"}

    ranked.sort(key=lambda c: c["final_objective"], reverse=True)
    best = ranked[0]

    return {
        "best": best,
        "leaderboard": ranked[:top_n],
        "n_evaluated": len(ranked),
        "baseline_comparison": _baseline_comparison(
            universe, basket_size, best, yf_data=yf_data,
        ),
        "selection_method": "min(train, validation, test model splits)",
        "recommendation": (
            f"Лучший продукт: {' / '.join(best['basket'])} · "
            f"барьер {best['barrier']}% · срок {best['tenor_months']}мес · "
            f"купон ~{best['coupon']:.0f}% · P(loss) {best['p_loss_pct']:.0f}%"
        ),
    }
