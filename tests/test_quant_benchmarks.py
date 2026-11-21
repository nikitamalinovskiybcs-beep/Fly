from src.quant_benchmarks import (
    analytical_worst_of_probability,
    historical_barrier_probability,
    regime_adjusted_probability,
)


def test_analytical_quant_benchmark_is_bounded_and_labeled() -> None:
    prices = {
        "A": [100.0 + index for index in range(80)],
        "B": [100.0 + index * 0.9 for index in range(80)],
        "C": [100.0 + index * 1.1 for index in range(80)],
    }
    result = analytical_worst_of_probability(prices, ["A", "B", "C"])
    assert result["source"] == "analytical_quant"
    assert 0.0 <= result["robust_lower"] <= result["p_loss"] <= result["robust_upper"] <= 1.0


def test_path_and_regime_candidates_are_bounded() -> None:
    prices = {
        "A": [100.0 + index for index in range(120)],
        "B": [100.0 + index * 0.9 for index in range(120)],
        "C": [100.0 + index * 1.1 for index in range(120)],
    }
    path = historical_barrier_probability(prices, ["A", "B", "C"], 60)
    regime = regime_adjusted_probability(prices, ["A", "B", "C"], 0.2)
    assert 0.0 <= path["p_loss"] <= 1.0
    assert 0.0 <= regime["p_loss"] <= 1.0
