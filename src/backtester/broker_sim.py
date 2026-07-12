"""Simulated broker — realistic fills with slippage and commission."""


class SimulatedBroker:
    """Simulates order execution with slippage and commission."""

    def __init__(self, commission_pct: float = 0.001, slippage_pct: float = 0.0005):
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct

    def execute_buy(self, price: float, size: float) -> tuple[float, float, float]:
        """Return (fill_price, commission, slippage_cost)."""
        fill_price = price * (1 + self.slippage_pct)
        slippage_cost = (fill_price - price) * size
        commission = fill_price * size * self.commission_pct
        return fill_price, commission, slippage_cost

    def execute_sell(self, price: float, size: float) -> tuple[float, float, float]:
        """Return (fill_price, commission, slippage_cost)."""
        fill_price = price * (1 - self.slippage_pct)
        slippage_cost = (price - fill_price) * size
        commission = fill_price * size * self.commission_pct
        return fill_price, commission, slippage_cost
