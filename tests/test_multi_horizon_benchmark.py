from scripts.multi_horizon_benchmark import ANCHOR_MONTHS, _metrics


def test_multi_horizon_contract_is_deterministic() -> None:
    assert ANCHOR_MONTHS == (6, 12, 18, 24)
    result = _metrics([0.1, 0.2], [0.0, 1.0])
    assert result["mean_predicted_loss"] == 0.15
    assert result["mean_observed_loss"] == 0.5
