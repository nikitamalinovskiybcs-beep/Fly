"""Portfolio optimizer data models."""

from dataclasses import dataclass, field


@dataclass
class PortfolioAllocation:
    tickers: list[str]
    weights: dict[str, float]
    method: str
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    expected_sharpe: float = 0.0
    max_weight: float = 0.0
    min_weight: float = 0.0
    extra: dict = field(default_factory=dict)
