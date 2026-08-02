from src.replay_calibration import (
    apply_histogram_calibrator,
    fit_histogram_calibrator,
    walk_forward_histogram_calibration,
)


def test_histogram_calibration_is_deterministic_and_train_only() -> None:
    rates = fit_histogram_calibrator(
        [0.1, 0.2, 0.8, 0.9],
        [0, 1, 1, 0],
        bins=2,
    )
    assert rates == [0.5, 0.5]
    assert apply_histogram_calibrator([0.0, 0.99], rates) == [0.5, 0.5]


def test_walk_forward_calibration_uses_only_prior_rows() -> None:
    result = walk_forward_histogram_calibration(
        [0.1, 0.2, 0.8, 0.9, 0.1, 0.9],
        [0, 0, 1, 1, 1, 0],
        initial_train=4,
        bins=2,
    )
    assert result["status"] == "research_only"
    assert result["oos_observations"] == 2
    assert result["production_weights_changed"] is False
