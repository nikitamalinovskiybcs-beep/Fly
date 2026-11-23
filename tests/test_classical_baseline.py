import pytest

from src.classical_baseline import (
    empirical_probability,
    evaluate_against_empirical_baseline,
    fixed_24m_gate,
)


def test_empirical_baseline_is_deterministic() -> None:
    assert empirical_probability([0.0, 1.0, 1.0]) == pytest.approx(2 / 3)


def test_classical_baseline_metrics_are_reproducible() -> None:
    result = evaluate_against_empirical_baseline([0.2, 0.8], [0.0, 1.0])

    assert result["brier"] == 0.04
    assert result["empirical_baseline_brier"] == 0.25
    assert result["brier_vs_baseline_pct"] == 84.0


def test_fixed_24m_gate_requires_every_anchor() -> None:
    passing = {
        "brier_vs_baseline_pct": 10.0,
        "log_loss": 0.4,
        "empirical_baseline_log_loss": 0.5,
        "ece": 0.02,
    }
    failing = {**passing, "brier_vs_baseline_pct": -1.0}

    assert fixed_24m_gate([passing, passing])["passed"] is True
    assert fixed_24m_gate([passing, failing])["passed"] is False
