"""Tests for src.agents — paper trading agent and models."""

import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


class TestAgentModels:
    """Tests for paper trading data models."""

    def test_trade_action_enum(self) -> None:
        from src.agents.models import TradeAction
        assert TradeAction.BUY.value == "buy"
        assert TradeAction.SELL.value == "sell"
        assert TradeAction.HOLD.value == "hold"

    def test_paper_trade(self) -> None:
        from src.agents.models import PaperTrade, TradeAction
        trade = PaperTrade(id="t1", timestamp="2024-01-01", ticker="AAPL",
                          action=TradeAction.BUY, price=150.0, quantity=10.0)
        assert trade.ticker == "AAPL"
        assert trade.status == "open"

    def test_paper_position(self) -> None:
        from src.agents.models import PaperPosition
        pos = PaperPosition(ticker="MSFT", quantity=5.0, avg_entry_price=300.0)
        assert pos.unrealized_pnl == 0.0

    def test_paper_portfolio(self) -> None:
        from src.agents.models import PaperPortfolio
        portfolio = PaperPortfolio(cash=50000.0, total_value=100000.0)
        assert portfolio.total_pnl == 0.0

    def test_daily_snapshot(self) -> None:
        from src.agents.models import DailySnapshot
        snap = DailySnapshot(date="2024-01-01", portfolio_value=100000.0,
                             cash=50000.0, positions_value=50000.0)
        assert snap.daily_return == 0.0

    def test_paper_trading_stats(self) -> None:
        from src.agents.models import PaperTradingStats
        stats = PaperTradingStats()
        assert stats.total_trades == 0
        assert stats.win_rate == 0.0

    def test_learning_insight(self) -> None:
        from src.agents.models import LearningInsight
        insight = LearningInsight(insight_type="signal_accuracy",
                                  description="RSI accuracy improved")
        assert insight.confidence == 0.0


class TestPaperTradingAgent:
    """Tests for paper trading agent."""

    def setup_method(self) -> None:
        self.tmp = tempfile.mkdtemp()

    def teardown_method(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_init(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL", "MSFT"])
        agent.DATA_DIR = Path(self.tmp)
        assert len(agent.tickers) == 2
        assert agent._cash == 100000.0

    def test_signal_weights_default(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        weights = agent._signal_weights
        assert "regime" in weights
        assert "rsi_oversold" in weights
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01

    def test_make_decision_buy(self) -> None:
        from src.agents.models import TradeAction
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        signals = {k: 1.0 for k in agent._signal_weights}
        action, confidence = agent._make_decision(signals)
        assert action == TradeAction.BUY
        assert confidence > 0.3

    def test_make_decision_sell(self) -> None:
        from src.agents.models import TradeAction
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        signals = {k: -1.0 for k in agent._signal_weights}
        action, confidence = agent._make_decision(signals)
        assert action == TradeAction.SELL

    def test_make_decision_hold(self) -> None:
        from src.agents.models import TradeAction
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        signals = {k: 0.0 for k in agent._signal_weights}
        action, confidence = agent._make_decision(signals)
        assert action == TradeAction.HOLD

    def test_regime_signal_bull(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        returns = pd.Series([0.01] * 30)
        signal = agent._regime_signal(returns)
        assert signal == 1.0

    def test_regime_signal_bear(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        returns = pd.Series([-0.01] * 30)
        signal = agent._regime_signal(returns)
        assert signal == -1.0

    def test_sma_crossover_above(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        prices = pd.Series([100 + i * 0.5 for i in range(60)])
        signal = agent._sma_crossover_signal(prices)
        assert signal == 1.0

    def test_momentum_signal(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        prices = pd.Series([100 + i for i in range(35)])
        signal = agent._momentum_signal(prices)
        assert signal > 0

    def test_get_portfolio_initial(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        portfolio = agent.get_portfolio()
        assert portfolio.cash == 100000.0
        assert portfolio.total_value == 100000.0

    def test_get_stats_empty(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        stats = agent.get_stats()
        assert stats.total_trades == 0

    def test_equity_curve_empty(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        curve = agent.get_equity_curve()
        assert isinstance(curve, pd.DataFrame)

    def test_save_and_load_state(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        agent._save_state()
        assert (Path(self.tmp) / "portfolio.json").exists()
        assert (Path(self.tmp) / "config.json").exists()

    def test_execute_buy_trade(self) -> None:
        from src.agents.models import TradeAction
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        signals = {"regime": 1.0, "rsi_oversold": 0.5}
        trade = agent._execute_paper_trade("AAPL", TradeAction.BUY, 150.0, 0.7, signals)
        assert trade is not None
        assert trade.action == TradeAction.BUY
        assert trade.ticker == "AAPL"
        assert agent._cash < 100000.0
        assert "AAPL" in agent._positions

    def test_execute_sell_no_position(self) -> None:
        from src.agents.models import TradeAction
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        trade = agent._execute_paper_trade("AAPL", TradeAction.SELL, 150.0, 0.7, {})
        assert trade is None

    def test_weekly_learning_insufficient(self) -> None:
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        insights = agent.weekly_learning()
        assert len(insights) == 0

    def _closed_trade(self, sig_val: float, pnl: float):
        from datetime import datetime
        from src.agents.models import PaperTrade, TradeAction
        return PaperTrade(
            id="x", timestamp=datetime.now().isoformat(), ticker="AAPL",
            action=TradeAction.BUY, price=100.0, quantity=1.0,
            signals={"regime": sig_val}, confidence=0.5, pnl=pnl, pnl_pct=pnl,
            status="closed", closed_at=datetime.now().isoformat(),
        )

    def test_generation_increments_on_learning(self) -> None:
        """Generation grows only when learning actually produces insights."""
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        # Four winning trades where the 'regime' signal was correct → accuracy
        # 100% → weight increase insight → generation increments.
        agent._trades = [self._closed_trade(0.8, 50.0) for _ in range(4)]
        assert agent._generation == 0
        insights = agent.weekly_learning()
        assert len(insights) >= 1
        assert agent._generation == 1

    def test_generation_persists(self) -> None:
        """Generation survives save/load round-trips."""
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        agent._generation = 7
        agent._save_state()

        reloaded = PaperTradingAgent(tickers=["AAPL"])
        reloaded.DATA_DIR = Path(self.tmp)
        reloaded._load_state()
        assert reloaded._generation == 7

    def test_alpha_signal_in_collected_signals(self) -> None:
        """The Numerai alpha is wired into the signal set used for decisions."""
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["AAPL"])
        agent.DATA_DIR = Path(self.tmp)
        agent._alpha_cache = {"AAPL": 0.5}
        prices = pd.Series([100 + i * 0.2 for i in range(60)])
        signals = agent._collect_signals("AAPL", prices)
        assert "numerai_alpha" in signals
        assert signals["numerai_alpha"] == 0.5

    def test_compute_alpha_offline(self) -> None:
        """_compute_alpha returns bounded, non-fabricated values from prices."""
        from src.agents.paper_trader import PaperTradingAgent
        agent = PaperTradingAgent(tickers=["UP", "DOWN"])
        agent.DATA_DIR = Path(self.tmp)
        up = pd.Series([100 + i * 0.8 for i in range(130)])
        down = pd.Series([100 - i * 0.4 for i in range(130)])
        alpha = agent._compute_alpha({"UP": up, "DOWN": down})
        assert set(alpha) == {"UP", "DOWN"}
        assert all(-1.0 <= v <= 1.0 for v in alpha.values())
        assert alpha["UP"] > alpha["DOWN"]


class TestBaseAgent:
    """Tests for base agent abstract class."""

    def test_cannot_instantiate(self) -> None:
        from src.agents.base_agent import BaseAgent
        with pytest.raises(TypeError):
            BaseAgent()
