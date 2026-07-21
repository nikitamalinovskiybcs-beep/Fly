"""Fly Strategy Library — pluggable trading strategies.

All strategies implement backtester.BaseStrategy and can be run through
the BacktestEngine or combined via EnsembleStrategy.
"""

from .breakout import BreakoutStrategy
from .carry import CarryStrategy
from .ensemble import EnsembleStrategy
from .mean_reversion import MeanReversionStrategy
from .momentum import MomentumStrategy
from .multi_factor import MultiFactorStrategy
from .pairs_trading import PairsTradingStrategy
from .risk_parity import RiskParityStrategy
from .sector_rotation import SectorRotationStrategy
from .trend_following import TrendFollowingStrategy
from .volatility_target import VolatilityTargetStrategy

__all__ = [
    "MomentumStrategy",
    "MeanReversionStrategy",
    "BreakoutStrategy",
    "TrendFollowingStrategy",
    "VolatilityTargetStrategy",
    "RiskParityStrategy",
    "SectorRotationStrategy",
    "PairsTradingStrategy",
    "MultiFactorStrategy",
    "CarryStrategy",
    "EnsembleStrategy",
]
