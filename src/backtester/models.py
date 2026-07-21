"""Backtester data models."""

from dataclasses import dataclass, field


@dataclass
class BacktestConfig:
    tickers: list[str]
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    commission_pct: float = 0.001  # 0.1%
    slippage_pct: float = 0.0005  # 0.05%
    max_position_pct: float = 0.20
    benchmark: str = "SPY"
    rebalance_freq: str = "daily"  # daily, weekly, monthly


@dataclass
class BacktestTrade:
    ticker: str
    entry_date: str
    exit_date: str
    side: str  # long/short
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    hold_days: int
    commission: float
    slippage: float


@dataclass
class BacktestResult:
    config: BacktestConfig
    total_return: float = 0.0
    cagr: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    max_drawdown: float = 0.0
    max_dd_duration_days: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_hold_days: float = 0.0
    benchmark_return: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    information_ratio: float = 0.0
    equity_curve: list[dict] = field(default_factory=list)
    monthly_returns: dict = field(default_factory=dict)
    trades: list[BacktestTrade] = field(default_factory=list)
