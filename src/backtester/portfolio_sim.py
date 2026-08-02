"""Portfolio simulator — tracks state during a backtest."""

from .models import BacktestTrade


class PortfolioSimulator:
    """Tracks cash, positions, equity history, and closed trades."""

    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        # {ticker: {size, avg_price, entry_date, commission, slippage}}
        self.positions: dict[str, dict] = {}
        self.equity_history: list[dict] = []
        self.trades: list[BacktestTrade] = []

    def buy(self, ticker: str, price: float, size: float, date: str, commission: float, slippage: float) -> bool:
        cost = price * size + commission
        if size <= 0 or cost > self.cash:
            return False
        self.cash -= cost
        pos = self.positions.get(ticker)
        if pos is None:
            self.positions[ticker] = {
                "size": size,
                "avg_price": price,
                "entry_date": date,
                "commission": commission,
                "slippage": slippage,
            }
        else:
            total = pos["size"] + size
            pos["avg_price"] = (pos["avg_price"] * pos["size"] + price * size) / total
            pos["size"] = total
            pos["commission"] += commission
            pos["slippage"] += slippage
        return True

    def sell(self, ticker: str, price: float, size: float, date: str, commission: float, slippage: float) -> bool:
        pos = self.positions.get(ticker)
        if pos is None or size <= 0:
            return False
        size = min(size, pos["size"])
        proceeds = price * size - commission
        self.cash += proceeds
        entry_price = pos["avg_price"]
        gross = (price - entry_price) * size
        total_commission = commission + pos["commission"] * (size / pos["size"])
        total_slippage = slippage + pos["slippage"] * (size / pos["size"])
        pnl = gross - total_commission
        pnl_pct = (price / entry_price - 1) * 100 if entry_price else 0.0
        self.trades.append(
            BacktestTrade(
                ticker=ticker,
                entry_date=pos["entry_date"],
                exit_date=date,
                side="long",
                entry_price=entry_price,
                exit_price=price,
                size=size,
                pnl=pnl,
                pnl_pct=pnl_pct,
                hold_days=_days_between(pos["entry_date"], date),
                commission=total_commission,
                slippage=total_slippage,
            )
        )
        pos["size"] -= size
        if pos["size"] <= 1e-9:
            del self.positions[ticker]
        else:
            pos["commission"] *= 1 - (size / (pos["size"] + size))
            pos["slippage"] *= 1 - (size / (pos["size"] + size))
        return True

    def get_value(self, prices: dict[str, float]) -> float:
        value = self.cash
        for ticker, pos in self.positions.items():
            px = prices.get(ticker, pos["avg_price"])
            value += px * pos["size"]
        return value

    def mark_to_market(self, prices: dict[str, float], date: str) -> None:
        value = self.get_value(prices)
        peak = max([e["value"] for e in self.equity_history] + [value]) if self.equity_history else value
        drawdown = (value / peak - 1) * 100 if peak else 0.0
        self.equity_history.append({"date": date, "value": value, "drawdown": drawdown})

    def get_positions(self) -> dict:
        return self.positions


def _days_between(start: str, end: str) -> int:
    import datetime as _dt

    try:
        d0 = _dt.date.fromisoformat(start[:10])
        d1 = _dt.date.fromisoformat(end[:10])
        return (d1 - d0).days
    except Exception:  # noqa: BLE001
        return 0
