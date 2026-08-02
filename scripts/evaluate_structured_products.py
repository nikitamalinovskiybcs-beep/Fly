"""Run deterministic mathematical checks on the settled-note dataset."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.math_evaluation import brier_score, expected_calibration_error, log_loss
from src.real_data import SETTLED_NOTES, compute_p_loss
from src.structured_product import score_product


def evaluate_settled_notes() -> dict:
    probabilities = []
    outcomes = []
    for basket_text, term_years, bad in SETTLED_NOTES:
        basket = basket_text.split("/")
        probabilities.append(
            float(compute_p_loss(basket, term_months=round(term_years * 12))["p_loss"])
        )
        outcomes.append(int(bad))
    return {
        "dataset": "SETTLED_NOTES",
        "n_notes": len(outcomes),
        "brier": round(brier_score(probabilities, outcomes), 6),
        "log_loss": round(log_loss(probabilities, outcomes), 6),
        "ece": round(expected_calibration_error(probabilities, outcomes), 6),
        "observed_loss_rate": round(sum(outcomes) / len(outcomes), 6),
        "mean_predicted_loss": round(sum(probabilities) / len(probabilities), 6),
    }


def evaluate_structural_properties() -> dict:
    basket = ["AAPL", "MSFT", "NVDA"]
    barriers = [0.55, 0.60, 0.65, 0.70, 0.75]
    scores = [score_product(basket, barrier, 12)["p_loss_pct"] for barrier in barriers]
    return {
        "barrier_grid": barriers,
        "p_loss_by_barrier": scores,
        "p_loss_monotone_non_decreasing": scores == sorted(scores),
    }


def main() -> None:
    report = {
        "settled_note_metrics": evaluate_settled_notes(),
        "structural_properties": evaluate_structural_properties(),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
