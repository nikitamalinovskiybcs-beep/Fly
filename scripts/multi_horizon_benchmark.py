"""Run a 100-basket benchmark for the standard 24-month Phoenix product."""

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
from src.classical_baseline import evaluate_against_empirical_baseline, fixed_24m_gate
from src.quant_benchmarks import (
    analytical_worst_of_probability,
    historical_barrier_probability,
    regime_adjusted_probability,
)


EXTRA_UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLI", "XLP",
    "XLY", "XLB", "XLU", "ARKK", "EEM", "EFA", "TLT", "GLD", "SLV", "VNQ",
]
ANCHOR_MONTHS = (6, 12, 18, 24)
PRODUCT_TERM_MONTHS = 24


def _metrics(predicted: list[float], observed: list[float]) -> dict[str, float | None]:
    return evaluate_against_empirical_baseline(predicted, observed)


def build_multi_horizon_report(
    prices: dict[str, list[float]],
    baskets: list[list[str]],
) -> dict:
    anchors: dict[str, dict] = {}
    for months_ago in ANCHOR_MONTHS:
        end_offset_days = months_ago * 21
        product_days = PRODUCT_TERM_MONTHS * 21
        predictions: list[float] = []
        calibrated_predictions: list[float] = []
        quant_predictions: list[float] = []
        transfer_predictions: list[float] = []
        path_predictions: list[float] = []
        regime_predictions: list[float] = []
        observed: list[float] = []
        rows: list[dict] = []
        calibration_predictions: list[float] = []
        calibration_outcomes: list[int] = []
        for basket in baskets:
            if any(
                len(prices.get(ticker, [])) < end_offset_days + product_days
                for ticker in basket
            ):
                continue
            segment = {
                ticker: prices[ticker][-(end_offset_days + product_days):-end_offset_days]
                for ticker in basket
            }
            prediction = float(
                compute_p_loss(basket, term_months=PRODUCT_TERM_MONTHS)["p_loss"]
            )
            if prediction > 1:
                prediction /= 100
            historical = {
                ticker: prices[ticker][:-end_offset_days - product_days]
                for ticker in basket
            }
            quant = analytical_worst_of_probability(
                historical,
                basket,
                barrier=0.65,
                term_months=PRODUCT_TERM_MONTHS,
            )
            quant_12m = analytical_worst_of_probability(
                historical,
                basket,
                barrier=0.65,
                term_months=12,
            )
            path_quant = historical_barrier_probability(
                historical,
                basket,
                window_days=product_days,
                barrier=0.65,
            )
            regime_quant = regime_adjusted_probability(
                historical,
                basket,
                float(quant.get("p_loss", 0.0)),
            )
            train_replay = replay_historical_windows(
                historical,
                StructuredNoteSpec(
                    basket=basket,
                    barrier=0.65,
                    coupon_barrier=0.65,
                    term_months=PRODUCT_TERM_MONTHS,
                ),
                window_days=product_days,
                step_days=product_days,
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
                segment,
                StructuredNoteSpec(
                    basket=basket,
                    barrier=0.65,
                    coupon_barrier=0.65,
                    term_months=PRODUCT_TERM_MONTHS,
                ),
                window_days=product_days,
                step_days=product_days,
                max_windows=1,
                predicted_p_loss=prediction,
            )
            if replay.get("status") != "historical_replay":
                continue
            predictions.append(prediction)
            quant_predictions.append(float(quant.get("p_loss", 0.0)))
            transfer_predictions.append(
                0.5 * float(quant.get("p_loss", 0.0))
                + 0.5 * float(quant_12m.get("p_loss", 0.0))
            )
            path_predictions.append(float(path_quant.get("p_loss", 0.0)))
            regime_predictions.append(float(regime_quant.get("p_loss", 0.0)))
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
        calibrated_predictions = (
            apply_histogram_calibrator(predictions, calibration_rates)
            if len(calibration_outcomes) >= 20
            else list(predictions)
        )
        for row, calibrated in zip(rows, calibrated_predictions):
            row["calibrated_p_loss"] = round(calibrated, 6)
        anchors[str(months_ago)] = {
            "months_ago": months_ago,
            "product_term_months": PRODUCT_TERM_MONTHS,
            "end_offset_months": months_ago,
            "baskets_replayed": len(rows),
            "metrics": _metrics(predictions, observed),
            "calibrated_metrics": _metrics(calibrated_predictions, observed),
            "quant_metrics": _metrics(quant_predictions, observed),
            "duration_transfer_metrics": _metrics(transfer_predictions, observed),
            "path_quant_metrics": _metrics(path_predictions, observed),
            "regime_quant_metrics": _metrics(regime_predictions, observed),
            "calibration_train_observations": len(calibration_outcomes),
            "calibration_bins": 5,
            "calibration_rates": [round(rate, 6) for rate in calibration_rates],
            "quant_method": "gaussian_copula_terminal_worst_of",
            "duration_transfer_method": "50pct_24m_50pct_12m_quant_blend",
            "path_quant_method": "rolling_worst_of_barrier_frequency",
            "regime_quant_method": "recent_to_long_run_volatility_ratio",
            "phoenix_score_today": round(float(np.mean(1 - np.asarray(predictions)) * 100), 2)
            if predictions else None,
            "rows": rows,
        }
    candidate_metric_keys = {
        "raw": "metrics",
        "calibrated": "calibrated_metrics",
        "quant": "quant_metrics",
        "duration_transfer": "duration_transfer_metrics",
        "path_quant": "path_quant_metrics",
        "regime_quant": "regime_quant_metrics",
    }
    candidate_gates = {
        candidate: bool(
            fixed_24m_gate(
                (value[metric_key] for value in anchors.values())
            )["passed"]
        )
        for candidate, metric_key in candidate_metric_keys.items()
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "yfinance",
        "status": "research_only",
        "baskets_requested": len(baskets),
        "anchor_description": (
            "24-month product matured N months ago; anchor is the historical "
            "maturity date"
        ),
        "product_term_months": PRODUCT_TERM_MONTHS,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "anchor_months": list(ANCHOR_MONTHS),
        "anchors": anchors,
        "candidate_gates": candidate_gates,
        "candidate_status": {
            candidate: "eligible_for_review" if passed else "research_only_no_gate"
            for candidate, passed in candidate_gates.items()
        },
        "promotion_gate": {
            "eligible": any(candidate_gates.values()),
            "required": (
                "one candidate must beat baseline on Brier and log-loss at "
                "all four anchors with ECE <= 0.05"
            ),
            "reason": (
                "promotion blocked until one candidate passes all anchors"
                if not any(candidate_gates.values())
                else "research gate passed; separate PR review still required"
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baskets", type=int, default=100)
    parser.add_argument("--period", default="5y")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    universe = list(dict.fromkeys(DEFAULT_UNIVERSE + EXTRA_UNIVERSE))
    prices = _download_prices(universe, period=args.period)
    usable = [ticker for ticker in universe if ticker in prices]
    baskets = _build_baskets(usable, args.baskets, seed=args.seed)
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
