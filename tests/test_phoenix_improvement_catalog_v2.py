from scripts.build_phoenix_improvement_catalog_v2 import build_catalog


def test_catalog_v2_contains_100_new_numbered_proposals() -> None:
    catalog = build_catalog()
    proposals = catalog["proposals"]
    assert catalog["count"] == 100
    assert proposals[0]["id"] == "phoenix-101"
    assert proposals[-1]["id"] == "phoenix-200"
    assert len({item["proposal"] for item in proposals}) == 100
    assert all(item["status"] == "research_only" for item in proposals)
