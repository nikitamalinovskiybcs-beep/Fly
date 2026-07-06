"""ClickHouse Cloud client — columnar OLAP for large analytical datasets.

Free tier: 10GB storage, 100GB queries/month.
100x faster than PostgreSQL for aggregations on millions of rows.

Environment variables:
    CLICKHOUSE_HOST=xxx.clickhouse.cloud
    CLICKHOUSE_USER=default
    CLICKHOUSE_PASSWORD=xxx
"""

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ClickHouseStorage:
    """Analytics database for large datasets.

    Tables:
        ohlcv — ticker price history (partitioned by year)
        backtest_results — strategy performance records
        numerai_features — Numerai tournament data
        indicator_cache — precomputed technical indicators
    """

    def __init__(self, host: str = "", user: str = "default", password: str = "") -> None:
        self._client = None
        self._enabled = False

        if not host or not password:
            logger.info("ClickHouse not configured, analytics DB disabled")
            return

        try:
            import clickhouse_connect
            self._client = clickhouse_connect.get_client(
                host=host, username=user, password=password, secure=True,
            )
            self._create_tables()
            self._enabled = True
            logger.info("ClickHouse Cloud connected: %s", host)
        except ImportError:
            logger.info("clickhouse-connect not installed, ClickHouse disabled")
        except Exception as exc:
            logger.warning("ClickHouse init failed: %s", exc)

    @property
    def enabled(self) -> bool:
        """Whether ClickHouse is available."""
        return self._enabled

    def _create_tables(self) -> None:
        """Create tables if they don't exist."""
        try:
            self._client.command("""
                CREATE TABLE IF NOT EXISTS ohlcv (
                    ticker String,
                    date Date,
                    open Float64,
                    high Float64,
                    low Float64,
                    close Float64,
                    volume UInt64,
                    adj_close Float64
                ) ENGINE = MergeTree()
                PARTITION BY toYear(date)
                ORDER BY (ticker, date)
            """)
            self._client.command("""
                CREATE TABLE IF NOT EXISTS backtest_results (
                    id String,
                    timestamp DateTime,
                    strategy String,
                    tickers String,
                    start_date Date,
                    end_date Date,
                    sharpe Float64,
                    total_return Float64,
                    max_drawdown Float64,
                    win_rate Float64,
                    total_trades UInt32,
                    parameters String
                ) ENGINE = MergeTree()
                ORDER BY (strategy, timestamp)
            """)
            self._client.command("""
                CREATE TABLE IF NOT EXISTS indicator_cache (
                    ticker String,
                    date Date,
                    indicator String,
                    period UInt32,
                    value Float64
                ) ENGINE = MergeTree()
                ORDER BY (ticker, date, indicator)
            """)
        except Exception as exc:
            logger.warning("ClickHouse table creation failed: %s", exc)

    def save_ohlcv(self, ticker: str, data: pd.DataFrame) -> int:
        """Save OHLCV price data for a ticker.

        Args:
            ticker: Ticker symbol.
            data: DataFrame with date, open, high, low, close, volume columns.

        Returns:
            Number of rows inserted.
        """
        if not self._enabled or data.empty:
            return 0
        try:
            df = data.copy()
            df["ticker"] = ticker
            if "adj_close" not in df.columns:
                df["adj_close"] = df["close"]
            cols = ["ticker", "date", "open", "high", "low", "close", "volume", "adj_close"]
            df = df[[c for c in cols if c in df.columns]]
            self._client.insert_df("ohlcv", df)
            return len(df)
        except Exception as exc:
            logger.warning("ClickHouse save OHLCV failed: %s", exc)
            return 0

    def get_ohlcv(self, ticker: str, start: str = "", end: str = "") -> pd.DataFrame:
        """Get OHLCV data for a ticker.

        Args:
            ticker: Ticker symbol.
            start: Start date (YYYY-MM-DD).
            end: End date (YYYY-MM-DD).

        Returns:
            DataFrame with OHLCV data.
        """
        if not self._enabled:
            return pd.DataFrame()
        try:
            sql = f"SELECT * FROM ohlcv WHERE ticker = '{ticker}'"
            if start:
                sql += f" AND date >= '{start}'"
            if end:
                sql += f" AND date <= '{end}'"
            sql += " ORDER BY date"
            return self._client.query_df(sql)
        except Exception as exc:
            logger.warning("ClickHouse get OHLCV failed: %s", exc)
            return pd.DataFrame()

    def save_backtest(self, strategy: str, results: dict) -> bool:
        """Save a backtest result.

        Args:
            strategy: Strategy name.
            results: Backtest metrics dict.

        Returns:
            True if saved.
        """
        if not self._enabled:
            return False
        try:
            df = pd.DataFrame([{
                "id": results.get("id", ""),
                "timestamp": datetime.now(),
                "strategy": strategy,
                "tickers": results.get("tickers", ""),
                "start_date": results.get("start_date", ""),
                "end_date": results.get("end_date", ""),
                "sharpe": results.get("sharpe", 0.0),
                "total_return": results.get("total_return", 0.0),
                "max_drawdown": results.get("max_drawdown", 0.0),
                "win_rate": results.get("win_rate", 0.0),
                "total_trades": results.get("total_trades", 0),
                "parameters": str(results.get("parameters", {})),
            }])
            self._client.insert_df("backtest_results", df)
            return True
        except Exception as exc:
            logger.warning("ClickHouse save backtest failed: %s", exc)
            return False

    def get_backtest(self, strategy: str) -> pd.DataFrame:
        """Get backtest results for a strategy.

        Args:
            strategy: Strategy name.

        Returns:
            DataFrame with backtest results.
        """
        if not self._enabled:
            return pd.DataFrame()
        try:
            return self._client.query_df(
                f"SELECT * FROM backtest_results WHERE strategy = '{strategy}' ORDER BY timestamp DESC"
            )
        except Exception as exc:
            logger.warning("ClickHouse get backtest failed: %s", exc)
            return pd.DataFrame()

    def query(self, sql: str) -> pd.DataFrame:
        """Run raw SQL query for analytics.

        Args:
            sql: SQL query string.

        Returns:
            DataFrame with results.
        """
        if not self._enabled:
            return pd.DataFrame()
        try:
            return self._client.query_df(sql)
        except Exception as exc:
            logger.warning("ClickHouse query failed: %s", exc)
            return pd.DataFrame()

    def table_stats(self) -> dict[str, int]:
        """Get row counts for all tables.

        Returns:
            Dict of table_name -> row_count.
        """
        if not self._enabled:
            return {}
        stats: dict[str, int] = {}
        for table in ["ohlcv", "backtest_results", "indicator_cache"]:
            try:
                result = self._client.query(f"SELECT count() as cnt FROM {table}")
                stats[table] = int(result.result_rows[0][0])
            except Exception:
                stats[table] = 0
        return stats
