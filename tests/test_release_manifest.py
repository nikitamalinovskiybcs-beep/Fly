from scripts.build_release_manifest import build_release_manifest


def test_release_manifest_preserves_rollback_and_safety_state() -> None:
    manifest = build_release_manifest(
        {"status": "healthy"},
        {"mode": "research_only"},
        version="abc123",
        rollback_ref="refs/heads/main",
    )

    assert manifest["version"] == "abc123"
    assert manifest["rollback_ref"] == "refs/heads/main"
    assert manifest["retention_days"] == 30
    assert manifest["promotion"] == "human_review_required"
    assert manifest["trades_created"] is False
