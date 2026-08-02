"""Run a 100-basket historical benchmark across multiple note horizons."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.replay_80_baskets import DEFAULT_UNIVERSE, _download_prices, _build_baskets
from src.outcome_engine import StructuredNoteSpec, replay_historical_windows
from src.real_data import compute_p_loss
from src.replay_calibration import apply_histogram_calibrator, fit_histogram_calibrator


EXTRA_UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLI", "XLP",
    "XLY", "XLB", "XLU", "ARKK", "EEM", "EFA", "TLT", "GLD", "SLV", "VNQ",
]
ANCHOR_MONTHS = (6, 12, 18, 24)


def _metrics(predicted: list[float], observed: list[float]) -> dict[str, float | None]:
    if not observed:
        return {"brier": None, "mean_predicted_loss": None, "mean_observed_loss": None}
    p = np.asarray(predicted, dtype=float)
    y = np.asarray(observed, dtype=float)
    baseline = float(np.mean(y))
    brier = float(np.mean((p - y) ** 2))
    baseline_brier = float(np.mean((baseline - y) ** 2))
    return {
        "brier": round(brier, 6),
        "empirical_baseline_brier": round(baseline_brier, 6),
        "brier_vs_baseline_pct": round(
            (baseline_brier - brier) / baseline_brier * 100, 2,
        ) if baseline_brier else None,
        "mean_predicted_loss": round(float(np.mean(p)), 6),
        "mean_observed_loss": round(float(np.mean(y)), 6),
    }


def build_multi_horizon_report(
    prices: dict[str, list[float]],
    baskets: list[list[str]],
) -> dict:
    anchors: dict[str, dict] = {}
    for months_ago in ANCHOR_MONTHS:
        forward_days = months_ago * 21
        predictions: list[float] = []
        calibrated_predictions: list[float] = []
        observed: list[float] = []
        rows: list[dict] = []
        calibration_predictions: list[float] = []
        calibration_outcomes: list[int] = []
        for basket in baskets:
            if any(len(prices.get(ticker, [])) < forward_days for ticker in basket):
                continue
            forward = {ticker: prices[ticker][-forward_days:] for ticker in basket}
            prediction = float(compute_p_loss(basket, term_months=months_ago)["p_loss"])
            if prediction > 1:
                prediction /= 100
            historical = {
                ticker: prices[ticker][:-forward_days]
                for ticker in basket
            }
            train_replay = replay_historical_windows(
                historical,
                StructuredNoteSpec(
                    basket=basket,
                    barrier=0.65,
                    coupon_barrier=0.65,
                    term_months=months_ago,
                ),
                window_days=forward_days,
                step_days=forward_days,
                max_windows=5,
                predicted_p_loss=prediction,
            )
            if train_replay.get("status") == "historical_replay":
                for window in train_replay["windows"]:
                    calibration_predictions.append(prediction)
                    calibration_outcomes.append(
                        int(window["outcome_type"] == "knock_in_loss")
                    )
            replay = replay_historical_windows(
                forward,
                StructuredNoteSpec(
                    basket=basket,
                    barrier=0.65,
                    coupon_barrier=0.65,
                    term_months=months_ago,
                ),
                window_days=forward_days,
                step_days=forward_days,
                max_windows=1,
                predicted_p_loss=prediction,
            )
            if replay.get("status") != "historical_replay":
                continue
            predictions.append(prediction)
            observed.append(float(replay["realized_replay_loss_rate"]))
            rows.append(
                {
                    "basket": basket,
                    "predicted_p_loss": round(prediction, 6),
                    "observed_loss_rate": replay["realized_replay_loss_rate"],
                    "source": "historical_forward_replay",
                    "prediction_source": "current_model_replayed_as_of_anchor",
                    "simulated_rows": 0,
                }
            )
        calibration_rates = fit_histogram_calibrator(
            calibration_predictions,
            calibration_outcomes,
            bins=5,
        )
        calibrated_predictions = apply_histogram_calibrator(
            predictions,
            calibration_rates,
        )
        for row, calibrated in zip(rows, calibrated_predictions):
            row["calibrated_p_loss"] = round(calibrated, 6)
        anchors[str(months_ago)] = {
            "months_ago": months_ago,
            "forward_days": forward_days,
            "baskets_replayed": len(rows),
            "metrics": _metrics(predictions, observed),
            "calibrated_metrics": _metrics(calibrated_predictions, observed),
            "calibration_train_observations": len(calibration_outcomes),
            "calibration_bins": 5,
            "calibration_rates": [round(rate, 6) for rate in calibration_rates],
            "phoenix_score_today": round(float(np.mean(1 - np.asarray(predictions)) * 100), 2)
            if predictions else None,
            "rows": rows,
        }
    passing_anchors = [
        value["calibrated_metrics"].get("brier_vs_baseline_pct", -100.0) > 0
        for value in anchors.values()
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "yfinance",
        "status": "research_only",
        "baskets_requested": len(baskets),
        "anchor_description": "basket started N months ago and evaluated through today",
        "production_weights_changed": False,
        "verdict_mutated": False,
        "anchor_months": list(ANCHOR_MONTHS),
        "anchors": anchors,
        "promotion_gate": {
            "eligible": bool(passing_anchors) and all(passing_anchors),
            "required": "all four anchor tests must beat their empirical baseline",
            "reason": (
                "promotion blocked until every anchor beats baseline"
                if not all(passing_anchors)
                else "research gate passed; separate PR review still required"
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baskets", type=int, default=100)
    parser.add_argument("--period", default="5y")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    universe = list(dict.fromkeys(DEFAULT_UNIVERSE + EXTRA_UNIVERSE))
    prices = _download_prices(universe, period=args.period)
    usable = [ticker for ticker in universe if ticker in prices]
    baskets = _build_baskets(usable, args.baskets, seed=2026)
    report = build_multi_horizon_report(prices, baskets)
    report.update(
        {
            "universe_requested": len(universe),
            "universe_with_data": len(usable),
            "missing_symbols": [ticker for ticker in universe if ticker not in prices],
        }
    )
    payload = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload)


if __name__ == "__main__":
    main()
