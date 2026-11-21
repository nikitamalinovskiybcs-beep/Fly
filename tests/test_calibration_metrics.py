import pytest

from src.performance_metrics import binary_calibration_metrics


def test_binary_calibration_metrics_are_bounded() -> None:
    result = binary_calibration_metrics(
        [0.1, 0.9, 0.2, 0.8],
        [0.0, 1.0, 1.0, 0.0],
        bins=5,
    )

    assert result["observations"] == 4
    assert 0 <= result["brier"] <= 1
    assert result["log_loss"] > 0
    assert 0 <= result["ece"] <= 1


def test_binary_calibration_metrics_rejects_mismatched_inputs() -> None:
    with pytest.raises(ValueError, match="equal length"):
        binary_calibration_metrics([0.5], [0.0, 1.0])
