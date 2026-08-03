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


def find_duplicate_observations(
    observations: Iterable[Mapping[str, object]],
) -> dict[tuple[str, str], list[str]]:
    sources_by_key: dict[tuple[str, str], set[str]] = {}
    for observation in observations:
        key = (
            str(observation.get("ticker", "")),
            str(observation.get("observation_timestamp", "")),
        )
        sources_by_key.setdefault(key, set()).add(str(observation.get("source", "")))
    return {
        key: sorted(source for source in sources if source)
        for key, sources in sources_by_key.items()
        if len(sources) > 1
    }


def build_corporate_action_provenance(
    *,
    ticker: str,
    action_type: str,
    effective_date: str,
    source: str,
) -> dict[str, str]:
    record = {
        "ticker": ticker,
        "action_type": action_type,
        "effective_date": effective_date,
        "source": source,
        "evidence_class": "market_data",
    }
    record["lineage_hash"] = hashlib.sha256(
        "|".join(record.values()).encode("utf-8")
    ).hexdigest()
    return record


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
    term_months: int = 24,
    anchors: tuple[int, ...] = (6, 12, 18, 24),
) -> dict[str, str]:
    if train_end >= test_start or test_start > test_end:
        raise ValueError("walk-forward periods overlap or are reversed")
    if not snapshot_hash:
        raise ValueError("snapshot_hash is required")
    if term_months != 24:
        raise ValueError("fixed-24m term is required")
    if anchors != (6, 12, 18, 24):
        raise ValueError("fixed-24m anchors are required")
    return {
        "train_end": train_end,
        "test_start": test_start,
        "test_end": test_end,
        "snapshot_hash": snapshot_hash,
        "split_type": "chronological",
        "term_months": str(term_months),
        "anchors": ",".join(str(anchor) for anchor in anchors),
    }


def build_agent_ablation_record(
    *,
    agent: str,
    baseline_metric: float,
    ablated_metric: float,
    sample_size: int = 0,
) -> dict[str, object]:
    if sample_size < 0:
        raise ValueError("sample_size must be non-negative")
    return {
        "agent": agent,
        "baseline_metric": baseline_metric,
        "ablated_metric": ablated_metric,
        "incremental_improvement": round(baseline_metric - ablated_metric, 6),
        "promotion_allowed": False,
        "sample_size": sample_size,
        "human_review_required": True,
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


def validate_committee_proposal_strict(
    proposal: Mapping[str, object],
) -> list[str]:
    errors = validate_committee_proposal(proposal)
    for field in ("implementation_files", "acceptance_tests"):
        value = proposal.get(field)
        if not isinstance(value, (list, tuple)) or not value:
            errors.append(f"missing:{field}")
    return errors


def migration_checksum(sql: str) -> str:
    normalized = "\n".join(line.rstrip() for line in sql.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def evidence_badge(
    value: object,
    *,
    source: str = "",
    evidence_class: str = "",
) -> str:
    if value in (None, "", []):
        return "MISSING"
    normalized_class = evidence_class.lower()
    normalized_source = source.lower()
    if normalized_class in {"realized", "paper", "historical_replay"}:
        return normalized_class.upper()
    if normalized_class in {"simulation", "synthetic"} or normalized_source in {
        "simulation",
        "synthetic",
        "replay",
    }:
        return "SIMULATION"
    if normalized_class in {"estimated", "fallback"}:
        return "ESTIMATED"
    return "FACT"


def build_source_quality_record(
    observations: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    rows = [dict(observation) for observation in observations]
    total = len(rows)
    stale = sum(1 for row in rows if row.get("stale") is True)
    valid = sum(1 for row in rows if row.get("value") not in (None, ""))
    sources = sorted({str(row.get("source", "")) for row in rows if row.get("source")})
    return {
        "total_rows": total,
        "valid_rows": valid,
        "stale_rows": stale,
        "sources": sources,
        "reliability_score": source_reliability_score(
            valid_rows=valid,
            total_rows=total,
            stale_rows=stale,
        ),
        "evidence_gate": "research_only",
    }
