"""Research-only drift checks for Phoenix probabilities and BCS quotes."""

from __future__ import annotations

from statistics import mean
from typing import Iterable


def _mean(values: Iterable[float]) -> float | None:
    items = [float(value) for value in values]
    return mean(items) if items else None


def build_evidence_drift_report(
    *,
    reference_p_loss: Iterable[float],
    current_p_loss: Iterable[float],
    reference_bcs_coupon: Iterable[float],
    current_bcs_coupon: Iterable[float],
    p_loss_threshold: float = 0.10,
    coupon_threshold: float = 2.0,
) -> dict[str, object]:
    """Detect distribution shifts without recalibrating or mutating state."""
    ref_loss = _mean(reference_p_loss)
    cur_loss = _mean(current_p_loss)
    ref_coupon = _mean(reference_bcs_coupon)
    cur_coupon = _mean(current_bcs_coupon)
    shifts = {
        "p_loss": (
            None if ref_loss is None or cur_loss is None
            else round(cur_loss - ref_loss, 6)
        ),
        "bcs_coupon_pp": (
            None if ref_coupon is None or cur_coupon is None
            else round(cur_coupon - ref_coupon, 6)
        ),
    }
    alerts = []
    if shifts["p_loss"] is not None and abs(shifts["p_loss"]) > p_loss_threshold:
        alerts.append("p_loss_drift")
    if shifts["bcs_coupon_pp"] is not None and abs(shifts["bcs_coupon_pp"]) > coupon_threshold:
        alerts.append("bcs_coupon_drift")
    return {
        "status": "drift_detected" if alerts else "stable",
        "alerts": alerts,
        "shifts": shifts,
        "thresholds": {
            "p_loss": p_loss_threshold,
            "bcs_coupon_pp": coupon_threshold,
        },
        "action": "committee_review" if alerts else "monitor",
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
