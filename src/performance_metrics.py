"""Realized-only model evaluation and baseline comparison."""

import math
from statistics import mean
from typing import Iterable, Mapping


def binary_calibration_metrics(
    probabilities: Iterable[float],
    outcomes: Iterable[float],
    bins: int = 10,
) -> dict[str, float | int]:
    """Compute Brier, log-loss, ECE, and Brier decomposition."""
    predicted = [min(1.0, max(0.0, float(value))) for value in probabilities]
    actual = [float(value) for value in outcomes]
    if len(predicted) != len(actual):
        raise ValueError("probabilities and outcomes must have equal length")
    if not predicted:
        raise ValueError("at least one observation is required")
    if bins < 2:
        raise ValueError("bins must be at least 2")
    base_rate = mean(actual)
    brier = mean((probability - outcome) ** 2 for probability, outcome in zip(predicted, actual))
    epsilon = 1e-12
    log_loss = mean(
        -outcome * math.log(max(epsilon, probability))
        - (1.0 - outcome) * math.log(max(epsilon, 1.0 - probability))
        for probability, outcome in zip(predicted, actual)
    )
    reliability = 0.0
    resolution = 0.0
    ece = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        members = [
            position for position, probability in enumerate(predicted)
            if lower <= probability < upper
            or (index == bins - 1 and probability == upper)
        ]
        if not members:
            continue
        fraction = len(members) / len(predicted)
        mean_prediction = mean(predicted[position] for position in members)
        mean_outcome = mean(actual[position] for position in members)
        reliability += fraction * (mean_prediction - mean_outcome) ** 2
        resolution += fraction * (mean_outcome - base_rate) ** 2
        ece += fraction * abs(mean_prediction - mean_outcome)
    uncertainty = base_rate * (1.0 - base_rate)
    return {
        "observations": len(predicted),
        "brier": round(brier, 8),
        "log_loss": round(log_loss, 8),
        "ece": round(ece, 8),
        "reliability": round(reliability, 8),
        "resolution": round(resolution, 8),
        "uncertainty": round(uncertainty, 8),
    }


def build_realized_evaluation(
    notes: Iterable[Mapping],
    target_notes: int = 20,
    stretch_target: int = 50,
) -> dict:
    """Summarize resolved notes without treating paper or replay as realized."""
    realized = [
        note for note in notes
        if note.get("status") == "realized"
        and note.get("outcome", {}).get("source") == "realized"
    ]
    outcomes = [note["outcome"] for note in realized]
    returns = [float(item["return_pct"]) for item in outcomes if "return_pct" in item]
    losses = [
        item.get("outcome_type") == "knock_in_loss"
        for item in outcomes
    ]
    autocalls = [
        item.get("outcome_type") == "autocall"
        for item in outcomes
    ]
    predicted = [
        (
            float(note.get("metadata", {}).get("predicted_autocall_prob")),
            float(item.get("outcome_type") == "autocall"),
        )
        for note, item in zip(realized, outcomes)
        if note.get("metadata", {}).get("predicted_autocall_prob") is not None
    ]
    brier = (
        mean((probability - actual) ** 2 for probability, actual in predicted)
        if predicted else None
    )
    count = len(realized)
    return {
        "status": "ready" if count >= target_notes else "building_sample",
        "realized_notes": count,
        "target_notes": target_notes,
        "stretch_target": stretch_target,
        "progress_pct": round(min(100.0, count / max(1, target_notes) * 100), 1),
        "stretch_progress_pct": round(
            min(100.0, count / max(1, stretch_target) * 100),
            1,
        ),
        "win_rate_pct": round(
            (1.0 - mean(losses)) * 100 if losses else 0.0,
            2,
        ),
        "loss_rate_pct": round(mean(losses) * 100 if losses else 0.0, 2),
        "autocall_rate_pct": round(mean(autocalls) * 100 if autocalls else 0.0, 2),
        "mean_return_pct": round(mean(returns), 4) if returns else None,
        "brier_autocall": round(brier, 6) if brier is not None else None,
        "source": "realized_notes_only",
    }


def compare_realized_baselines(records: Iterable[Mapping]) -> dict:
    """Compare realized net returns against supplied model baselines."""
    rows = [row for row in records if row.get("source") == "realized"]
    fields = ("model_net_return_pct", "baseline_net_return_pct", "dealer_net_return_pct")
    result = {"source": "realized_notes_only", "observations": len(rows)}
    for field in fields:
        values = [float(row[field]) for row in rows if row.get(field) is not None]
        result[field] = round(mean(values), 4) if values else None
    if result["model_net_return_pct"] is not None and result["baseline_net_return_pct"] is not None:
        result["model_lift_vs_baseline_pct"] = round(
            result["model_net_return_pct"] - result["baseline_net_return_pct"],
            4,
        )
    if result["model_net_return_pct"] is not None and result["dealer_net_return_pct"] is not None:
        result["model_lift_vs_dealer_pct"] = round(
            result["model_net_return_pct"] - result["dealer_net_return_pct"],
            4,
        )
    return result


def build_out_of_sample_gate(
    metrics: Mapping,
    minimum_observations: int = 20,
) -> dict:
    """Approve a candidate only when it beats baseline out of sample."""
    observations = int(metrics.get("observations", 0))
    checks = {
        "sample_size": observations >= minimum_observations,
        "brier": (
            metrics.get("model_brier") is not None
            and metrics.get("baseline_brier") is not None
            and float(metrics["model_brier"]) <= float(metrics["baseline_brier"])
        ),
        "return": (
            metrics.get("model_net_return_pct") is not None
            and metrics.get("baseline_net_return_pct") is not None
            and float(metrics["model_net_return_pct"])
            >= float(metrics["baseline_net_return_pct"])
        ),
        "tail_risk": (
            metrics.get("model_cvar") is not None
            and metrics.get("baseline_cvar") is not None
            and float(metrics["model_cvar"]) <= float(metrics["baseline_cvar"])
        ),
    }
    if metrics.get("model_log_loss") is not None and metrics.get("baseline_log_loss") is not None:
        checks["log_loss"] = float(metrics["model_log_loss"]) <= float(metrics["baseline_log_loss"])
    if metrics.get("model_ece") is not None and metrics.get("baseline_ece") is not None:
        checks["ece"] = float(metrics["model_ece"]) <= float(metrics["baseline_ece"])
    return {
        "passed": all(checks.values()),
        "status": "approved" if all(checks.values()) else "blocked",
        "checks": checks,
        "observations": observations,
        "reason": (
            "model_beats_baseline_out_of_sample"
            if all(checks.values())
            else "out_of_sample_baseline_not_beaten"
        ),
    }
