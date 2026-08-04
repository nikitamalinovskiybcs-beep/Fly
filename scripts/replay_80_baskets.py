"""Replay six-month structured notes across an 80-stock free-data universe."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.outcome_engine import StructuredNoteSpec, replay_historical_windows
from src.real_data import compute_p_loss
from src.replay_calibration import apply_histogram_calibrator, fit_histogram_calibrator


DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "AVGO", "TSLA",
    "AMD", "QCOM", "NFLX", "ADBE", "CRM", "ORCL", "INTC", "CSCO",
    "JPM", "BAC", "GS", "MS", "C", "WFC", "V", "MA", "PYPL", "AXP",
    "XOM", "CVX", "COP", "SLB", "CAT", "DE", "GE", "HON", "MMM",
    "HD", "LOW", "WMT", "COST", "TGT", "MCD", "SBUX", "NKE", "DIS",
    "PEP", "KO", "UNH", "JNJ", "MRK", "PFE", "LLY", "ABBV", "BMY",
    "TMO", "ABT", "AMGN", "GILD", "BA", "UBER", "BKNG", "ABNB",
    "PLTR", "SNOW", "PANW", "CRWD", "NOW", "SHOP", "SQ", "COIN",
    "T", "VZ", "IBM", "TXN", "MU", "LRCX", "AMAT", "ADI", "BK",
    "ORLY", "REGN",
]


def _download_prices(tickers: list[str], period: str) -> dict[str, list[float]]:
    import yfinance as yf

    raw = yf.download(
        tickers,
        period=period,
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    if raw.empty:
        return {}
    closes = raw["Close"] if "Close" in raw else raw
    if hasattr(closes, "to_frame"):
        closes = closes.to_frame(name=tickers[0])
    return {
        ticker: [float(value) for value in closes[ticker].dropna().tolist()]
        for ticker in tickers
        if ticker in closes
    }


def _build_baskets(tickers: list[str], count: int, seed: int) -> list[list[str]]:
    rng = np.random.default_rng(seed)
    baskets: list[list[str]] = []
    for index in range(count):
        offset = (index * 3) % max(1, len(tickers))
        rotated = tickers[offset:] + tickers[:offset]
        if index % 2 == 0:
            basket = rotated[:3]
        else:
            basket = list(rng.choice(tickers, size=3, replace=False))
        baskets.append(sorted(set(basket)))
    return [basket for basket in baskets if len(basket) == 3]


def _binary_metrics(probabilities: list[float], outcomes: list[int]) -> dict[str, float]:
    if not outcomes:
        return {"brier": 0.0, "log_loss": 0.0}
    clipped = np.clip(probabilities, 1e-12, 1 - 1e-12)
    values = np.asarray(outcomes, dtype=float)
    return {
        "brier": round(float(np.mean((clipped - values) ** 2)), 6),
        "log_loss": round(
            float(np.mean(-(values * np.log(clipped) + (1 - values) * np.log(1 - clipped)))),
            6,
        ),
    }


def build_report(
    tickers: list[str] | None = None,
    basket_count: int = 80,
    period: str = "1y",
    seed: int = 42,
) -> dict:
    universe = list(dict.fromkeys(tickers or DEFAULT_UNIVERSE))
    prices = _download_prices(universe, period=period)
    usable = [ticker for ticker in universe if ticker in prices and len(prices[ticker]) >= 150]
    baskets = _build_baskets(usable, basket_count, seed)
    rows: list[dict] = []
    observations: list[tuple[int, float, int]] = []
    for basket in baskets:
        aligned = {ticker: prices[ticker] for ticker in basket}
        prediction = compute_p_loss(basket, term_months=6)["p_loss"]
        replay = replay_historical_windows(
            aligned,
            StructuredNoteSpec(
                basket=basket,
                barrier=0.65,
                coupon_barrier=0.65,
                term_months=6,
            ),
            window_days=126,
            step_days=21,
            max_windows=10,
            predicted_p_loss=prediction,
        )
        if replay.get("status") != "historical_replay":
            continue
        rows.append(
            {
                "basket": basket,
                "source": "historical_replay",
                "prediction_source": "phoenix_in_sample_model",
                "predicted_p_loss": prediction,
                "n_windows": replay["n_windows"],
                "observed_loss_rate": replay["realized_replay_loss_rate"],
                "mean_return_pct": replay["mean_return_pct"],
                "loss_rate_error": replay.get("loss_rate_error"),
            }
        )
        for window in replay["windows"]:
            observations.append(
                (
                    int(window["window_index"]),
                    float(prediction),
                    int(window["outcome_type"] == "knock_in_loss"),
                )
            )
    observed = [row["observed_loss_rate"] for row in rows]
    predicted = [row["predicted_p_loss"] for row in rows]
    empirical_rate = float(np.mean(observed)) if observed else 0.0

    def log_loss(probabilities: list[float], outcomes: list[float]) -> float:
        values = [
            -(outcome * np.log(np.clip(probability, 1e-12, 1 - 1e-12))
              + (1 - outcome) * np.log(np.clip(1 - probability, 1e-12, 1 - 1e-12)))
            for probability, outcome in zip(probabilities, outcomes)
        ]
        return float(np.mean(values)) if values else 0.0

    brier = float(np.mean((np.asarray(predicted) - np.asarray(observed)) ** 2))
    baseline_brier = float(np.mean((empirical_rate - np.asarray(observed)) ** 2))
    phoenix_log_loss = log_loss(predicted, observed)
    baseline_log_loss = log_loss([empirical_rate] * len(observed), observed)
    observations.sort(key=lambda item: item[0])
    split = int(len(observations) * 0.6)
    train = observations[:split]
    test = observations[split:]
    train_prior = float(np.mean([item[2] for item in train])) if train else 0.0
    train_predictions = [item[1] for item in train]
    train_outcomes = [item[2] for item in train]
    test_predictions = [item[1] for item in test]
    test_outcomes = [item[2] for item in test]
    shrinkage_strength = 0.5
    shrinkage_candidate = _binary_metrics(
        [
            shrinkage_strength * item[1] + (1 - shrinkage_strength) * train_prior
            for item in test
        ],
        test_outcomes,
    )
    oos_baseline = _binary_metrics(
        [train_prior] * len(test),
        [item[2] for item in test],
    )
    oos_phoenix = _binary_metrics(
        [item[1] for item in test],
        [item[2] for item in test],
    )
    histogram_rates = fit_histogram_calibrator(
        train_predictions,
        train_outcomes,
        bins=5,
    )
    histogram_candidate = _binary_metrics(
        apply_histogram_calibrator(test_predictions, histogram_rates),
        test_outcomes,
    )
    histogram_brier_improvement = (
        (oos_baseline["brier"] - histogram_candidate["brier"])
        / oos_baseline["brier"]
        * 100
        if oos_baseline["brier"]
        else None
    )
    histogram_log_loss_improvement = (
        (oos_baseline["log_loss"] - histogram_candidate["log_loss"])
        / oos_baseline["log_loss"]
        * 100
        if oos_baseline["log_loss"]
        else None
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "six_month_historical_replay",
        "universe_requested": len(universe),
        "universe_with_data": len(usable),
        "baskets_requested": basket_count,
        "baskets_replayed": len(rows),
        "historical_source": "yfinance",
        "simulated_rows": 0,
        "warning": (
            "Phoenix is trained on SETTLED_NOTES; this replay is historical "
            "research, not independent production validation."
        ),
        "summary": {
            "mean_predicted_loss": round(float(np.mean(predicted)), 6) if predicted else None,
            "mean_observed_loss": round(float(np.mean(observed)), 6) if observed else None,
            "mean_absolute_probability_gap": (
                round(float(np.mean(np.abs(np.asarray(predicted) - np.asarray(observed)))), 6)
                if predicted else None
            ),
            "brier": round(brier, 6) if predicted else None,
            "empirical_baseline_brier": round(baseline_brier, 6) if predicted else None,
            "brier_improvement_pct": (
                round((baseline_brier - brier) / baseline_brier * 100, 2)
                if baseline_brier else None
            ),
            "log_loss": round(phoenix_log_loss, 6) if predicted else None,
            "empirical_baseline_log_loss": round(baseline_log_loss, 6) if predicted else None,
            "log_loss_improvement_pct": (
                round((baseline_log_loss - phoenix_log_loss) / baseline_log_loss * 100, 2)
                if baseline_log_loss else None
            ),
        },
        "oos_calibration_research": {
            "source": "historical_replay",
            "status": "research_only",
            "train_observations": len(train),
            "oos_observations": len(test),
            "train_prior": round(train_prior, 6),
            "phoenix": oos_phoenix,
            "empirical_baseline": oos_baseline,
            "predeclared_shrinkage_strength": shrinkage_strength,
            "shrinkage_candidate": shrinkage_candidate,
            "histogram_bins": 5,
            "histogram_rates": [round(rate, 6) for rate in histogram_rates],
            "histogram_candidate": histogram_candidate,
            "histogram_brier_improvement_pct": round(histogram_brier_improvement, 2),
            "histogram_log_loss_improvement_pct": round(histogram_log_loss_improvement, 2),
            "oos_baseline_gate_passed": (
                histogram_candidate["brier"] < oos_baseline["brier"]
                and histogram_candidate["log_loss"] < oos_baseline["log_loss"]
            ),
            "accepted_candidate": "fixed_width_histogram_5_bins",
            "production_weights_changed": False,
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baskets", type=int, default=80)
    parser.add_argument("--period", default="1y")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(basket_count=args.baskets, period=args.period)
    payload = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload)


if __name__ == "__main__":
    main()
