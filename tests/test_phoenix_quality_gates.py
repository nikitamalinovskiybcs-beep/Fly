from datetime import date

from src.phoenix_quality_gates import (
    autocall_metrics,
    agent_evidence_gate,
    confidence_interval,
    evidence_partition,
    feature_lineage,
    monte_carlo_convergence,
    monotonicity_check,
    quote_fit_gate,
    require_fixed_24m_anchors,
    seed_sensitivity,
    snapshot_hash,
    sensitivity_grid,
    validate_basket_symbols,
    validate_correlation_matrix,
    validate_chronological_oos,
    validate_market_observations,
    validate_observation_schedule,
    validate_payoff_bounds,
    worst_of_driver,
)


def test_market_gate_rejects_future_and_stale_rows() -> None:
    result = validate_market_observations(
        [
            {"source": "test", "as_of": "2024-11-01"},
            {"source": "test", "as_of": "2024-11-20"},
        ],
        as_of=date(2024, 11, 10),
        max_age_days=5,
    )

    assert result["passed"] is False
    assert "0:stale" in result["errors"]
    assert "1:future_dated" in result["errors"]


def test_quality_helpers_are_deterministic_and_bounded() -> None:
    assert snapshot_hash({"b": 2, "a": 1}) == snapshot_hash({"a": 1, "b": 2})
    payoff = validate_payoff_bounds(
        notional=100.0,
        cashflows=[5.0, 5.0],
        terminal_redemption=100.0,
    )
    assert payoff["passed"] is True


def test_autocall_metrics_and_evidence_partition() -> None:
    result = autocall_metrics(
        [
            {"outcome_type": "autocall", "autocall_observation": 1},
            {"outcome_type": "knock_in_loss"},
        ]
    )
    assert result["autocall_rate"] == 0.5
    assert evidence_partition(
        [{"evidence_status": "realized"}, {"evidence_status": "simulation"}]
    ) == {
        "realized": 1,
        "verified_quote": 0,
        "historical_replay": 0,
        "simulation": 1,
        "unverified": 0,
    }


def test_fixed_24m_gate_requires_all_anchors() -> None:
    assert require_fixed_24m_anchors(
        {"6": {}, "12": {}, "18": {}, "24": {}}
    )["passed"]
    assert require_fixed_24m_anchors({"6": {}})["passed"] is False


def test_chronological_oos_gate_rejects_missing_or_reordered_anchors() -> None:
    assert validate_chronological_oos(
        [{"anchor_months": month} for month in [6, 12, 18, 24]]
    )["passed"]
    result = validate_chronological_oos(
        [{"anchor_months": month} for month in [12, 6, 18, 24]]
    )
    assert result["passed"] is False
    assert "not_chronological" in result["errors"]


def test_correlation_quote_and_worst_of_gates() -> None:
    assert validate_correlation_matrix([[1.0, 0.2], [0.2, 1.0]])["passed"]
    assert quote_fit_gate(
        model_coupon_pa=0.10, dealer_coupon_pa=0.105, tolerance_pa=0.01
    )["passed"]
    assert worst_of_driver({"A": 0.9, "B": 0.7})["ticker"] == "B"


def test_convergence_and_confidence_helpers() -> None:
    interval = confidence_interval([0.4, 0.5, 0.6])
    assert interval["lower"] < interval["mean"] < interval["upper"]
    convergence = monte_carlo_convergence(
        [100, 200], [0.2, 0.21], [0.05, 0.03]
    )
    assert convergence["non_increasing_standard_error"] is True


def test_lineage_input_and_sensitivity_helpers() -> None:
    assert validate_basket_symbols(["A", "B"], ["A", "B"])["passed"]
    assert validate_observation_schedule(
        ["2024-01-01", "2024-04-01"]
    )["passed"]
    lineage = feature_lineage(
        model_id="phoenix", model_version="v1",
        data_snapshot={"as_of": "2024-01-01"}, feature_names=["vol", "corr"]
    )
    assert lineage["lineage_status"] == "recorded"
    assert seed_sensitivity({1: 0.1, 2: 0.101}, tolerance=0.01)["passed"]
    assert sensitivity_grid(
        parameter="barrier", values=[0.6, 0.7], estimates=[0.2, 0.3]
    )["points"][1]["estimate"] == 0.3
    assert agent_evidence_gate(
        provider="local:qwen", status="completed",
        evidence_ids=["snapshot-1"], confidence=0.7
    )["passed"]
    assert monotonicity_check(0.2, 0.3, expected="increasing")["passed"]
