"""Fly Feature Store — centralized feature computation and caching.

Compute technical/statistical features once, reuse everywhere.
DuckDB-backed cache with TTL (graceful fallback to in-memory).

Usage:
    from src.feature_store import FeatureStore
    store = FeatureStore()
    vector = store.get_features("AAPL")           # -> FeatureVector
    vectors = store.get_features_batch(["AAPL", "MSFT"])
"""

from .models import FeatureVector
from .store import FeatureStore

__all__ = ["FeatureVector", "FeatureStore"]
