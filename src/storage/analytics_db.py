"""DuckDB analytical database — columnar storage for OLAP queries.

100x faster than SQLite for aggregations on large datasets.
Used for: price history, signal accuracy, backtests, Numerai features.
File: data/fly_analytics.duckdb
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

DUCK_DIR = Path("data")
DUCK_PATH = DUCK_DIR / "fly_analytics.duckdb"

ANALYTICS_TABLES_SQL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS price_history (
        ticker VARCHAR,
        date DATE,
        open DOUBLE,
        high DOUBLE,
        low DOUBLE,
        close DOUBLE,
        volume BIGINT,
        adj_close DOUBLE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signals_history (
        timestamp TIMESTAMP,
        ticker VARCHAR,
        agent VARCHAR,
        signal DOUBLE,
        confidence DOUBLE,
        regime VARCHAR,
        actual_return_1d DOUBLE,
        actual_return_5d DOUBLE,
        was_correct BOOLEAN
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_results (
        id VARCHAR,
        timestamp TIMESTAMP,
        strategy VARCHAR,
        tickers VARCHAR,
        start_date DATE,
        end_date DATE,
        sharpe DOUBLE,
        total_return DOUBLE,
        max_drawdown DOUBLE,
        win_rate DOUBLE,
        total_trades INTEGER,
        parameters VARCHAR
    )
    """,
]


class AnalyticsDB:
    """DuckDB for analytical queries on large datasets."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._path = db_path or DUCK_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = None
        self._connect()

    def _connect(self) -> None:
        """Initialize DuckDB connection and create tables."""
        try:
            import duckdb
            self._conn = duckdb.connect(str(self._path))
            for sql in ANALYTICS_TABLES_SQL:
                self._conn.execute(sql)
            logger.info("AnalyticsDB initialized: %s", self._path)
        except ImportError:
            logger.warning("duckdb not installed, analytics disabled")
            self._conn = None
        except Exception as exc:
            logger.warning("DuckDB init failed: %s", exc)
            self._conn = None

    @property
    def available(self) -> bool:
        """Whether DuckDB is available."""
        return self._conn is not None

    def query(self, sql: str) -> pd.DataFrame:
        """Run analytical query and return DataFrame.

        Args:
            sql: SQL query string.

        Returns:
            pandas DataFrame with results.
        """
        if not self.available:
            return pd.DataFrame()
        try:
            return self._conn.execute(sql).df()
        except Exception as exc:
            logger.warning("DuckDB query failed: %s", exc)
            return pd.DataFrame()

    def insert_prices(self, ticker: str, df: pd.DataFrame) -> int:
        """Insert price data for a ticker.

        Args:
            ticker: Ticker symbol.
            df: DataFrame with OHLCV columns.

        Returns:
            Number of rows inserted.
        """
        if not self.available or df.empty:
            return 0
        try:
            df = df.copy()
            df["ticker"] = ticker
            cols = ["ticker", "date", "open", "high", "low", "close", "volume"]
            if "adj_close" in df.columns:
                cols.append("adj_close")
            available_cols = [c for c in cols if c in df.columns]
            subset = df[available_cols]
            self._conn.execute(
                f"DELETE FROM price_history WHERE ticker = '{ticker}'"
            )
            self._conn.execute(
                "INSERT INTO price_history SELECT * FROM subset"
            )
            return len(subset)
        except Exception as exc:
            logger.warning("Insert prices failed: %s", exc)
            return 0

    def insert_signals(self, signals: list[dict]) -> int:
        """Insert agent signal records.

        Args:
            signals: List of signal dicts.

        Returns:
            Number of rows inserted.
        """
        if not self.available or not signals:
            return 0
        try:
            df = pd.DataFrame(signals)
            self._conn.execute("INSERT INTO signals_history SELECT * FROM df")
            return len(df)
        except Exception as exc:
            logger.warning("Insert signals failed: %s", exc)
            return 0

    def insert_backtest(self, result: dict) -> None:
        """Insert a backtest result record.

        Args:
            result: Backtest result dict.
        """
        if not self.available:
            return
        try:
            self._conn.execute(
                "INSERT INTO backtest_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [result.get(k, "") for k in (
                    "id", "timestamp", "strategy", "tickers", "start_date", "end_date",
                    "sharpe", "total_return", "max_drawdown", "win_rate", "total_trades", "parameters",
                )],
            )
        except Exception as exc:
            logger.warning("Insert backtest failed: %s", exc)

    def read_parquet(self, path: str) -> pd.DataFrame:
        """Read Parquet file directly using DuckDB.

        Args:
            path: Path to parquet file.

        Returns:
            DataFrame with parquet data.
        """
        if not self.available:
            return pd.DataFrame()
        try:
            return self._conn.execute(f"SELECT * FROM '{path}'").df()
        except Exception as exc:
            logger.warning("Read parquet failed: %s", exc)
            return pd.DataFrame()

    def get_price_history(self, ticker: str, days: int = 365) -> pd.DataFrame:
        """Get price history for a ticker.

        Args:
            ticker: Ticker symbol.
            days: Number of days to retrieve.

        Returns:
            DataFrame with OHLCV data.
        """
        return self.query(
            f"SELECT * FROM price_history WHERE ticker = '{ticker}' "
            f"ORDER BY date DESC LIMIT {days}"
        )

    def get_signal_accuracy(self, agent: str, days: int = 90) -> dict:
        """Get signal accuracy stats for an agent.

        Args:
            agent: Agent name.
            days: Lookback period in days.

        Returns:
            Dict with total_signals, correct, accuracy.
        """
        df = self.query(
            f"SELECT was_correct, COUNT(*) as cnt FROM signals_history "
            f"WHERE agent = '{agent}' AND was_correct IS NOT NULL "
            f"GROUP BY was_correct"
        )
        if df.empty:
            return {"total_signals": 0, "correct": 0, "accuracy": 0.0}
        total = int(df["cnt"].sum())
        correct_df = df[df["was_correct"] == True]  # noqa: E712
        correct = int(correct_df["cnt"].sum()) if not correct_df.empty else 0
        return {
            "total_signals": total,
            "correct": correct,
            "accuracy": correct / total if total > 0 else 0.0,
        }

    def get_backtest_history(self, limit: int = 50) -> pd.DataFrame:
        """Get recent backtest results.

        Args:
            limit: Max number of results.

        Returns:
            DataFrame of backtest results.
        """
        return self.query(
            f"SELECT * FROM backtest_results ORDER BY timestamp DESC LIMIT {limit}"
        )

    def table_stats(self) -> dict[str, int]:
        """Get row counts for all analytics tables.

        Returns:
            Dict of table_name -> row_count.
        """
        stats: dict[str, int] = {}
        for table in ["price_history", "signals_history", "backtest_results"]:
            df = self.query(f"SELECT COUNT(*) as cnt FROM {table}")
            stats[table] = int(df["cnt"].iloc[0]) if not df.empty else 0
        return stats

    def close(self) -> None:
        """Close DuckDB connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
