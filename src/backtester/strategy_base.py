"""Base strategy interface. All strategies implement this."""

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    """All strategies must implement this interface."""

    @abstractmethod
    def name(self) -> str:
        """Strategy name."""

    @abstractmethod
    def generate_signals(
        self,
        data: dict[str, pd.DataFrame],
        features: dict,
        date: str,
    ) -> dict[str, float]:
        """Generate signals for all tickers on a given date.

        Return {ticker: signal} where signal in [-1, +1]:
        +1 strong buy, -1 strong sell, 0 hold/no signal.
        """

    def position_size(
        self,
        ticker: str,
        signal: float,
        portfolio_value: float,
        current_price: float,
        max_position_pct: float = 0.20,
    ) -> float:
        """Calculate position size in shares. Return 0 to skip.

        Default: allocate (|signal| * max_position_pct) of portfolio.
        """
        if current_price <= 0 or signal == 0:
            return 0.0
        alloc = portfolio_value * max_position_pct * min(abs(signal), 1.0)
        return float(alloc / current_price)

    def on_trade(self, trade) -> None:
        """Optional callback when a trade is executed."""
