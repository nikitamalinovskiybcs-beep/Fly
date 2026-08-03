from src.research_improvements import (
    build_agent_ablation_record,
    build_corporate_action_provenance,
    build_walk_forward_manifest,
    coupon_memory_transition,
    deduplicate_observations,
    evidence_badge,
    migration_checksum,
    normalize_timestamp,
    source_reliability_score,
    validate_committee_proposal,
)


def test_data_provenance_helpers_are_deterministic() -> None:
    assert source_reliability_score(valid_rows=9, total_rows=10, stale_rows=1) == 0.8
    assert normalize_timestamp("2024-11-01T12:00:00+00:00", "UTC").endswith("+00:00")
    observations = [
        {"ticker": "AAPL", "observation_timestamp": "t", "source": "a"},
        {"ticker": "AAPL", "observation_timestamp": "t", "source": "a"},
    ]
    assert len(deduplicate_observations(observations)) == 1
    assert build_corporate_action_provenance(
        ticker="AAPL",
        action_type="split",
        effective_date="2024-01-01",
        source="provider",
    )["evidence_class"] == "market_data"


def test_payoff_and_calibration_helpers_block_unsafe_inputs() -> None:
    assert coupon_memory_transition(
        coupon_due=True,
        coupon_paid=False,
        memory_balance=2,
    ) == 3
    assert coupon_memory_transition(
        coupon_due=True,
        coupon_paid=True,
        memory_balance=2,
    ) == 0
    manifest = build_walk_forward_manifest(
        train_end="2024-01-01",
        test_start="2024-01-02",
        test_end="2024-02-01",
        snapshot_hash="abc",
    )
    assert manifest["split_type"] == "chronological"
    assert build_agent_ablation_record(
        agent="risk",
        baseline_metric=0.2,
        ablated_metric=0.25,
    )["promotion_allowed"] is False


def test_committee_storage_and_ui_helpers_preserve_evidence() -> None:
    valid = {
        "proposal_id": "p1",
        "decision": "RESEARCH",
        "metric_gate": "fixed-24m OOS",
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
    assert validate_committee_proposal(valid) == []
    invalid = dict(valid)
    invalid["trades_created"] = True
    assert "unsafe:trades_created" in validate_committee_proposal(invalid)
    assert len(migration_checksum("select 1")) == 64
    assert evidence_badge(0, source="yfinance") == "FACT"
    assert evidence_badge(0, source="replay") == "SIMULATION"
    assert evidence_badge(None) == "MISSING"
