from src.performance_metrics import (
    build_out_of_sample_gate,
    build_realized_evaluation,
    compare_realized_baselines,
)


def test_evaluation_excludes_paper_notes() -> None:
    notes = [
        {"status": "paper", "outcome": {"source": "paper"}},
        {
            "status": "realized",
            "outcome": {
                "source": "realized",
                "outcome_type": "autocall",
                "return_pct": 4.0,
            },
            "metadata": {"predicted_autocall_prob": 0.7},
        },
    ]

    report = build_realized_evaluation(notes)

    assert report["realized_notes"] == 1
    assert report["mean_return_pct"] == 4.0
    assert report["source"] == "realized_notes_only"


def test_baseline_comparison_is_realized_only() -> None:
    report = compare_realized_baselines([
        {
            "source": "realized",
            "model_net_return_pct": 3.0,
            "baseline_net_return_pct": 1.0,
            "dealer_net_return_pct": 2.0,
        },
        {"source": "paper", "model_net_return_pct": 99.0},
    ])

    assert report["observations"] == 1
    assert report["model_lift_vs_baseline_pct"] == 2.0
    assert report["model_lift_vs_dealer_pct"] == 1.0


def test_out_of_sample_gate_requires_all_baseline_checks() -> None:
    gate = build_out_of_sample_gate({
        "observations": 20,
        "model_brier": 0.12,
        "baseline_brier": 0.15,
        "model_net_return_pct": 3.0,
        "baseline_net_return_pct": 2.0,
        "model_cvar": 0.20,
        "baseline_cvar": 0.25,
    })

    assert gate["passed"] is True
