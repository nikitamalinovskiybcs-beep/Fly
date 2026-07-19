"""Tests for the 4 minimal-cost (Karpathy-style) improvements.

1. Offline deterministic synthetic bootstrap.
2. Deterministic AlphaAgent signal quality (no random mirage).
3. Cheap Numerai feature-neutralization post-process.
4. Cached connectivity probe (pure-render).
"""

import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


class TestSyntheticBootstrap:
    def setup_method(self) -> None:
        self.tmp = tempfile.mkdtemp()

    def teardown_method(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_offline_and_deterministic(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        a = PaperTradingAgent(tickers=["AAA", "BBB", "CCC", "DDD", "EEE"])
        a.DATA_DIR = Path(self.tmp)
        r1 = a.bootstrap_synthetic(days=120, seed=1)

        b = PaperTradingAgent(tickers=["AAA", "BBB", "CCC", "DDD", "EEE"])
        b.DATA_DIR = Path(tempfile.mkdtemp())
        r2 = b.bootstrap_synthetic(days=120, seed=1)

        assert r1["mode"] == "synthetic"
        assert r1["closed_trades"] > 0
        assert r1["closed_trades"] == r2["closed_trades"]
        assert r1["total_trades"] == r2["total_trades"]

    def test_generation_rises(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        a = PaperTradingAgent(tickers=["AAA", "BBB", "CCC", "DDD", "EEE"])
        a.DATA_DIR = Path(self.tmp)
        assert a._generation == 0
        a.bootstrap_synthetic(days=120, seed=1)
        assert a._generation >= 1


class TestDeterministicAlphaAgent:
    def test_no_randomness(self) -> None:
        from src.self_learning_agents import AlphaAgent
        agent = AlphaAgent()
        feats = {"tox_norm": 0.2, "fund_norm": 0.8}
        q1 = agent._estimate_signal_quality("s", 0.5, feats)
        q2 = agent._estimate_signal_quality("s", 0.5, feats)
        assert q1 == q2  # deterministic
        assert q1 >= 0.0

    def test_zero_value(self) -> None:
        from src.self_learning_agents import AlphaAgent
        agent = AlphaAgent()
        assert agent._estimate_signal_quality("s", 0.0, {}) == 0.0


class TestNeutralize:
    def test_reduces_feature_exposure(self) -> None:
        from src.integrations.numerai_pipeline import neutralize
        rng = np.random.default_rng(0)
        n = 500
        f1 = rng.normal(size=n)
        f2 = rng.normal(size=n)
        feats = pd.DataFrame({"f1": f1, "f2": f2})
        # Prediction strongly exposed to f1.
        preds = 0.9 * f1 + 0.1 * rng.normal(size=n)

        neutral = neutralize(preds, feats, proportion=1.0)
        exposure_before = abs(np.corrcoef(preds, f1)[0, 1])
        exposure_after = abs(np.corrcoef(neutral, f1)[0, 1])
        assert exposure_after < exposure_before
        assert len(neutral) == n

    def test_zero_proportion_is_identity(self) -> None:
        from src.integrations.numerai_pipeline import neutralize
        feats = pd.DataFrame({"f1": [1.0, 2.0, 3.0], "f2": [3.0, 2.0, 1.0]})
        preds = np.array([0.1, 0.5, 0.9])
        out = neutralize(preds, feats, proportion=0.0)
        assert np.allclose(out, preds)


class TestConnectivityProbeCache:
    def test_cache_roundtrip(self, tmp_path, monkeypatch) -> None:
        import src.api_manager as am
        monkeypatch.setattr(am, "PROBE_CACHE", tmp_path / "probe.json")
        mgr = am.APIManager()
        # No network: all services report no keys → deterministic.
        monkeypatch.setattr(mgr, "test_all", lambda: {"numerai": {"connected": False, "message": "no keys"}})

        assert mgr.get_cached_probe()["cached"] is False
        first = mgr.probe_connectivity(force=True)
        assert first["cached"] is False
        cached = mgr.get_cached_probe()
        assert cached["cached"] is True
        assert "numerai" in cached["results"]

    def test_cache_avoids_reprobe(self, tmp_path, monkeypatch) -> None:
        import src.api_manager as am
        monkeypatch.setattr(am, "PROBE_CACHE", tmp_path / "probe.json")
        mgr = am.APIManager()
        calls = {"n": 0}

        def _probe():
            calls["n"] += 1
            return {"numerai": {"connected": False}}

        monkeypatch.setattr(mgr, "test_all", _probe)
        mgr.probe_connectivity(force=True)
        mgr.probe_connectivity(force=False, max_age_s=9999)  # should hit cache
        assert calls["n"] == 1
