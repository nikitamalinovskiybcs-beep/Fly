"""Tests for the Numerai pipeline pure helpers (no network)."""
import numpy as np

from src.integrations.numerai_pipeline import _rank


def test_rank_is_monotonic_and_bounded():
    values = np.array([0.5, -2.0, 3.1, 0.0, 100.0])
    ranked = _rank(values)
    assert ranked.min() > 0.0
    assert ranked.max() < 1.0
    # order preserved
    assert list(np.argsort(values)) == list(np.argsort(ranked))


def test_rank_handles_ties_uniquely():
    values = np.array([1.0, 1.0, 1.0, 2.0])
    ranked = _rank(values)
    assert len(set(ranked.tolist())) == len(values)
    assert ranked[3] == ranked.max()


def test_rank_length_matches_input():
    values = np.random.default_rng(0).normal(size=250)
    ranked = _rank(values)
    assert len(ranked) == len(values)
    assert np.all((ranked > 0) & (ranked < 1))
