"""Deterministic tests for structured-note outcomes."""

import json

import pandas as pd

from src.outcome_engine import (
    PaperOutcomeTracker,
    StructuredNoteSpec,
    build_decision_record,
    build_quality_report,
    evaluate_product_safety,
    replay_historical,
    replay_historical_windows,
    simulate_monte_carlo,
    simulate_stress_suite,
)


def test_decision_record_links_market_evidence_to_product() -> None:
    record = build_decision_record(
        {
            "basket": ["A", "B"],
            "barrier": 60,
            "tenor_months": 24,
            "coupon": 8.0,
            "final_objective": 12.4,
        },
        market_data={
            "A": {"source": "xfinlink", "is_real": True, "as_of": "2025-01-02"},
            "B": {"source": "xfinlink", "is_real": True, "as_of": "2025-01-03"},
        },
        evidence_gate={"passed": True, "real_tickers": ["A", "B"]},
        generated_at="2025-01-03T12:00:00+00:00",
    )
    assert record["decision_id"].startswith("decision_")
    assert record["market_data_as_of"] == "2025-01-03"
    assert record["freshness_status"] == "verified"
    assert record["selection"]["basket"] == ["A", "B"]


def _prices(rows: list[list[float]]) -> dict[str, pd.Series]:
    frame = pd.DataFrame(rows, columns=["A", "B"])
    frame.index = pd.date_range("2024-01-01", periods=len(frame), freq="D")
    return {column: frame[column] for column in frame.columns}


def test_coupon_payment_and_maturity_redemption() -> None:
    spec = StructuredNoteSpec(
        basket=["A", "B"],
        term_months=12,
        observations_per_year=2,
        coupon_rate=0.05,
    )
    result = replay_historical(
        _prices([[100, 100], [98, 97], [98, 97], [96, 95]]),
        spec,
    )
    assert result["status"] == "historical_replay"
    assert result["outcome_type"] == "maturity_no_loss"
    assert result["coupons_paid"] == 2
    assert result["payoff"] == 1.1


def test_autocall_terminates_at_first_observation() -> None:
    spec = StructuredNoteSpec(
        basket=["A", "B"],
        term_months=12,
        observations_per_year=2,
        coupon_rate=0.05,
    )
    result = replay_historical(
        _prices([[100, 100], [110, 105], [108, 104], [70, 70]]),
        spec,
    )
    assert result["outcome_type"] == "autocall"
    assert result["autocall_observation"] == 1
    assert result["principal_return"] == 1.0


def test_barrier_breach_and_worst_of_redemption() -> None:
    spec = StructuredNoteSpec(
        basket=["A", "B"],
        barrier=0.7,
        term_months=12,
        observations_per_year=2,
        coupon_rate=0.0,
    )
    result = replay_historical(
        _prices([[100, 100], [65, 95], [80, 55], [80, 60]]),
        spec,
    )
    assert result["barrier_breached"] is True
    assert result["worst_of"] == "B"
    assert result["principal_return"] == 0.6
    assert result["outcome_type"] == "knock_in_loss"


def test_monte_carlo_is_reproducible_and_simulated() -> None:
    spec = StructuredNoteSpec(basket=["A", "B"], term_months=3)
    first = simulate_monte_carlo(spec, n_paths=200, seed=7)
    second = simulate_monte_carlo(spec, n_paths=200, seed=7)
    assert first == second
    assert first["source"] == "simulated"
    assert 0 <= first["p_loss"] <= 1


def test_stress_suite_has_expanded_simulated_scenarios() -> None:
    report = simulate_stress_suite(
        StructuredNoteSpec(basket=["AAPL", "MSFT"]),
        n_paths=100,
    )
    assert report["source"] == "simulated"
    assert report["scenario_count"] == 8
    assert "combined_stress" in report["scenarios"]
    assert "realized market evidence" in report["warning"]


def test_paper_resolution_is_the_only_learning_eligible_outcome(tmp_path) -> None:
    path = tmp_path / "outcomes.json"
    tracker = PaperOutcomeTracker(path)
    spec = StructuredNoteSpec(basket=["A", "B"], term_months=3)
    note = tracker.open_note(spec, note_id="note-1")
    assert tracker.open_note(spec, note_id="note-1")["id"] == note["id"]
    replay = replay_historical(_prices([[100, 100], [101, 101], [102, 102]]), spec)
    assert replay["learning_eligible"] is False
    resolved = tracker.resolve("note-1", _prices([[100, 100], [101, 101], [102, 102]]))
    assert resolved["status"] == "realized"
    assert resolved["learning_eligible"] is True
    saved = json.loads(path.read_text())
    assert saved["notes"][0]["status"] == "realized"


def test_paper_note_keeps_decision_id_until_realized(tmp_path) -> None:
    tracker = PaperOutcomeTracker(tmp_path / "outcomes.json")
    spec = StructuredNoteSpec(basket=["A", "B"], term_months=3)
    note = tracker.open_note(
        spec,
        note_id="note-linked",
        metadata={"decision_record": {"decision_id": "decision_123"}},
    )
    assert note["decision_id"] == "decision_123"
    assert note["instrument_type"] == "structured_note"
    state = tracker.refresh(
        "note-linked",
        _prices([[100, 100], [101, 101], [102, 102]]),
        as_of="2024-01-02",
    )
    assert state["decision_id"] == "decision_123"


def test_open_paper_note_has_mark_to_market_state(tmp_path) -> None:
    tracker = PaperOutcomeTracker(tmp_path / "outcomes.json")
    spec = StructuredNoteSpec(basket=["A", "B"], term_months=24)
    tracker.open_note(spec, note_id="note-mtm")

    state = tracker.refresh(
        "note-mtm",
        _prices([[100, 100], [70, 70], [50, 50]]),
        as_of="2024-01-02",
    )

    assert state["status"] == "paper"
    assert state["mark_to_market_principal"] == 0.5
    assert state["mark_to_market_return_pct"] < 0


def test_missing_price_data_is_explicit() -> None:
    spec = StructuredNoteSpec(basket=["A", "B"])
    result = replay_historical({"A": pd.Series([100, 101])}, spec)
    assert result["status"] == "insufficient_data"


def test_historical_windows_report_replay_error_against_prediction() -> None:
    spec = StructuredNoteSpec(basket=["A", "B"], term_months=3)
    prices = _prices([[100, 100], [95, 95], [94, 94], [93, 93]] * 3)
    report = replay_historical_windows(
        prices,
        spec,
        window_days=4,
        step_days=2,
        predicted_p_loss=0.10,
    )
    assert report["status"] == "historical_replay"
    assert report["n_windows"] == 5
    assert report["loss_rate_error"] >= 0


def test_safety_gate_blocks_high_loss_and_does_not_use_simulated_learning() -> None:
    gate = evaluate_product_safety(
        {"p_loss_pct": 50, "selected_vs_baseline": -1},
        stress_report={
            "scenarios": {
                "base": {"p_loss": 0.4, "cvar_95": 0.5},
            },
        },
    )
    assert gate["passed"] is False
    assert "model_p_loss_above_limit" in gate["reasons"]


def test_quality_report_is_conservative_with_small_samples() -> None:
    report = build_quality_report(
        {
            "n_windows": 4,
            "loss_rate_error": 0.05,
        },
        realized_outcomes=0,
    )
    assert report["status"] == "limited_evidence"
    assert report["confidence_pct"] < 50
    assert "historical_sample_below_20_windows" in report["warnings"]
