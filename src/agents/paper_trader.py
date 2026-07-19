"""Paper trading agent — execute, record, learn, evolve.

Architecture:
1. SIGNAL COLLECTION: aggregate signals (regime, RSI, SMA, momentum, EVT)
2. DECISION ENGINE: weighted voting → action
3. EXECUTION: paper trades with realistic slippage/commission
4. RECORDING: trades + daily snapshots → Storage layer
5. LEARNING: weekly analysis → weight adjustment
6. EVOLUTION: monthly reoptimization via scipy.optimize
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.agents.models import (
    DailySnapshot,
    LearningInsight,
    PaperPortfolio,
    PaperPosition,
    PaperTrade,
    PaperTradingStats,
    TradeAction,
)

logger = logging.getLogger(__name__)


class PaperTradingAgent:
    """Paper trading agent with self-learning signal weights."""

    DATA_DIR = Path("data/paper_trading")
    INITIAL_CASH = 100_000.0
    COMMISSION_PCT = 0.001
    SLIPPAGE_PCT = 0.0005
    MAX_POSITION_PCT = 0.20

    DEFAULT_SIGNAL_WEIGHTS = {
        "regime": 0.15,
        "rsi_oversold": 0.10,
        "rsi_overbought": 0.10,
        "sma_crossover": 0.13,
        "evt_var_safe": 0.10,
        "momentum_30d": 0.12,
        "mean_reversion": 0.08,
        "volume_confirmation": 0.10,
        "numerai_alpha": 0.12,
    }

    def __init__(
        self,
        tickers: list[str],
        initial_cash: float = 100_000.0,
    ) -> None:
        self.tickers = tickers
        self.INITIAL_CASH = initial_cash

        self._trades: list[PaperTrade] = []
        self._positions: dict[str, PaperPosition] = {}
        self._cash: float = initial_cash
        self._snapshots: list[DailySnapshot] = []
        self._signal_weights: dict[str, float] = dict(self.DEFAULT_SIGNAL_WEIGHTS)
        self._insights: list[LearningInsight] = []

        self._volume_cache: dict[str, pd.Series] = {}
        self._alpha_cache: dict[str, float] = {}
        self._generation: int = 0

        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._load_state()

    def run_daily(self) -> list[PaperTrade]:
        """Main daily loop: collect signals, decide, execute, record.

        Returns:
            List of trades executed today.
        """
        today_trades: list[PaperTrade] = []
        prices = self._fetch_prices()
        self._alpha_cache = self._compute_alpha(prices)

        for ticker in self.tickers:
            if ticker not in prices or prices[ticker] is None:
                continue

            price_series = prices[ticker]
            current_price = float(price_series.iloc[-1]) if len(price_series) > 0 else 0
            if current_price <= 0:
                continue

            signals = self._collect_signals(ticker, price_series)
            action, confidence = self._make_decision(signals)

            if action == TradeAction.HOLD:
                continue

            trade = self._execute_paper_trade(
                ticker, action, current_price, confidence, signals,
            )
            if trade:
                today_trades.append(trade)

        self._update_positions(prices)
        self._record_snapshot(prices)
        self._save_state()

        now = datetime.now()
        if now.weekday() == 6:
            self.weekly_learning()
        if now.day == 1:
            self.monthly_evolution()

        return today_trades

    def _collect_signals(self, ticker: str, prices: pd.Series) -> dict[str, float]:
        """Collect all signals for a ticker. Each returns -1 to +1.

        Args:
            ticker: Ticker symbol.
            prices: Historical price series.

        Returns:
            Dict of signal_name → value in [-1, +1].
        """
        signals: dict[str, float] = {}

        if len(prices) < 2:
            return {k: 0.0 for k in self._signal_weights}

        returns = prices.pct_change().dropna()

        signals["regime"] = self._regime_signal(returns)
        signals["rsi_oversold"] = self._rsi_signal(prices, oversold=True)
        signals["rsi_overbought"] = self._rsi_signal(prices, oversold=False)
        signals["sma_crossover"] = self._sma_crossover_signal(prices)
        signals["evt_var_safe"] = self._evt_var_signal(returns)
        signals["momentum_30d"] = self._momentum_signal(prices, period=30)
        signals["mean_reversion"] = self._mean_reversion_signal(prices)
        signals["volume_confirmation"] = self._volume_signal(ticker)
        signals["numerai_alpha"] = self._alpha_cache.get(ticker, 0.0)

        return signals

    def _compute_alpha(
        self, prices: dict[str, Optional[pd.Series]],
    ) -> dict[str, float]:
        """Cross-sectional Numerai-style alpha over the current basket.

        Delegates to NumeraiIntegration.extract_alpha_signals with the price
        history we already fetched (no extra network I/O).
        """
        history = {t: s for t, s in prices.items() if s is not None}
        if len(history) < 2:
            return {}
        try:
            from src.integrations.numerai import NumeraiIntegration
            return NumeraiIntegration().extract_alpha_signals(
                list(history.keys()), price_history=history,
            )
        except Exception as exc:
            logger.info("Alpha computation skipped: %s", exc)
            return {}

    def _make_decision(self, signals: dict[str, float]) -> tuple[TradeAction, float]:
        """Weighted vote: composite = Σ(signal × weight).

        Args:
            signals: Signal dict.

        Returns:
            (action, confidence).
        """
        composite = 0.0
        for name, value in signals.items():
            weight = self._signal_weights.get(name, 0.0)
            composite += value * weight

        confidence = min(abs(composite), 1.0)

        if composite > 0.3:
            return TradeAction.BUY, confidence
        if composite < -0.3:
            return TradeAction.SELL, confidence
        return TradeAction.HOLD, confidence

    def _execute_paper_trade(
        self,
        ticker: str,
        action: TradeAction,
        price: float,
        confidence: float,
        signals: dict,
    ) -> Optional[PaperTrade]:
        """Execute a paper trade with commission and slippage.

        Args:
            ticker: Ticker.
            action: Buy or sell.
            price: Current market price.
            confidence: Decision confidence.
            signals: Signal snapshot.

        Returns:
            PaperTrade or None if cannot execute.
        """
        trade_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        if action == TradeAction.BUY:
            if ticker in self._positions:
                return None

            portfolio_value = self._portfolio_value()
            max_spend = portfolio_value * self.MAX_POSITION_PCT
            effective_price = price * (1 + self.COMMISSION_PCT + self.SLIPPAGE_PCT)
            quantity = min(max_spend, self._cash) / effective_price

            if quantity < 0.01 or self._cash < effective_price:
                return None

            cost = quantity * effective_price
            self._cash -= cost

            self._positions[ticker] = PaperPosition(
                ticker=ticker,
                quantity=quantity,
                avg_entry_price=price,
                current_price=price,
                entry_date=now,
            )

            trade = PaperTrade(
                id=trade_id, timestamp=now, ticker=ticker,
                action=action, price=price, quantity=quantity,
                reason=f"composite_score={confidence:.3f}",
                signals=signals, confidence=confidence,
            )
            self._trades.append(trade)
            return trade

        if action == TradeAction.SELL:
            pos = self._positions.get(ticker)
            if not pos:
                return None

            effective_price = price * (1 - self.COMMISSION_PCT - self.SLIPPAGE_PCT)
            proceeds = pos.quantity * effective_price
            self._cash += proceeds

            pnl = (effective_price - pos.avg_entry_price) * pos.quantity
            pnl_pct = (effective_price / pos.avg_entry_price - 1) * 100

            trade = PaperTrade(
                id=trade_id, timestamp=now, ticker=ticker,
                action=action, price=price, quantity=pos.quantity,
                reason=f"composite_score={confidence:.3f}",
                signals=signals, confidence=confidence,
                pnl=round(pnl, 2), pnl_pct=round(pnl_pct, 2),
                status="closed", closed_at=now,
            )
            self._trades.append(trade)
            del self._positions[ticker]
            return trade

        return None

    def get_portfolio(self) -> PaperPortfolio:
        """Current portfolio state."""
        positions = list(self._positions.values())
        positions_value = sum(p.quantity * p.current_price for p in positions)
        total = self._cash + positions_value
        initial = self.INITIAL_CASH

        return PaperPortfolio(
            cash=round(self._cash, 2),
            positions=positions,
            total_value=round(total, 2),
            total_pnl=round(total - initial, 2),
            total_pnl_pct=round((total / initial - 1) * 100, 2) if initial > 0 else 0,
        )

    def get_stats(self) -> PaperTradingStats:
        """Calculate performance statistics from trade history."""
        closed = [t for t in self._trades if t.status == "closed"]
        if not closed:
            return PaperTradingStats()

        wins = [t for t in closed if (t.pnl or 0) > 0]
        losses = [t for t in closed if (t.pnl or 0) <= 0]

        win_rate = len(wins) / len(closed) if closed else 0
        avg_win = float(np.mean([t.pnl for t in wins])) if wins else 0
        avg_loss = float(np.mean([abs(t.pnl) for t in losses])) if losses else 0

        total_wins = sum(t.pnl for t in wins) if wins else 0
        total_losses = sum(abs(t.pnl) for t in losses) if losses else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        daily_returns = self._daily_returns()
        sharpe = self._calc_sharpe(daily_returns)
        sortino = self._calc_sortino(daily_returns)
        max_dd = self._calc_max_drawdown(daily_returns)

        total_return = (self._portfolio_value() / self.INITIAL_CASH - 1) * 100
        n_days = max(len(self._snapshots), 1)
        ann_return = total_return * (252 / n_days) if n_days > 0 else 0

        return PaperTradingStats(
            start_date=closed[0].timestamp if closed else "",
            end_date=closed[-1].timestamp if closed else "",
            total_days=n_days,
            total_trades=len(closed),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=round(win_rate, 4),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            profit_factor=round(profit_factor, 2),
            sharpe_ratio=round(sharpe, 4),
            sortino_ratio=round(sortino, 4),
            max_drawdown=round(max_dd, 4),
            total_return=round(total_return, 2),
            annualized_return=round(ann_return, 2),
        )

    def get_equity_curve(self) -> pd.DataFrame:
        """Return daily portfolio value series."""
        if not self._snapshots:
            return pd.DataFrame(columns=["date", "value"])
        data = [{"date": s.date, "value": s.portfolio_value} for s in self._snapshots]
        return pd.DataFrame(data)

    def weekly_learning(self) -> list[LearningInsight]:
        """Analyze last 7 days and adjust signal weights.

        Returns:
            List of insights discovered.
        """
        insights: list[LearningInsight] = []
        recent_trades = [
            t for t in self._trades
            if t.status == "closed"
            and t.closed_at
            and t.closed_at >= (datetime.now() - timedelta(days=7)).isoformat()
        ]

        if len(recent_trades) < 3:
            return insights

        for signal_name in self._signal_weights:
            correct = 0
            total = 0
            for trade in recent_trades:
                sig_val = trade.signals.get(signal_name, 0)
                pnl = trade.pnl or 0
                if abs(sig_val) > 0.1:
                    total += 1
                    if (sig_val > 0 and pnl > 0) or (sig_val < 0 and pnl < 0):
                        correct += 1

            if total < 2:
                continue

            accuracy = correct / total
            old_weight = self._signal_weights[signal_name]

            if accuracy > 0.60:
                new_weight = min(old_weight + 0.02, 0.35)
                insights.append(LearningInsight(
                    insight_type="signal_accuracy",
                    description=f"{signal_name}: accuracy {accuracy:.0%} → increase weight",
                    metric_before=old_weight, metric_after=new_weight,
                    recommendation="increase", confidence=accuracy,
                ))
            elif accuracy < 0.40:
                new_weight = max(old_weight - 0.02, 0.05)
                insights.append(LearningInsight(
                    insight_type="signal_accuracy",
                    description=f"{signal_name}: accuracy {accuracy:.0%} → decrease weight",
                    metric_before=old_weight, metric_after=new_weight,
                    recommendation="decrease", confidence=1 - accuracy,
                ))
            else:
                new_weight = old_weight

            self._signal_weights[signal_name] = new_weight

        total_w = sum(self._signal_weights.values())
        if total_w > 0:
            self._signal_weights = {k: v / total_w for k, v in self._signal_weights.items()}

        if insights:
            self._generation += 1

        self._insights.extend(insights)
        self._save_state()
        return insights

    def monthly_evolution(self) -> dict:
        """Full weight reoptimization using last 3 months of data.

        Returns:
            Dict with old_weights, new_weights, sharpe_improvement.
        """
        closed = [t for t in self._trades if t.status == "closed"]
        if len(closed) < 20:
            return {"status": "insufficient_data", "trades": len(closed)}

        old_weights = dict(self._signal_weights)

        try:
            from scipy.optimize import minimize

            def neg_sharpe(weights_arr: np.ndarray) -> float:
                w = dict(zip(self._signal_weights.keys(), weights_arr))
                pnls = []
                for trade in closed[-90:]:
                    composite = sum(trade.signals.get(k, 0) * w.get(k, 0) for k in w)
                    pnls.append(composite * (trade.pnl or 0))
                pnls_arr = np.array(pnls)
                if pnls_arr.std() == 0:
                    return 0
                return -float(pnls_arr.mean() / pnls_arr.std())

            n = len(self._signal_weights)
            x0 = np.array(list(self._signal_weights.values()))
            bounds = [(0.05, 0.35)] * n
            constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

            result = minimize(neg_sharpe, x0, method="SLSQP",
                              bounds=bounds, constraints=constraints)

            if result.success:
                new_sharpe = -result.fun
                old_sharpe = -neg_sharpe(x0)

                if new_sharpe > old_sharpe + 0.1:
                    self._signal_weights = dict(zip(
                        self._signal_weights.keys(), result.x.tolist(),
                    ))
                    self._generation += 1
                    self._save_state()
                    return {
                        "old_weights": old_weights,
                        "new_weights": dict(self._signal_weights),
                        "sharpe_improvement": round(new_sharpe - old_sharpe, 4),
                        "generation": self._generation,
                    }

            return {"status": "no_improvement"}
        except ImportError:
            return {"status": "scipy_not_available"}

    def _fetch_prices(self) -> dict[str, Optional[pd.Series]]:
        """Fetch latest prices for all tickers."""
        result: dict[str, Optional[pd.Series]] = {}
        try:
            import yfinance as yf
            for ticker in self.tickers:
                hist = yf.Ticker(ticker).history(period="6mo")
                if not hist.empty:
                    result[ticker] = hist["Close"]
                    self._volume_cache[ticker] = hist["Volume"]
                else:
                    result[ticker] = None
        except Exception as exc:
            logger.warning("Price fetch failed: %s", exc)
        return result

    def _update_positions(self, prices: dict) -> None:
        """Update current prices for all positions."""
        for ticker, pos in self._positions.items():
            if ticker in prices and prices[ticker] is not None:
                series = prices[ticker]
                if len(series) > 0:
                    pos.current_price = float(series.iloc[-1])
                    pos.unrealized_pnl = (pos.current_price - pos.avg_entry_price) * pos.quantity
                    pos.unrealized_pnl_pct = (
                        (pos.current_price / pos.avg_entry_price - 1) * 100
                        if pos.avg_entry_price > 0 else 0
                    )

    def _record_snapshot(self, prices: dict) -> None:
        """Record daily portfolio snapshot."""
        portfolio = self.get_portfolio()
        prev_value = self._snapshots[-1].portfolio_value if self._snapshots else self.INITIAL_CASH
        daily_ret = (portfolio.total_value / prev_value - 1) if prev_value > 0 else 0

        snap = DailySnapshot(
            date=datetime.now().strftime("%Y-%m-%d"),
            portfolio_value=portfolio.total_value,
            cash=portfolio.cash,
            positions_value=portfolio.total_value - portfolio.cash,
            daily_return=round(daily_ret, 6),
            cumulative_return=round(portfolio.total_pnl_pct, 4),
            num_positions=len(portfolio.positions),
        )
        self._snapshots.append(snap)

    def _portfolio_value(self) -> float:
        """Total portfolio value."""
        pos_val = sum(p.quantity * p.current_price for p in self._positions.values())
        return self._cash + pos_val

    def _daily_returns(self) -> np.ndarray:
        """Extract daily returns from snapshots."""
        if not self._snapshots:
            return np.array([])
        return np.array([s.daily_return for s in self._snapshots])

    def _calc_sharpe(self, returns: np.ndarray) -> float:
        if len(returns) < 2 or returns.std() == 0:
            return 0.0
        return float(returns.mean() / returns.std() * np.sqrt(252))

    def _calc_sortino(self, returns: np.ndarray) -> float:
        if len(returns) < 2:
            return 0.0
        downside = returns[returns < 0]
        if len(downside) == 0 or downside.std() == 0:
            return 0.0
        return float(returns.mean() / downside.std() * np.sqrt(252))

    def _calc_max_drawdown(self, returns: np.ndarray) -> float:
        if len(returns) < 2:
            return 0.0
        cumulative = np.cumprod(1 + returns)
        peak = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - peak) / peak
        return float(drawdowns.min()) if len(drawdowns) > 0 else 0.0

    # ── Signal implementations ──

    def _regime_signal(self, returns: pd.Series) -> float:
        """Regime signal: +1 bull, 0 sideways, -1 bear."""
        if len(returns) < 20:
            return 0.0
        recent = returns.iloc[-20:]
        mean_ret = float(recent.mean())
        if mean_ret > 0.001:
            return 1.0
        if mean_ret < -0.001:
            return -1.0
        return 0.0

    def _rsi_signal(self, prices: pd.Series, oversold: bool = True) -> float:
        """RSI signal."""
        if len(prices) < 15:
            return 0.0
        delta = prices.diff().dropna()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - 100 / (1 + rs)
        current_rsi = float(rsi.iloc[-1]) if not rsi.empty and not np.isnan(rsi.iloc[-1]) else 50

        if oversold:
            if current_rsi < 30:
                return 1.0
            if current_rsi < 40:
                return 0.5
            return 0.0
        else:
            if current_rsi > 70:
                return -1.0
            if current_rsi > 60:
                return -0.5
            return 0.0

    def _sma_crossover_signal(self, prices: pd.Series) -> float:
        """SMA crossover: +1 if price > SMA50, -1 if below."""
        if len(prices) < 50:
            return 0.0
        sma50 = float(prices.rolling(50).mean().iloc[-1])
        current = float(prices.iloc[-1])
        if current > sma50 * 1.02:
            return 1.0
        if current < sma50 * 0.98:
            return -1.0
        return 0.0

    def _evt_var_signal(self, returns: pd.Series) -> float:
        """EVT VaR safety signal."""
        if len(returns) < 30:
            return 0.0
        var_95 = float(np.percentile(returns, 5))
        last_return = float(returns.iloc[-1])
        if last_return > var_95:
            return 1.0
        return -1.0

    def _momentum_signal(self, prices: pd.Series, period: int = 30) -> float:
        """Momentum signal normalized to [-1, +1]."""
        if len(prices) < period + 1:
            return 0.0
        momentum = float(prices.iloc[-1] / prices.iloc[-period] - 1)
        return float(np.clip(momentum * 10, -1, 1))

    def _mean_reversion_signal(self, prices: pd.Series) -> float:
        """Mean reversion: buy if far below SMA200, sell if far above."""
        if len(prices) < 200:
            if len(prices) < 50:
                return 0.0
            sma = float(prices.rolling(50).mean().iloc[-1])
        else:
            sma = float(prices.rolling(200).mean().iloc[-1])

        current = float(prices.iloc[-1])
        deviation = (current - sma) / sma if sma > 0 else 0

        if deviation < -0.10:
            return 1.0
        if deviation > 0.10:
            return -1.0
        return float(-deviation * 10)

    def _volume_signal(self, ticker: str) -> float:
        """Volume confirmation: +1 if volume above 20d avg, -1 if below."""
        vol_series = self._volume_cache.get(ticker)
        if vol_series is None or len(vol_series) < 21:
            return 0.0
        avg_vol = float(vol_series.iloc[-21:-1].mean())
        if avg_vol <= 0:
            return 0.0
        current_vol = float(vol_series.iloc[-1])
        ratio = current_vol / avg_vol
        if ratio > 1.5:
            return 1.0
        if ratio > 1.2:
            return 0.5
        if ratio < 0.5:
            return -1.0
        if ratio < 0.8:
            return -0.5
        return 0.0

    def bootstrap_historical(self, days: int = 120) -> dict:
        """Run paper trading on historical data to bootstrap learning.

        Simulates daily trading decisions using rolling windows of
        historical prices, building up a trade history that enables
        weekly_learning() and monthly_evolution() to function.

        Args:
            days: Number of historical days to simulate.

        Returns:
            Dict with total trades, buys, sells, and learning results.
        """
        import yfinance as yf

        logger.info("Bootstrap: fetching 1y history for %s", self.tickers)
        hist_data: dict[str, pd.DataFrame] = {}
        for ticker in self.tickers:
            hist = yf.Ticker(ticker).history(period="1y")
            if not hist.empty:
                hist_data[ticker] = hist

        if not hist_data:
            return {"error": "no_data"}

        return self._run_bootstrap_loop(hist_data, days)

    def bootstrap_synthetic(self, days: int = 120, seed: int = 42) -> dict:
        """Bootstrap learning from deterministic synthetic price paths.

        Network-free and cheap (Karpathy-style precompute): generates
        reproducible geometric-Brownian-motion histories per ticker so
        weekly_learning() and monthly_evolution() always have qualifying
        closed trades even when yfinance is rate-limited or offline.
        """
        rng = np.random.default_rng(seed)
        n = days + 60
        idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=n, freq="B")
        hist_data: dict[str, pd.DataFrame] = {}
        for i, ticker in enumerate(self.tickers):
            drift = 0.0004 + 0.0002 * ((i % 3) - 1)  # per-ticker trend
            shocks = rng.normal(drift, 0.03, n)  # ~48% annualized vol
            close = 100.0 * np.exp(np.cumsum(shocks))
            volume = rng.uniform(5e5, 2e6, n)
            hist_data[ticker] = pd.DataFrame(
                {"Close": close, "Volume": volume}, index=idx,
            )
        result = self._run_bootstrap_loop(hist_data, days)
        result["mode"] = "synthetic"
        return result

    def _run_bootstrap_loop(
        self, hist_data: dict[str, pd.DataFrame], days: int,
    ) -> dict:
        """Shared rolling-window simulation for historical/synthetic bootstrap."""
        min_len = min(len(df) for df in hist_data.values())
        if min_len < days + 50:
            days = max(20, min_len - 50)

        total_buys = 0
        total_sells = 0
        simulated_dates: list[str] = []

        for day_offset in range(days):
            window_end = min_len - days + day_offset
            if window_end < 50:
                continue

            windows: dict[str, pd.Series] = {}
            for ticker in self.tickers:
                if ticker in hist_data:
                    windows[ticker] = hist_data[ticker]["Close"].iloc[:window_end]
            self._alpha_cache = self._compute_alpha(windows)

            day_trades: list[PaperTrade] = []
            for ticker in self.tickers:
                if ticker not in hist_data:
                    continue
                df = hist_data[ticker]
                price_window = df["Close"].iloc[:window_end]
                vol_window = df["Volume"].iloc[:window_end]
                self._volume_cache[ticker] = vol_window

                if len(price_window) < 2:
                    continue
                current_price = float(price_window.iloc[-1])
                if current_price <= 0:
                    continue

                signals = self._collect_signals(ticker, price_window)
                action, confidence = self._make_decision(signals)

                if action == TradeAction.HOLD:
                    continue

                trade = self._execute_paper_trade(
                    ticker, action, current_price, confidence, signals,
                )
                if trade:
                    day_trades.append(trade)
                    if action == TradeAction.BUY:
                        total_buys += 1
                    else:
                        total_sells += 1

            prices_snapshot = {}
            for ticker in self.tickers:
                if ticker in hist_data:
                    df = hist_data[ticker]
                    window_end_idx = min_len - days + day_offset
                    prices_snapshot[ticker] = df["Close"].iloc[:window_end_idx]

            self._update_positions(prices_snapshot)
            self._record_snapshot(prices_snapshot)

            trade_date = list(hist_data.values())[0].index[window_end - 1]
            simulated_dates.append(str(trade_date.date()))

            if day_offset % 5 == 4:
                for ticker, pos in list(self._positions.items()):
                    if ticker in hist_data:
                        df = hist_data[ticker]
                        current = float(df["Close"].iloc[min_len - days + day_offset])
                        ret = (current - pos.avg_entry_price) / pos.avg_entry_price
                        if ret > 0.08 or ret < -0.05:
                            price = current
                            eff_price = price * (1 - self.COMMISSION_PCT - self.SLIPPAGE_PCT)
                            proceeds = pos.quantity * eff_price
                            pnl = (eff_price - pos.avg_entry_price) * pos.quantity
                            pnl_pct = (eff_price / pos.avg_entry_price - 1) * 100
                            self._cash += proceeds
                            close_trade = PaperTrade(
                                id=str(uuid.uuid4())[:8],
                                timestamp=str(trade_date),
                                ticker=ticker,
                                action=TradeAction.SELL,
                                price=price,
                                quantity=pos.quantity,
                                reason=f"auto_close_ret={ret:.2%}",
                                signals={},
                                confidence=0.5,
                                pnl=round(pnl, 2),
                                pnl_pct=round(pnl_pct, 2),
                                status="closed",
                                closed_at=str(trade_date),
                            )
                            self._trades.append(close_trade)
                            del self._positions[ticker]
                            total_sells += 1

        self._save_state()

        learning_results = self.weekly_learning()
        evolution_results = self.monthly_evolution()

        return {
            "days_simulated": days,
            "total_trades": len(self._trades),
            "buys": total_buys,
            "sells": total_sells,
            "closed_trades": sum(1 for t in self._trades if t.status == "closed"),
            "final_value": round(self._portfolio_value(), 2),
            "pnl": round(self._portfolio_value() - self.INITIAL_CASH, 2),
            "learning_insights": len(learning_results),
            "evolution": evolution_results,
            "dates": f"{simulated_dates[0]} → {simulated_dates[-1]}" if simulated_dates else "",
        }

    # ── Persistence ──

    def _save_state(self) -> None:
        """Save all state to JSON files."""
        try:
            trades_data = [
                {
                    "id": t.id, "timestamp": t.timestamp, "ticker": t.ticker,
                    "action": t.action.value, "price": t.price, "quantity": t.quantity,
                    "reason": t.reason, "signals": t.signals, "regime": t.regime,
                    "confidence": t.confidence, "pnl": t.pnl, "pnl_pct": t.pnl_pct,
                    "status": t.status, "closed_at": t.closed_at,
                }
                for t in self._trades
            ]
            (self.DATA_DIR / "trades.json").write_text(json.dumps(trades_data, indent=2))

            portfolio = {
                "cash": self._cash,
                "positions": {
                    t: {
                        "quantity": p.quantity, "avg_entry_price": p.avg_entry_price,
                        "current_price": p.current_price, "entry_date": p.entry_date,
                    }
                    for t, p in self._positions.items()
                },
            }
            (self.DATA_DIR / "portfolio.json").write_text(json.dumps(portfolio, indent=2))

            (self.DATA_DIR / "config.json").write_text(
                json.dumps(
                    {"weights": self._signal_weights, "generation": self._generation},
                    indent=2,
                ),
            )
        except Exception as exc:
            logger.warning("Save state failed: %s", exc)

    def _load_state(self) -> None:
        """Load saved state from JSON files."""
        try:
            trades_path = self.DATA_DIR / "trades.json"
            if trades_path.exists():
                data = json.loads(trades_path.read_text())
                self._trades = [
                    PaperTrade(
                        id=t["id"], timestamp=t["timestamp"], ticker=t["ticker"],
                        action=TradeAction(t["action"]), price=t["price"],
                        quantity=t["quantity"], reason=t.get("reason", ""),
                        signals=t.get("signals", {}), regime=t.get("regime", ""),
                        confidence=t.get("confidence", 0), pnl=t.get("pnl"),
                        pnl_pct=t.get("pnl_pct"), status=t.get("status", "open"),
                        closed_at=t.get("closed_at"),
                    )
                    for t in data
                ]

            portfolio_path = self.DATA_DIR / "portfolio.json"
            if portfolio_path.exists():
                data = json.loads(portfolio_path.read_text())
                self._cash = data.get("cash", self.INITIAL_CASH)
                for ticker, pos_data in data.get("positions", {}).items():
                    self._positions[ticker] = PaperPosition(
                        ticker=ticker,
                        quantity=pos_data["quantity"],
                        avg_entry_price=pos_data["avg_entry_price"],
                        current_price=pos_data.get("current_price", pos_data["avg_entry_price"]),
                        entry_date=pos_data.get("entry_date", ""),
                    )

            config_path = self.DATA_DIR / "config.json"
            if config_path.exists():
                cfg = json.loads(config_path.read_text())
                if isinstance(cfg, dict) and "weights" in cfg:
                    self._signal_weights = cfg["weights"]
                    self._generation = cfg.get("generation", 0)
                else:
                    # backward-compat: old format stored weights at top level
                    self._signal_weights = cfg

        except Exception as exc:
            logger.warning("Load state failed: %s", exc)
