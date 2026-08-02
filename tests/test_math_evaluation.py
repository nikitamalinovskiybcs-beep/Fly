import pytest

from src.math_evaluation import brier_score, expected_calibration_error, log_loss


def test_perfect_binary_predictions_have_zero_brier() -> None:
    assert brier_score([0.0, 1.0], [0, 1]) == 0.0


def test_log_loss_rejects_mismatched_inputs() -> None:
    with pytest.raises(ValueError):
        log_loss([0.5], [0, 1])


def test_calibration_error_is_zero_for_well_calibrated_groups() -> None:
    assert expected_calibration_error([0.0, 1.0], [0, 1]) == 0.0
