"""Event-driven backtest engine."""

import logging

import numpy as np
import pandas as pd

from .broker_sim import SimulatedBroker
from .models import BacktestConfig, BacktestResult
from .portfolio_sim import PortfolioSimulator
from .strategy_base import BaseStrategy

logger = logging.getLogger(__name__)

TRADING_DAYS = 252


class BacktestEngine:
    """Main backtest engine. Event-driven daily simulation.

    A data_fetcher(ticker, start, end) -> DataFrame can be injected for
    tests / offline runs; defaults to yfinance.
    """

    def __init__(self, strategy: BaseStrategy, config: BacktestConfig, data_fetcher=None):
        self.strategy = strategy
        self.config = config
        self.broker = SimulatedBroker(config.commission_pct, config.slippage_pct)
        self.portfolio = PortfolioSimulator(config.initial_capital)
        self._fetch = data_fetcher or self._default_fetch

    @staticmethod
    def _default_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
        try:
            import yfinance as yf

            return yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch failed for %s: %s", ticker, exc)
            return pd.DataFrame()

    def run(self) -> BacktestResult:
        cfg = self.config
        data: dict[str, pd.DataFrame] = {}
        for ticker in cfg.tickers:
            df = self._fetch(ticker, cfg.start_date, cfg.end_date)
            if df is not None and not df.empty:
                data[ticker] = df
        bench_df = self._fetch(cfg.benchmark, cfg.start_date, cfg.end_date)

        if not data:
            logger.warning("No data for any ticker — empty backtest")
            return BacktestResult(config=cfg)

        all_dates = sorted(set().union(*[set(df.index) for df in data.values()]))
        rebalance_dates = self._rebalance_dates(all_dates, cfg.rebalance_freq)

        for date in all_dates:
            date_str = _date_str(date)
            prices = {t: _close_on(df, date) for t, df in data.items() if _close_on(df, date) is not None}

            if date in rebalance_dates:
                features = self._features_on(data, date)
                signals = self.strategy.generate_signals(data, features, date_str)
                self._apply_signals(signals, prices, date_str)

            self.portfolio.mark_to_market(prices, date_str)

        # Close all open positions at last available price
        last_str = _date_str(all_dates[-1])
        for ticker in list(self.portfolio.positions.keys()):
            px = _close_on(data[ticker], all_dates[-1])
            if px is None:
                px = self.portfolio.positions[ticker]["avg_price"]
            size = self.portfolio.positions[ticker]["size"]
            fill, comm, slip = self.broker.execute_sell(px, size)
            self.portfolio.sell(ticker, fill, size, last_str, comm, slip)

        return self._build_result(bench_df)

    def _apply_signals(self, signals: dict[str, float], prices: dict[str, float], date_str: str) -> None:
        cfg = self.config
        pv = self.portfolio.get_value(prices)
        for ticker, signal in signals.items():
            price = prices.get(ticker)
            if price is None or price <= 0:
                continue
            has_position = ticker in self.portfolio.positions
            if signal > 0.1 and not has_position:
                size = self.strategy.position_size(ticker, signal, pv, price, cfg.max_position_pct)
                if size > 0:
                    fill, comm, slip = self.broker.execute_buy(price, size)
                    if self.portfolio.buy(ticker, fill, size, date_str, comm, slip):
                        self.strategy.on_trade(self.portfolio.trades[-1] if self.portfolio.trades else None)
            elif signal < -0.1 and has_position:
                size = self.portfolio.positions[ticker]["size"]
                fill, comm, slip = self.broker.execute_sell(price, size)
                self.portfolio.sell(ticker, fill, size, date_str, comm, slip)

    def _features_on(self, data: dict[str, pd.DataFrame], date) -> dict:
        """Lightweight per-ticker feature dict computed from data up to date."""
        from src.feature_store.features import (
            compute_momentum,
            compute_rsi,
            compute_sma,
        )
        from src.feature_store.models import FeatureVector

        out: dict[str, FeatureVector] = {}
        for ticker, df in data.items():
            window = df[df.index <= date]
            if len(window) < 60:
                continue
            close = window["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            try:
                sma50 = compute_sma(close, 50)
                sma200 = compute_sma(close, 200) if len(close) >= 200 else sma50
                last = float(close.iloc[-1])
                regime = "bull" if last > sma50 > sma200 else "bear" if last < sma50 < sma200 else "sideways"
                out[ticker] = FeatureVector(
                    ticker=ticker,
                    date=_date_str(date),
                    rsi_14=compute_rsi(close, 14),
                    sma_50=sma50,
                    sma_200=sma200,
                    momentum_30d=compute_momentum(close, 30),
                    distance_to_sma50_pct=(last / sma50 - 1) * 100,
                    distance_to_sma200_pct=(last / sma200 - 1) * 100,
                    regime=regime,
                )
            except Exception:  # noqa: BLE001
                continue
        return out

    @staticmethod
    def _rebalance_dates(dates: list, freq: str) -> set:
        if freq == "daily":
            return set(dates)
        out = set()
        last_key = None
        for d in dates:
            ts = pd.Timestamp(d)
            key = (ts.year, ts.isocalendar().week) if freq == "weekly" else (ts.year, ts.month)
            if key != last_key:
                out.add(d)
                last_key = key
        return out

    def _build_result(self, bench_df: pd.DataFrame) -> BacktestResult:
        cfg = self.config
        eq = self.portfolio.equity_history
        result = BacktestResult(config=cfg, equity_curve=eq, trades=self.portfolio.trades)
        if not eq:
            return result

        values = np.array([e["value"] for e in eq], dtype=float)
        rets = np.diff(values) / values[:-1] if len(values) > 1 else np.array([0.0])

        result.total_return = float((values[-1] / values[0] - 1) * 100)
        n_days = len(values)
        years = max(n_days / TRADING_DAYS, 1e-9)
        result.cagr = float(((values[-1] / values[0]) ** (1 / years) - 1) * 100)

        if rets.std() > 0:
            result.sharpe = float(rets.mean() / rets.std() * np.sqrt(TRADING_DAYS))
            downside = rets[rets < 0]
            if downside.std() > 0:
                result.sortino = float(rets.mean() / downside.std() * np.sqrt(TRADING_DAYS))

        result.max_drawdown = float(min(e["drawdown"] for e in eq))
        result.max_dd_duration_days = _max_dd_duration(eq)
        if result.max_drawdown < 0:
            result.calmar = float(result.cagr / abs(result.max_drawdown))

        trades = self.portfolio.trades
        result.total_trades = len(trades)
        if trades:
            wins = [t for t in trades if t.pnl > 0]
            losses = [t for t in trades if t.pnl <= 0]
            result.win_rate = float(len(wins) / len(trades) * 100)
            result.avg_win = float(np.mean([t.pnl for t in wins])) if wins else 0.0
            result.avg_loss = float(np.mean([t.pnl for t in losses])) if losses else 0.0
            gross_win = sum(t.pnl for t in wins)
            gross_loss = abs(sum(t.pnl for t in losses))
            result.profit_factor = float(gross_win / gross_loss) if gross_loss > 0 else 0.0
            result.avg_hold_days = float(np.mean([t.hold_days for t in trades]))

        result.monthly_returns = _monthly_returns(eq)
        self._add_benchmark_stats(result, bench_df, rets)
        return result

    def _add_benchmark_stats(self, result: BacktestResult, bench_df: pd.DataFrame, rets: np.ndarray) -> None:
        if bench_df is None or bench_df.empty:
            return
        bclose = bench_df["Close"]
        if isinstance(bclose, pd.DataFrame):
            bclose = bclose.iloc[:, 0]
        bench_ret = float((bclose.iloc[-1] / bclose.iloc[0] - 1) * 100)
        result.benchmark_return = bench_ret
        result.alpha = float(result.total_return - bench_ret)
        bench_daily = bclose.pct_change().dropna().to_numpy()
        n = min(len(bench_daily), len(rets))
        if n > 2:
            b = bench_daily[-n:]
            r = rets[-n:]
            var = np.var(b)
            if var > 0:
                result.beta = float(np.cov(r, b)[0, 1] / var)
            active = r - b
            if active.std() > 0:
                result.information_ratio = float(active.mean() / active.std() * np.sqrt(TRADING_DAYS))


def _close_on(df: pd.DataFrame, date):
    if date not in df.index:
        return None
    val = df.loc[date, "Close"]
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _date_str(date) -> str:
    return pd.Timestamp(date).strftime("%Y-%m-%d")


def _max_dd_duration(eq: list[dict]) -> int:
    longest = 0
    current = 0
    for e in eq:
        if e["drawdown"] < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _monthly_returns(eq: list[dict]) -> dict:
    if not eq:
        return {}
    df = pd.DataFrame(eq)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    monthly = df["value"].resample("ME").last()
    rets = monthly.pct_change().dropna() * 100
    return {ts.strftime("%Y-%m"): float(v) for ts, v in rets.items()}
