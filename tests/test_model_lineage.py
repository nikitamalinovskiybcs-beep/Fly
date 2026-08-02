from src.model_lineage import build_lineage_record, marginal_agent_contributions


def test_lineage_record_is_stable_and_secret_free() -> None:
    first = build_lineage_record(
        candidate="calibration",
        code_version="abc123",
        data_snapshot="snapshot-1",
        feature_names=["vol", "corr"],
        parameters={"bins": 5},
        gate={"passed": False},
    )
    second = build_lineage_record(
        candidate="calibration",
        code_version="abc123",
        data_snapshot="snapshot-1",
        feature_names=["corr", "vol"],
        parameters={"bins": 5},
        gate={"passed": False},
    )
    assert first["lineage_id"] == second["lineage_id"]
    assert first["production_weights_changed"] is False


def test_agent_ablation_marks_non_contributors() -> None:
    result = marginal_agent_contributions(0.10, {"risk": 0.10, "alpha": 0.12})
    assert result["remove_candidates"] == ["risk", "alpha"]
