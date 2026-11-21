"""Evidence summaries for fixed-24m research candidates and BCS quotes."""

from __future__ import annotations

from typing import Mapping


def build_fixed_24m_evidence_report(
    *,
    anchors: Mapping[str, Mapping[str, float]],
    bcs_quote: Mapping[str, float] | None = None,
) -> dict[str, object]:
    """Summarize anchor metrics and dealer quote-fit without promotion."""
    anchor_rows = []
    for name, metrics in sorted(anchors.items(), key=lambda item: int(item[0])):
        anchor_rows.append({
            "anchor_months": int(name),
            "model_brier": metrics.get("model_brier"),
            "baseline_brier": metrics.get("baseline_brier"),
            "model_log_loss": metrics.get("model_log_loss"),
            "baseline_log_loss": metrics.get("baseline_log_loss"),
            "model_ece": metrics.get("model_ece"),
            "baseline_ece": metrics.get("baseline_ece"),
            "beats_brier": (
                metrics.get("model_brier") is not None
                and metrics.get("baseline_brier") is not None
                and metrics["model_brier"] <= metrics["baseline_brier"]
            ),
        })
    quote_fit = None
    if bcs_quote:
        observed = float(bcs_quote["coupon_pa"])
        model = float(bcs_quote["model_coupon_pa"])
        delta = observed - model
        quote_fit = {
            "dealer": "BCS Capital",
            "observed_coupon_pa": observed,
            "model_coupon_pa": model,
            "delta_pp": round(delta, 6),
            "fit": abs(delta) <= float(bcs_quote.get("tolerance_pp", 2.0)),
            "evidence_only": True,
        }
    return {
        "status": "research_only",
        "anchor_count": len(anchor_rows),
        "anchors": anchor_rows,
        "bcs_quote_fit": quote_fit,
        "promotion_gate": all(row["beats_brier"] for row in anchor_rows)
        and bool(anchor_rows),
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
