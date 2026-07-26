from src import full_pipeline


def test_full_analysis_runs_stages_in_order(monkeypatch) -> None:
    calls: list[str] = []

    def fake_precompute(tickers):
        calls.append("phoenix")
        return {"evidence_gate": {"passed": True}}

    def fake_market(tickers, period="2y"):
        calls.append("market")
        return {
            ticker: {"is_real": True, "source": "xfinlink", "as_of": "2025-01-03"}
            for ticker in tickers
        }

    def fake_product(universe, **kwargs):
        calls.append("product")
        return {
            "best": {
                "basket": ["A", "B", "C"],
                "barrier": 60,
                "coupon": 8,
                "tenor_months": 24,
            },
            "leaderboard": [],
            "n_evaluated": 1,
        }

    class FakeStress:
        def __call__(self, spec, n_paths=500):
            calls.append("stress")
            return {"source": "simulated", "scenarios": {}}

    monkeypatch.setattr(full_pipeline, "precompute_all", fake_precompute)
    monkeypatch.setattr(full_pipeline, "fetch_ticker_data", fake_market)
    monkeypatch.setattr(
        full_pipeline,
        "find_best_structured_product",
        fake_product,
    )
    monkeypatch.setattr(full_pipeline, "simulate_stress_suite", FakeStress())

    result = full_pipeline.run_full_analysis(["A", "B", "C"])

    assert calls == ["phoenix", "market", "product", "stress"]
    assert result["stages"]["product"] == "complete"
    assert result["stages"]["outcomes"] == "stress_complete"
