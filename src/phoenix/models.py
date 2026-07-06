"""Phoenix analytics data models — dataclasses for Greeks, vol, barrier risk."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GreeksReport:
    """Greeks for a single asset in a Phoenix/Autocall product."""

    ticker: str
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    barrier_delta: float
    digital_risk: float


@dataclass
class VolPoint:
    """Single point on a volatility surface."""

    strike: float
    expiry_days: int
    iv: float


@dataclass
class VolSurface:
    """Implied volatility surface for a ticker."""

    ticker: str
    atm_iv: float
    skew_25d: float
    term_structure: list[VolPoint] = field(default_factory=list)
    iv_percentile_1y: float = 0.5


@dataclass
class ImpliedCorrelationResult:
    """Implied vs realized correlation analysis."""

    realized_correlation: float
    implied_correlation: float
    correlation_risk_premium: float
    is_overpriced: bool


@dataclass
class BarrierRiskReport:
    """Barrier-specific risk analysis for worst-of products."""

    ticker: str
    spot: float
    barrier: float
    distance_pct: float
    barrier_delta: float
    gap_risk_overnight: float
    digital_risk_pct: float
    time_to_barrier_days: Optional[float] = None


@dataclass
class PhoenixPricingResult:
    """MC pricing result for a Phoenix/Autocall product."""

    fair_value_pct: float
    market_price_pct: Optional[float] = None
    edge_pct: Optional[float] = None
    autocall_probabilities: dict[str, float] = field(default_factory=dict)
    expected_coupon_payments: int = 0
    expected_life_years: float = 0.0
    worst_of_asset: str = ""
    worst_of_prob: float = 0.0


@dataclass
class DividendForecast:
    """Dividend analysis and barrier impact."""

    ticker: str
    current_yield: float
    forward_yield: float
    ex_dates_next_12m: list[str] = field(default_factory=list)
    impact_on_barrier_pct: float = 0.0
