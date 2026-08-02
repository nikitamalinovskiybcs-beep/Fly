from src.system_health import build_system_health


def test_system_health_keeps_benchmark_failure_visible() -> None:
    result = build_system_health(
        data_quality={"passed": True},
        structure_audit={"passed": True},
        benchmark={"promotion_gate": {"eligible": False}},
        safety={
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
        },
    )
    assert result["status"] == "attention_required"
    assert result["failed_checks"] == ["benchmark_gate"]
    assert result["production_weights_changed"] is False
