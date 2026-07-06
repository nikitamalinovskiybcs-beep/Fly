"""Paper trading data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TradeAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class PaperTrade:
    id: str
    timestamp: str
    ticker: str
    action: TradeAction
    price: float
    quantity: float
    reason: str = ""
    signals: dict = field(default_factory=dict)
    regime: str = "unknown"
    confidence: float = 0.0
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    status: str = "open"
    closed_at: Optional[str] = None


@dataclass
class PaperPosition:
    ticker: str
    quantity: float
    avg_entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    entry_date: str = ""
    days_held: int = 0


@dataclass
class PaperPortfolio:
    cash: float
    positions: list[PaperPosition] = field(default_factory=list)
    total_value: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0


@dataclass
class DailySnapshot:
    date: str
    portfolio_value: float
    cash: float
    positions_value: float
    daily_return: float = 0.0
    cumulative_return: float = 0.0
    drawdown: float = 0.0
    num_positions: int = 0


@dataclass
class PaperTradingStats:
    start_date: str = ""
    end_date: str = ""
    total_days: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration_days: int = 0
    calmar_ratio: float = 0.0
    total_return: float = 0.0
    annualized_return: float = 0.0
    best_day: float = 0.0
    worst_day: float = 0.0
    avg_holding_period_days: float = 0.0
    kelly_optimal: float = 0.0


@dataclass
class LearningInsight:
    insight_type: str
    description: str
    metric_before: float = 0.0
    metric_after: float = 0.0
    recommendation: str = ""
    confidence: float = 0.0
