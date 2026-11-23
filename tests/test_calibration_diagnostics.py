from src.replay_calibration import diagnose_calibration_bottleneck


def test_calibration_diagnostics_prioritize_high_ece() -> None:
    result = diagnose_calibration_bottleneck(
        {
            "raw": {"log_loss": 0.5},
            "calibrated": {"log_loss": 0.4, "ece": 0.20},
        },
    )

    assert result["priority"] == "reduce_calibration_error"
    assert result["production_weights_changed"] is False
