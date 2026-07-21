"""Tests for the feature store, feature computations, and cache."""

import numpy as np
import pandas as pd
import pytest

from src.feature_store import FeatureStore, FeatureVector
from src.feature_store.cache import FeatureCache
from src.feature_store import features as F


def _synthetic_ohlcv(n: int = 260, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n)
    close = pd.Series(100 + np.cumsum(rng.standard_normal(n)), index=idx)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": pd.Series(rng.integers(1_000_000, 5_000_000, n), index=idx),
        }
    )


class TestFeatureFunctions:
    def setup_method(self):
        self.df = _synthetic_ohlcv()
        self.close = self.df["Close"]

    def test_rsi_bounds(self):
        rsi = F.compute_rsi(self.close, 14)
        assert 0.0 <= rsi <= 100.0

    def test_sma_ema(self):
        assert F.compute_sma(self.close, 20) > 0
        assert F.compute_ema(self.close, 12) > 0

    def test_atr_positive(self):
        atr = F.compute_atr(self.df["High"], self.df["Low"], self.close, 14)
        assert atr >= 0

    def test_momentum_short_series(self):
        # fewer data points than lookback -> 0.0, no crash
        assert F.compute_momentum(self.close.head(3), 30) == 0.0

    def test_macd_triple(self):
        macd, signal, hist = F.compute_macd(self.close)
        assert np.isclose(hist, macd - signal, atol=1e-6)

    def test_bollinger(self):
        upper, lower, pct_b = F.compute_bollinger(self.close)
        assert upper > lower

    def test_adx_non_negative(self):
        adx = F.compute_adx(self.df["High"], self.df["Low"], self.close, 14)
        assert adx >= 0

    def test_beta_zero_variance(self):
        market = pd.Series(np.zeros(60))
        stock = pd.Series(np.random.randn(60))
        assert F.compute_beta(stock, market) == 1.0

    def test_volume_ratio_zero_avg(self):
        vol = pd.Series(np.zeros(30))
        assert F.compute_volume_ratio(vol) == 1.0


class TestFeatureCache:
    def test_set_get_roundtrip(self):
        cache = FeatureCache()
        cache.invalidate()
        cache.set("AAPL", "2025-01-01", "rsi_14", 55.5)
        assert cache.get("AAPL", "2025-01-01", "rsi_14") == 55.5

    def test_get_missing_returns_none(self):
        cache = FeatureCache()
        assert cache.get("ZZZ", "2025-01-01", "rsi_14") is None

    def test_get_vector(self):
        cache = FeatureCache()
        cache.invalidate("MSFT")
        cache.set("MSFT", "2025-01-01", "rsi_14", 60.0)
        cache.set("MSFT", "2025-01-01", "sma_50", 300.0)
        vec = cache.get_vector("MSFT", "2025-01-01")
        assert vec["rsi_14"] == 60.0
        assert vec["sma_50"] == 300.0

    def test_stats_structure(self):
        cache = FeatureCache()
        stats = cache.stats()
        assert "backend" in stats
        assert "total_entries" in stats
        assert stats["backend"] in ("duckdb", "memory")

    def test_invalidate_ticker(self):
        cache = FeatureCache()
        cache.set("TSLA", "2025-01-01", "rsi_14", 40.0)
        cache.invalidate("TSLA")
        assert cache.get("TSLA", "2025-01-01", "rsi_14") is None


class TestFeatureStore:
    def _store(self):
        def fetcher(ticker, period="1y"):
            seed = abs(hash(ticker)) % 1000
            return _synthetic_ohlcv(seed=seed)

        return FeatureStore(data_fetcher=fetcher)

    def test_get_features_returns_vector(self):
        store = self._store()
        vec = store.get_features("AAPL", "2025-01-01")
        assert isinstance(vec, FeatureVector)
        assert vec.ticker == "AAPL"
        assert vec.rsi_14 is not None
        assert vec.sma_50 is not None

    def test_features_cached_second_call(self):
        store = self._store()
        store.invalidate_cache("NVDA")
        store.get_features("NVDA", "2025-01-02")
        stats = store.cache_stats()
        assert stats["total_entries"] >= 20

    def test_batch(self):
        store = self._store()
        out = store.get_features_batch(["AAPL", "MSFT"])
        assert set(out.keys()) == {"AAPL", "MSFT"}

    def test_feature_matrix(self):
        store = self._store()
        df = store.get_feature_matrix(["AAPL", "MSFT"], feature_names=["rsi_14", "sma_50"])
        assert list(df.columns) == ["rsi_14", "sma_50"]
        assert len(df) == 2

    def test_empty_data_graceful(self):
        store = FeatureStore(data_fetcher=lambda t, p="1y": pd.DataFrame())
        vec = store.get_features("XXX", "2025-01-01")
        assert vec.ticker == "XXX"
        assert vec.rsi_14 is None

    def test_as_feature_map_excludes_none(self):
        vec = FeatureVector(ticker="A", date="2025-01-01", rsi_14=50.0)
        fmap = vec.as_feature_map()
        assert fmap == {"rsi_14": 50.0}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
