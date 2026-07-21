"""Backtest performance reporting."""

import pandas as pd

from .models import BacktestResult


class BacktestReporter:
    """Formats a BacktestResult into human-readable summaries and tables."""

    def summary(self, result: BacktestResult) -> str:
        r = result
        return (
            f"Backtest: {', '.join(r.config.tickers)} "
            f"({r.config.start_date} -> {r.config.end_date})\n"
            f"  Total return:   {r.total_return:+.2f}%\n"
            f"  CAGR:           {r.cagr:+.2f}%\n"
            f"  Sharpe:         {r.sharpe:.2f}\n"
            f"  Sortino:        {r.sortino:.2f}\n"
            f"  Calmar:         {r.calmar:.2f}\n"
            f"  Max drawdown:   {r.max_drawdown:.2f}% "
            f"({r.max_dd_duration_days}d)\n"
            f"  Win rate:       {r.win_rate:.1f}%\n"
            f"  Profit factor:  {r.profit_factor:.2f}\n"
            f"  Trades:         {r.total_trades} "
            f"(avg hold {r.avg_hold_days:.1f}d)\n"
            f"  Benchmark:      {r.benchmark_return:+.2f}%\n"
            f"  Alpha:          {r.alpha:+.2f}%   Beta: {r.beta:.2f}\n"
            f"  Info ratio:     {r.information_ratio:.2f}"
        )

    def to_dataframe(self, result: BacktestResult) -> pd.DataFrame:
        """Equity curve as DataFrame indexed by date."""
        if not result.equity_curve:
            return pd.DataFrame(columns=["value", "drawdown"])
        df = pd.DataFrame(result.equity_curve)
        return df.set_index("date")

    def monthly_table(self, result: BacktestResult) -> pd.DataFrame:
        """Monthly returns pivoted (month rows x year columns)."""
        if not result.monthly_returns:
            return pd.DataFrame()
        rows = []
        for ym, ret in result.monthly_returns.items():
            year, month = ym.split("-")
            rows.append({"year": year, "month": int(month), "return": ret})
        df = pd.DataFrame(rows)
        return df.pivot(index="month", columns="year", values="return").sort_index()

    def trades_dataframe(self, result: BacktestResult) -> pd.DataFrame:
        if not result.trades:
            return pd.DataFrame()
        return pd.DataFrame([t.__dict__ for t in result.trades])
