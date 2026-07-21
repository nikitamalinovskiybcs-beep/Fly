"""Pydantic-free data models for Autopilot Agent.

Uses dataclasses instead of Pydantic to keep dependencies minimal.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    STOPPED = "stopped"


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class HealthReport:
    """Snapshot of system health from Monitor."""
    timestamp: datetime
    status: HealthStatus
    sharpe_30d: float
    win_rate_20: float
    max_drawdown: float
    open_positions: int
    signals_quality: float
    data_freshness_hours: float
    disk_usage_pct: float
    alerts: list[dict] = field(default_factory=list)


@dataclass
class AnalysisInsight:
    """One finding from Analyzer."""
    timestamp: datetime
    category: str
    finding: str
    metric_name: str
    metric_value: float
    recommendation: str
    confidence: float
    priority: str


@dataclass
class ParameterChange:
    """Proposed or deployed parameter change."""
    parameter_name: str
    current_value: float
    proposed_value: float
    change_pct: float
    reason: str
    backtest_sharpe_before: float
    backtest_sharpe_after: float
    improvement_pct: float
    pbo_score: float
    walk_forward_pass: bool
    status: str = "proposed"


@dataclass
class DeploymentResult:
    """Result of deploying a parameter change."""
    timestamp: datetime
    parameter_name: str
    old_value: float
    new_value: float
    trial_trades: int
    trial_sharpe: float
    trial_win_rate: float
    accepted: bool
    rollback_reason: Optional[str] = None


@dataclass
class DailyReport:
    """Daily summary for Reporter."""
    date: str
    pnl_today: float
    pnl_total: float
    trades_today: int
    wins_today: int
    losses_today: int
    sharpe_30d: float
    max_dd: float
    changes_today: list[ParameterChange] = field(default_factory=list)
    alerts_today: list[dict] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
