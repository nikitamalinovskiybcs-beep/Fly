"""Deterministic tests for structured-note outcomes."""

import json

import pandas as pd

from src.outcome_engine import (
    PaperOutcomeTracker,
    StructuredNoteSpec,
    replay_historical,
    simulate_monte_carlo,
)


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


def test_missing_price_data_is_explicit() -> None:
    spec = StructuredNoteSpec(basket=["A", "B"])
    result = replay_historical({"A": pd.Series([100, 101])}, spec)
    assert result["status"] == "insufficient_data"
