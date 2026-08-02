from src.infrastructure_health import build_infrastructure_health


def test_infrastructure_health_has_one_schema() -> None:
    result = build_infrastructure_health(
        data={"passed": True},
        cache={"healthy": True},
        storage={"healthy": True},
        runtime={"healthy": True},
        model={"production_safety": True, "promotion_gate": False},
    )

    assert result["schema_version"] == "infrastructure-health-v1"
    assert result["status"] == "attention_required"
    assert result["failed_checks"] == ["promotion_gate"]
    assert result["production_weights_changed"] is False
