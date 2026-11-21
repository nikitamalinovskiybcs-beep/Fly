from pathlib import Path

from src.calibration_agent import build_calibration_proposal, run_calibration_cycle


def _notes(count: int = 20) -> list[dict]:
    return [
        {
            "status": "realized",
            "metadata": {"predicted_autocall_prob": 0.5 + (index % 4) * 0.05},
            "outcome": {
                "source": "realized",
                "learning_eligible": True,
                "outcome_type": "autocall" if index % 2 == 0 else "knock_in_loss",
            },
        }
        for index in range(count)
    ]


def test_calibration_agent_never_changes_production_weights() -> None:
    result = build_calibration_proposal(_notes())
    assert result["production_weights_changed"] is False
    assert result["oos_observations"] == 8


def test_calibration_agent_persists_audit_record(tmp_path: Path) -> None:
    result = run_calibration_cycle(_notes(), tmp_path / "audit.json")
    assert result["agent"] == "calibration_agent"
    assert (tmp_path / "audit.json").exists()
