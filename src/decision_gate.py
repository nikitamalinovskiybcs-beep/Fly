"""Conservative decision gate for buyer-facing structured-product verdicts."""

from __future__ import annotations

from typing import Any, Mapping


def build_decision_gate(
    data: Mapping[str, Any],
    product: Mapping[str, Any],
    evidence_gate: Mapping[str, Any],
) -> dict[str, Any]:
    """Return one auditable verdict and its blocking reasons."""
    reasons: list[str] = []
    checks: dict[str, bool] = {}

    checks["real_market_data"] = bool(evidence_gate.get("passed"))
    if not checks["real_market_data"]:
        reasons.append("real_market_data_incomplete")

    best = product.get("best")
    checks["product_selected"] = isinstance(best, Mapping)
    if not checks["product_selected"]:
        reasons.append("no_product_selected")

    quote_fit = {}
    if isinstance(best, Mapping):
        candidate_quote_fit = best.get("dealer_quote_fit", best.get("quote_fit", {}))
        if isinstance(candidate_quote_fit, Mapping):
            quote_fit = dict(candidate_quote_fit)
    checks["dealer_quote_fit"] = bool(
        quote_fit.get("observed") or quote_fit.get("passed")
    )
    if not checks["dealer_quote_fit"]:
        reasons.append("dealer_quote_fit_missing")

    model_pki = float(data.get("p_ki", 0.0)) / 100.0
    empirical = data.get("empirical_pki", {})
    empirical_pki = (
        float(empirical.get("p_ki_empirical", -1.0)) / 100.0
        if isinstance(empirical, Mapping)
        else -1.0
    )
    pki_gap = abs(model_pki - empirical_pki) if empirical_pki >= 0 else None
    checks["pki_calibration"] = pki_gap is None or pki_gap <= 0.25
    if not checks["pki_calibration"]:
        reasons.append("model_empirical_pki_gap_above_25pct")

    recommendation = data.get("recommendation", {})
    action = recommendation.get("action") if isinstance(recommendation, Mapping) else ""
    score = float(data.get("score", 0.0))
    checks["model_action_consistent"] = action not in {"HOLD", "BLOCKED"} or score < 75
    if not checks["model_action_consistent"]:
        reasons.append("model_action_requires_wait")

    agent_report = data.get("sl_agents", {})
    disagreement = (
        float(agent_report.get("signal_disagreement", 0.0))
        if isinstance(agent_report, Mapping)
        else 0.0
    )
    checks["agent_agreement"] = disagreement <= 0.75
    if not checks["agent_agreement"]:
        reasons.append("agent_disagreement_high")

    if not checks["real_market_data"] or not checks["product_selected"]:
        verdict = "BAD"
    elif reasons:
        verdict = "CAUTION"
    else:
        verdict = "GOOD"

    return {
        "verdict": verdict,
        "passed": verdict == "GOOD",
        "reasons": reasons,
        "checks": checks,
        "pki_gap": round(pki_gap, 4) if pki_gap is not None else None,
        "what_to_check": [
            "obtain observed dealer quote and validate coupon/barrier/tenor",
            "reconcile model P(KI) with empirical settled-note outcomes",
            "confirm all agent features are non-default and fresh",
        ],
        "source": "decision_gate",
    }
