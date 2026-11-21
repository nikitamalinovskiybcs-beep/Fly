from scripts.build_phoenix_improvement_catalog import build_catalog


def test_catalog_contains_100_distinct_safe_proposals() -> None:
    catalog = build_catalog()
    proposals = catalog["proposals"]
    assert catalog["count"] == 100
    assert len({item["id"] for item in proposals}) == 100
    assert all(item["status"] == "research_only" for item in proposals)
    assert catalog["production_weights_changed"] is False
