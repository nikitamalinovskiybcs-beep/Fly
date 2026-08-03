"""Small, local-only helpers for the next Phoenix improvement batch."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
import hashlib


def source_reliability_score(
    *,
    valid_rows: int,
    total_rows: int,
    stale_rows: int = 0,
) -> float:
    if total_rows <= 0 or valid_rows < 0 or stale_rows < 0:
        return 0.0
    usable = max(0, valid_rows - stale_rows)
    return round(min(1.0, usable / total_rows), 6)


def normalize_timestamp(timestamp: str, timezone_name: str) -> str:
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone information")
    if timezone_name.upper() != "UTC":
        raise ValueError("only UTC normalization is supported")
    return parsed.astimezone(timezone.utc).isoformat()


def deduplicate_observations(
    observations: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, object]] = []
    for observation in observations:
        key = (
            str(observation.get("ticker", "")),
            str(observation.get("observation_timestamp", "")),
            str(observation.get("source", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(observation))
    return result


def build_corporate_action_provenance(
    *,
    ticker: str,
    action_type: str,
    effective_date: str,
    source: str,
) -> dict[str, str]:
    return {
        "ticker": ticker,
        "action_type": action_type,
        "effective_date": effective_date,
        "source": source,
        "evidence_class": "market_data",
    }


def coupon_memory_transition(
    *,
    coupon_due: bool,
    coupon_paid: bool,
    memory_balance: int,
) -> int:
    if memory_balance < 0:
        raise ValueError("memory_balance must be non-negative")
    if coupon_paid:
        return 0
    return memory_balance + 1 if coupon_due else memory_balance


def build_walk_forward_manifest(
    *,
    train_end: str,
    test_start: str,
    test_end: str,
    snapshot_hash: str,
) -> dict[str, str]:
    if train_end >= test_start or test_start > test_end:
        raise ValueError("walk-forward periods overlap or are reversed")
    if not snapshot_hash:
        raise ValueError("snapshot_hash is required")
    return {
        "train_end": train_end,
        "test_start": test_start,
        "test_end": test_end,
        "snapshot_hash": snapshot_hash,
        "split_type": "chronological",
    }


def build_agent_ablation_record(
    *,
    agent: str,
    baseline_metric: float,
    ablated_metric: float,
) -> dict[str, object]:
    return {
        "agent": agent,
        "baseline_metric": baseline_metric,
        "ablated_metric": ablated_metric,
        "incremental_improvement": round(baseline_metric - ablated_metric, 6),
        "promotion_allowed": False,
        "evidence_gate": "fixed-24m OOS and human review",
    }


def validate_committee_proposal(proposal: Mapping[str, object]) -> list[str]:
    required = ("proposal_id", "decision", "metric_gate")
    errors = [
        f"missing:{field}"
        for field in required
        if not str(proposal.get(field, "")).strip()
    ]
    if proposal.get("decision") not in {"NOW", "RESEARCH", "BLOCKED", "REJECTED"}:
        errors.append("invalid:decision")
    for flag in (
        "production_weights_changed",
        "verdict_mutated",
        "trades_created",
    ):
        if proposal.get(flag) is not False:
            errors.append(f"unsafe:{flag}")
    return errors


def migration_checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def evidence_badge(value: object, *, source: str = "") -> str:
    if value in (None, "", []):
        return "MISSING"
    if source in {"simulation", "synthetic", "replay"}:
        return "SIMULATION"
    return "FACT"
