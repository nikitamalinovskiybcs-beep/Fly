"""Tests for src.structured_product — best-product optimizer."""


class TestStructuredProduct:
    """The optimizer must produce a deterministic, ranked best product."""

    def test_score_product_keys(self) -> None:
        from src.structured_product import score_product
        cfg = score_product(["AAPL", "MSFT", "GOOGL"], 0.65, 24)
        assert set(cfg) >= {"barrier", "tenor_months", "coupon",
                            "p_loss_pct", "avg_tox", "objective"}
        assert cfg["barrier"] == 65
        assert cfg["tenor_months"] == 24

    def test_best_config_grid(self) -> None:
        from src.structured_product import best_config_for_basket, score_product
        basket = ["AAPL", "MSFT", "GOOGL"]
        best = best_config_for_basket(basket)
        # No other grid point may beat the chosen configuration.
        for barrier in (0.55, 0.65, 0.75):
            for tenor in (12, 24, 36):
                assert score_product(basket, barrier, tenor)["objective"] <= best["objective"] + 1e-9

    def test_find_best_product(self) -> None:
        from src.structured_product import find_best_structured_product
        universe = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "JPM"]
        result = find_best_structured_product(universe, basket_size=3)
        assert "best" in result
        assert len(result["best"]["basket"]) == 3
        assert result["n_evaluated"] > 0
        # Leaderboard is sorted by final objective, descending.
        objs = [c["final_objective"] for c in result["leaderboard"]]
        assert objs == sorted(objs, reverse=True)

    def test_deterministic(self) -> None:
        from src.structured_product import find_best_structured_product
        universe = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "JPM"]
        a = find_best_structured_product(universe, basket_size=3)
        b = find_best_structured_product(universe, basket_size=3)
        assert a["best"]["basket"] == b["best"]["basket"]

    def test_live_agent_features_are_used(self) -> None:
        from src.structured_product import find_best_structured_product

        yf_data = {
            "AAPL": {
                "pe": 25, "iv30": 22, "hist_vol": 20, "return_1m": 0.04,
                "beta": 1.0, "sector": "Technology", "ema200_above": True,
            },
            "MSFT": {
                "pe": 30, "iv30": 24, "hist_vol": 21, "return_1m": 0.03,
                "beta": 1.1, "sector": "Technology", "ema200_above": True,
            },
            "JPM": {
                "pe": 12, "iv30": 30, "hist_vol": 28, "return_1m": -0.01,
                "beta": 1.2, "sector": "Financials", "ema200_above": False,
            },
        }
        result = find_best_structured_product(
            ["AAPL", "MSFT", "JPM"], basket_size=3, yf_data=yf_data,
        )
        assert result["best"]["agents_with_signal"]
        assert result["best"]["agent_contributions"]
        assert len(result["candidate_catalog"]) == result["n_evaluated"]
        assert result["candidate_catalog"][0]["selected"] is True
        assert set(result["best"]["split_objectives"]) == {
            "train", "validation", "test",
        }
        assert "baseline_comparison" in result
        assert result["selection_method"].startswith("min(")

    def test_real_market_data_changes_objective(self) -> None:
        from src.structured_product import score_product

        market_data = {
            ticker: {
                "source": "xfinlink",
                "is_real": True,
                "iv30": 55,
                "beta": 1.8,
                "ema200_pct": -12,
            }
            for ticker in ("AAPL", "MSFT", "JPM")
        }
        static = score_product(["AAPL", "MSFT", "JPM"], 0.65, 24)
        live = score_product(
            ["AAPL", "MSFT", "JPM"], 0.65, 24, yf_data=market_data,
        )
        assert live["market_adjustment"] < 0
        assert live["objective"] < static["objective"]

    def test_real_data_gate_rejects_estimated_universe(self) -> None:
        from src.structured_product import find_best_structured_product

        result = find_best_structured_product(
            ["AAPL", "MSFT", "JPM"],
            basket_size=3,
            yf_data={
                ticker: {"source": "estimated", "is_real": False}
                for ticker in ("AAPL", "MSFT", "JPM")
            },
            require_real_data=True,
        )
        assert result["error"] == "insufficient_real_market_data"

    def test_universe_too_small(self) -> None:
        from src.structured_product import find_best_structured_product
        result = find_best_structured_product(["AAPL"], basket_size=3)
        assert result["error"] == "universe_too_small"


class TestSchedulerWiring:
    """Autopilot and product search must be live tasks in the scheduler."""

    def test_product_search_task(self, tmp_path, monkeypatch) -> None:
        import src.scheduler as sched_mod
        sched_mod.SCHEDULE_LOG = tmp_path / "scheduler_log.json"
        scheduler = sched_mod.FlyScheduler(universe=["AAPL", "MSFT", "GOOGL", "JPM"])
        result = scheduler._run_product_search()
        assert result["status"] == "ok"
        assert result["n_evaluated"] > 0
        assert result["best"]["basket"]

    def test_autopilot_task_runs(self, tmp_path) -> None:
        import src.scheduler as sched_mod
        sched_mod.SCHEDULE_LOG = tmp_path / "scheduler_log.json"
        scheduler = sched_mod.FlyScheduler()
        result = scheduler._run_autopilot()
        assert result["status"] in {"ran", "kill_switch_engaged", "error"}
