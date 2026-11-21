"""Deterministic prioritization of Phoenix research candidates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def rank_research_candidates(
    candidates: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Rank candidates by information gain, feasibility, and safety."""
    ranked = []
    for candidate in candidates:
        information_gain = float(candidate.get("information_gain", 0))
        feasibility = float(candidate.get("feasibility", 0))
        safety = float(candidate.get("safety", 0))
        cost = max(1.0, float(candidate.get("cost", 1)))
        score = (information_gain * 0.5 + feasibility * 0.3 + safety * 0.2) / cost
        ranked.append({
            **dict(candidate),
            "priority_score": round(score, 6),
            "decision": "research_only",
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
        })
    return sorted(ranked, key=lambda item: float(item["priority_score"]), reverse=True)
