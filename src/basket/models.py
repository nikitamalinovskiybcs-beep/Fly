"""Basket scoring data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BasketGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B_PLUS = "B+"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


@dataclass
class RedFlag:
    severity: str
    asset: str
    flag_type: str
    description: str
    value: float = 0.0


@dataclass
class AssetProfile:
    ticker: str
    price: float = 0.0
    market_cap: float = 0.0
    pe_ratio: Optional[float] = None
    net_margin: Optional[float] = None
    is_profitable: bool = True
    daily_volume_usd: float = 0.0
    atr_pct: float = 0.0
    evt_var_95: float = 0.0
    max_drawdown_60d: float = 0.0
    sector: str = "Unknown"
    distance_to_strike_pct: Optional[float] = None
    distance_to_barrier_pct: Optional[float] = None
    implied_vol: Optional[float] = None
    iv_skew: Optional[float] = None
    rsi: Optional[float] = None
    red_flags: list[RedFlag] = field(default_factory=list)


@dataclass
class CriterionScore:
    name: str
    weight: float
    raw_score: float
    weighted_score: float
    details: str = ""


@dataclass
class BasketReport:
    basket_name: str
    tickers: list[str]
    date: str = ""
    assets: list[AssetProfile] = field(default_factory=list)
    criteria: list[CriterionScore] = field(default_factory=list)
    total_score: float = 0.0
    grade: BasketGrade = BasketGrade.C
    red_flags: list[RedFlag] = field(default_factory=list)
    red_flag_count: int = 0
    worst_of_asset: str = ""
    worst_of_reason: str = ""
    autocall_probability: Optional[dict[str, float]] = None
    greeks: Optional[dict] = None
    recommendation: str = ""


@dataclass
class EvolutionLog:
    timestamp: str
    old_weights: dict[str, float] = field(default_factory=dict)
    new_weights: dict[str, float] = field(default_factory=dict)
    trigger: str = ""
    basket_tickers: list[str] = field(default_factory=list)
    actual_outcome: str = ""
    predicted_outcome: str = ""
    prediction_correct: bool = False
    score_error: float = 0.0
