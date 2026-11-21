from scripts.benchmark_structured_models import build_report


def test_benchmark_reports_oos_warning_and_baselines() -> None:
    report = build_report()
    assert report["evaluation_scope"] == "in_sample_research_only"
    assert "empirical_rate" in report["models"]
    assert "phoenix_p_loss" in report["models"]
    assert report["n_notes"] == 50
