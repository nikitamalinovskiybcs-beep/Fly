"""Tests for the strategy library."""

import numpy as np
import pandas as pd
import pytest

from src.feature_store.models import FeatureVector
from src.strategies import (
    BreakoutStrategy,
    CarryStrategy,
    EnsembleStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    MultiFactorStrategy,
    PairsTradingStrategy,
    RiskParityStrategy,
    SectorRotationStrategy,
    TrendFollowingStrategy,
    VolatilityTargetStrategy,
)

ALL_SINGLE = [
    MomentumStrategy,
    MeanReversionStrategy,
    BreakoutStrategy,
    TrendFollowingStrategy,
    VolatilityTargetStrategy,
    RiskParityStrategy,
    SectorRotationStrategy,
    MultiFactorStrategy,
    CarryStrategy,
]


def _features():
    return {
        "AAPL": FeatureVector(
            ticker="AAPL", date="2025-01-01", rsi_14=45.0, sma_50=180.0, sma_200=170.0,
            momentum_30d=8.0, distance_to_sma50_pct=2.0, distance_to_sma200_pct=6.0,
            volume_ratio_20d=1.6, adx_14=30.0, volatility_30d=18.0, bollinger_pct_b=0.4,
            momentum_10d=3.0, regime="bull",
        ),
        "XOM": FeatureVector(
            ticker="XOM", date="2025-01-01", rsi_14=75.0, sma_50=100.0, sma_200=110.0,
            momentum_30d=-6.0, distance_to_sma50_pct=-3.0, distance_to_sma200_pct=-12.0,
            volume_ratio_20d=0.7, adx_14=15.0, volatility_30d=35.0, bollinger_pct_b=1.1,
            momentum_10d=-2.0, regime="bear",
        ),
        "KO": FeatureVector(
            ticker="KO", date="2025-01-01", rsi_14=28.0, sma_50=60.0, sma_200=60.0,
            momentum_30d=1.0, distance_to_sma50_pct=-1.0, distance_to_sma200_pct=-11.0,
            volume_ratio_20d=1.0, adx_14=20.0, volatility_30d=12.0, bollinger_pct_b=-0.1,
            momentum_10d=0.5, regime="sideways",
        ),
    }


class TestSingleStrategies:
    @pytest.mark.parametrize("cls", ALL_SINGLE)
    def test_signals_in_range(self, cls):
        strat = cls()
        signals = strat.generate_signals({}, _features(), "2025-01-01")
        assert isinstance(strat.name(), str)
        for ticker, sig in signals.items():
            assert -1.0 <= sig <= 1.0, f"{cls.__name__} {ticker}={sig}"

    def test_momentum_no_buy_in_bear(self):
        signals = MomentumStrategy().generate_signals({}, _features(), "2025-01-01")
        assert signals["XOM"] == 0.0  # bear regime -> no long

    def test_mean_reversion_buys_oversold(self):
        signals = MeanReversionStrategy().generate_signals({}, _features(), "2025-01-01")
        assert signals["KO"] > 0  # RSI 28, below SMA200 -> buy

    def test_trend_following_direction(self):
        signals = TrendFollowingStrategy().generate_signals({}, _features(), "2025-01-01")
        assert signals["AAPL"] > 0  # sma50 > sma200 + adx>25
        assert signals["XOM"] < 0  # sma50 < sma200

    def test_risk_parity_weights_positive(self):
        signals = RiskParityStrategy().generate_signals({}, _features(), "2025-01-01")
        assert all(s >= 0 for s in signals.values())

    def test_position_size_default(self):
        size = MomentumStrategy().position_size("AAPL", 0.5, 100000, 100.0, 0.20)
        assert size == pytest.approx(100000 * 0.20 * 0.5 / 100.0)

    def test_position_size_zero_price(self):
        assert MomentumStrategy().position_size("AAPL", 0.5, 100000, 0.0) == 0.0


class TestEnsemble:
    def test_default_construction(self):
        ens = EnsembleStrategy()
        assert ens.name() == "Ensemble"
        assert len(ens.strategies) == 8

    def test_weighted_signals_in_range(self):
        signals = EnsembleStrategy().generate_signals({}, _features(), "2025-01-01")
        for sig in signals.values():
            assert -1.0 <= sig <= 1.0

    def test_custom_weights(self):
        ens = EnsembleStrategy(strategies=[MomentumStrategy()], weights={"Momentum": 1.0})
        signals = ens.generate_signals({}, _features(), "2025-01-01")
        mom = MomentumStrategy().generate_signals({}, _features(), "2025-01-01")
        assert signals["AAPL"] == pytest.approx(mom["AAPL"])


class TestPairsTrading:
    def test_pairs_no_crash_and_range(self):
        rng = np.random.default_rng(0)
        idx = pd.bdate_range("2023-01-01", periods=120)
        base = np.cumsum(rng.standard_normal(120)) + 100
        data = {
            "AAPL": pd.DataFrame({"Close": pd.Series(base, index=idx)}),
            "MSFT": pd.DataFrame({"Close": pd.Series(base + rng.standard_normal(120) * 0.5, index=idx)}),
        }
        signals = PairsTradingStrategy().generate_signals(data, {}, "2023-06-01")
        for sig in signals.values():
            assert -1.0 <= sig <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
