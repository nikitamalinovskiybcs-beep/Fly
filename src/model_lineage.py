"""Reproducible, secret-free lineage records for research candidates."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Mapping


def build_lineage_record(
    *,
    candidate: str,
    code_version: str,
    data_snapshot: str,
    feature_names: list[str],
    parameters: Mapping[str, object],
    gate: Mapping[str, object],
) -> dict[str, object]:
    """Create a stable audit record without storing credentials or raw data."""
    payload = {
        "candidate": candidate,
        "code_version": code_version,
        "data_snapshot": data_snapshot,
        "feature_names": sorted(feature_names),
        "parameters": dict(parameters),
        "gate": dict(gate),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode(),
    ).hexdigest()[:16]
    return {
        "lineage_id": f"lineage_{digest}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        **payload,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }


def marginal_agent_contributions(
    baseline_score: float,
    scores_without_agent: Mapping[str, float],
) -> dict[str, object]:
    """Report ablation deltas; positive delta means the agent helped."""
    contributions = {
        name: round(float(baseline_score) - float(score), 6)
        for name, score in scores_without_agent.items()
    }
    return {
        "baseline_score": float(baseline_score),
        "contributions": contributions,
        "remove_candidates": [
            name for name, contribution in contributions.items()
            if contribution <= 0
        ],
        "status": "research_only",
        "production_weights_changed": False,
        "verdict_mutated": False,
    }
