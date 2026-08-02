"""Realized-only model evaluation and baseline comparison."""

from statistics import mean
from typing import Iterable, Mapping


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
