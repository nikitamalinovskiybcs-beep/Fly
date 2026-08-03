from src.storage_readiness import build_storage_readiness


def test_storage_readiness_accepts_local_persistence() -> None:
    result = build_storage_readiness({"sqlite": True})

    assert result["status"] == "ready"
    assert result["local_persistence"] is True
    assert result["production_weights_changed"] is False


def test_storage_readiness_blocks_without_local_persistence() -> None:
    result = build_storage_readiness({})

    assert result["status"] == "blocked"
    assert result["local_persistence"] is False
