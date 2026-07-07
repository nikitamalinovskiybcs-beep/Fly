"""Tests for live features: volume signal, greeks exposure, bootstrap, scheduler."""

import numpy as np
import pandas as pd
import pytest

from src.agents.paper_trader import PaperTradingAgent
from src.agents.models import TradeAction


class TestVolumeSignal:
    """Test real volume_confirmation signal."""

    def test_volume_signal_high_volume(self):
        agent = PaperTradingAgent(tickers=["TEST"])
        volumes = [1_000_000] * 20 + [2_000_000]
        agent._volume_cache["TEST"] = pd.Series(volumes)
        result = agent._volume_signal("TEST")
        assert result == 1.0

    def test_volume_signal_low_volume(self):
        agent = PaperTradingAgent(tickers=["TEST"])
        volumes = [1_000_000] * 20 + [300_000]
        agent._volume_cache["TEST"] = pd.Series(volumes)
        result = agent._volume_signal("TEST")
        assert result == -1.0

    def test_volume_signal_normal_volume(self):
        agent = PaperTradingAgent(tickers=["TEST"])
        volumes = [1_000_000] * 21
        agent._volume_cache["TEST"] = pd.Series(volumes)
        result = agent._volume_signal("TEST")
        assert result == 0.0

    def test_volume_signal_no_data(self):
        agent = PaperTradingAgent(tickers=["TEST"])
        result = agent._volume_signal("NONE")
        assert result == 0.0

    def test_volume_signal_short_series(self):
        agent = PaperTradingAgent(tickers=["TEST"])
        agent._volume_cache["TEST"] = pd.Series([100] * 5)
        result = agent._volume_signal("TEST")
        assert result == 0.0

    def test_volume_signal_moderate_high(self):
        agent = PaperTradingAgent(tickers=["TEST"])
        volumes = [1_000_000] * 20 + [1_300_000]
        agent._volume_cache["TEST"] = pd.Series(volumes)
        result = agent._volume_signal("TEST")
        assert result == 0.5

    def test_volume_signal_moderate_low(self):
        agent = PaperTradingAgent(tickers=["TEST"])
        volumes = [1_000_000] * 20 + [700_000]
        agent._volume_cache["TEST"] = pd.Series(volumes)
        result = agent._volume_signal("TEST")
        assert result == -0.5


class TestGreeksExposure:
    """Test greeks_exposure with real IV/ATR data."""

    def test_greeks_score_low_vol(self):
        from src.basket.models import AssetProfile
        from src.basket.scorer import BasketScorer

        assets = [
            AssetProfile(ticker="A", implied_vol=0.10, atr_pct=0.02),
            AssetProfile(ticker="B", implied_vol=0.12, atr_pct=0.03),
        ]
        scorer = BasketScorer()
        result = scorer._score_greeks_exposure(assets)
        assert result.raw_score >= 75

    def test_greeks_score_high_vol(self):
        from src.basket.models import AssetProfile
        from src.basket.scorer import BasketScorer

        assets = [
            AssetProfile(ticker="A", implied_vol=0.60, atr_pct=0.15),
            AssetProfile(ticker="B", implied_vol=0.70, atr_pct=0.20),
        ]
        scorer = BasketScorer()
        result = scorer._score_greeks_exposure(assets)
        assert result.raw_score <= 40

    def test_greeks_score_no_data(self):
        from src.basket.models import AssetProfile
        from src.basket.scorer import BasketScorer

        assets = [AssetProfile(ticker="A")]
        scorer = BasketScorer()
        result = scorer._score_greeks_exposure(assets)
        assert result.raw_score == 60


class TestCollectSignals:
    """Test that _collect_signals uses volume."""

    def test_all_8_signals_computed(self):
        agent = PaperTradingAgent(tickers=["TEST"])
        prices = pd.Series(np.random.lognormal(0, 0.02, 200).cumprod() * 100)
        agent._volume_cache["TEST"] = pd.Series(np.random.uniform(500_000, 1_500_000, 200))
        signals = agent._collect_signals("TEST", prices)

        assert "volume_confirmation" in signals
        assert "regime" in signals
        assert "rsi_oversold" in signals
        assert "sma_crossover" in signals
        assert len(signals) == 8

    def test_volume_not_zero(self):
        agent = PaperTradingAgent(tickers=["TEST"])
        prices = pd.Series(np.random.lognormal(0, 0.02, 200).cumprod() * 100)
        volumes = [1_000_000] * 199 + [2_500_000]
        agent._volume_cache["TEST"] = pd.Series(volumes)
        signals = agent._collect_signals("TEST", prices)
        assert signals["volume_confirmation"] != 0.0


class TestScheduler:
    """Test scheduler module."""

    def test_scheduler_init(self):
        from src.scheduler import FlyScheduler
        sched = FlyScheduler(tickers=["AAPL"])
        assert sched.tickers == ["AAPL"]

    def test_scheduler_history_empty(self):
        from src.scheduler import FlyScheduler
        sched = FlyScheduler(tickers=["TEST"])
        hist = sched.get_history()
        assert isinstance(hist, list)


class TestFeedbackLoop:
    """Test basket feedback loop."""

    def test_feedback_init(self):
        from src.basket.feedback import BasketFeedbackLoop
        loop = BasketFeedbackLoop()
        stats = loop.get_stats()
        assert "pending" in stats
        assert "completed" in stats
        assert "accuracy" in stats

    def test_feedback_score_and_track(self):
        from src.basket.feedback import BasketFeedbackLoop
        loop = BasketFeedbackLoop()
        result = loop.score_and_track(["AAPL", "MSFT", "GOOGL"])
        assert "tracking_id" in result
        assert "score" in result
        assert "grade" in result


class TestBootstrapHistorical:
    """Test bootstrap method exists and has correct signature."""

    def test_bootstrap_method_exists(self):
        agent = PaperTradingAgent(tickers=["TEST"])
        assert hasattr(agent, "bootstrap_historical")
        assert callable(agent.bootstrap_historical)
