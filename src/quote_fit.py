"""Quote-fit calibration between the model coupon and an observed dealer quote.

A dealer quote is calibration evidence, not a decision by itself. The caller must
pass ``None`` when no quote was received; ``0.0`` is a real observed quote (the
dealer priced the structure at a zero coupon) and is treated as evidence.
"""


ALIGNED_PP = 2.0
DRIFT_PP = 5.0


def evaluate_quote_fit(
    model_coupon_pa: float,
    quoted_coupon_pa: float | None,
    dealer: str = "",
) -> dict:
    """Compare the model coupon with an observed dealer quote.

    Returns a flat dict with the quote status, the signed delta in percentage
    points and a bounded score penalty for large model-vs-quote deltas.
    """
    model = float(model_coupon_pa)

    if quoted_coupon_pa is None:
        return {
            "status": "missing",
            "dealer": dealer,
            "model_coupon_pa": round(model, 2),
            "quoted_coupon_pa": None,
            "delta_pp": None,
            "fit": "unknown",
            "score_penalty": 0.0,
            "blocker": "no dealer quote observed; quote-fit not calibrated",
            "note": "Missing quote is not a zero quote; calibration is unavailable.",
        }

    quoted = float(quoted_coupon_pa)
    delta = quoted - model
    abs_delta = abs(delta)

    if abs_delta <= ALIGNED_PP:
        fit = "aligned"
    elif abs_delta <= DRIFT_PP:
        fit = "drift"
    else:
        fit = "mismatch"

    # Bounded penalty: nothing inside tolerance, then 1 point per pp, capped.
    score_penalty = round(min(10.0, max(0.0, abs_delta - ALIGNED_PP)), 2)

    if fit == "mismatch":
        direction = "underprices" if delta > 0 else "overprices"
        blocker = f"model {direction} coupon by {abs_delta:.1f}pp vs dealer quote"
    else:
        blocker = None

    return {
        "status": "zero_quote" if quoted == 0.0 else "observed",
        "dealer": dealer,
        "model_coupon_pa": round(model, 2),
        "quoted_coupon_pa": round(quoted, 2),
        "delta_pp": round(delta, 2),
        "fit": fit,
        "score_penalty": score_penalty,
        "blocker": blocker,
        "note": (
            "Dealer quoted a zero coupon; treated as observed evidence, not a "
            "missing quote."
            if quoted == 0.0
            else "Dealer quote observed and used as calibration evidence."
        ),
    }
