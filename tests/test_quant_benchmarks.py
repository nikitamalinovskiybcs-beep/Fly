from src.quant_benchmarks import analytical_worst_of_probability


def test_analytical_quant_benchmark_is_bounded_and_labeled() -> None:
    prices = {
        "A": [100.0 + index for index in range(80)],
        "B": [100.0 + index * 0.9 for index in range(80)],
        "C": [100.0 + index * 1.1 for index in range(80)],
    }
    result = analytical_worst_of_probability(prices, ["A", "B", "C"])
    assert result["source"] == "analytical_quant"
    assert 0.0 <= result["robust_lower"] <= result["p_loss"] <= result["robust_upper"] <= 1.0
