"""Compare Phoenix loss probabilities with transparent baseline models."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.math_evaluation import brier_score, expected_calibration_error, log_loss
from src.real_data import SETTLED_NOTES, compute_p_loss


def _metrics(probabilities: list[float], outcomes: list[int]) -> dict[str, float]:
    return {
        "brier": round(brier_score(probabilities, outcomes), 6),
        "log_loss": round(log_loss(probabilities, outcomes), 6),
        "ece": round(expected_calibration_error(probabilities, outcomes), 6),
        "mean_probability": round(sum(probabilities) / len(probabilities), 6),
    }


def build_report() -> dict:
    outcomes = [int(bad) for _, _, bad in SETTLED_NOTES]
    empirical_rate = sum(outcomes) / len(outcomes)
    phoenix = [
        float(
            compute_p_loss(
                basket_text.split("/"),
                term_months=round(term_years * 12),
            )["p_loss"]
        )
        for basket_text, term_years, _ in SETTLED_NOTES
    ]
    baselines = {
        "phoenix_p_loss": _metrics(phoenix, outcomes),
        "empirical_rate": _metrics([empirical_rate] * len(outcomes), outcomes),
        "coin_flip": _metrics([0.5] * len(outcomes), outcomes),
    }
    return {
        "dataset": "SETTLED_NOTES",
        "n_notes": len(outcomes),
        "observed_loss_rate": round(empirical_rate, 6),
        "evaluation_scope": "in_sample_research_only",
        "warning": "Phoenix is trained on this dataset; use OOS data for model selection.",
        "models": baselines,
    }


def main() -> None:
    print(json.dumps(build_report(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
