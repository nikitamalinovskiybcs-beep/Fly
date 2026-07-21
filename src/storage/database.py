"""SQLite database manager — singleton, WAL mode, thread-safe.

Handles all OLTP operations: trades, portfolio, configs, learning log.
File: data/fly.db
"""

import json
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

from src.storage.migrations import run_migrations

logger = logging.getLogger(__name__)

DB_DIR = Path("data")
DB_PATH = DB_DIR / "fly.db"


class Database:
    """SQLite database manager. Singleton pattern with WAL mode."""

    _instance: Optional["Database"] = None
    _lock = threading.Lock()

    def __new__(cls, db_path: Optional[Path] = None) -> "Database":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if self._initialized:
            return
        self._db_path = db_path or DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path), check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        run_migrations(self._conn)
        self._initialized = True
        logger.info("Database initialized: %s", self._db_path)

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for atomic transactions.

        Yields:
            SQLite connection. Commits on success, rolls back on error.
        """
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def execute(self, sql: str, params: Optional[tuple] = None) -> sqlite3.Cursor:
        """Execute SQL statement.

        Args:
            sql: SQL query string.
            params: Query parameters.

        Returns:
            SQLite cursor.
        """
        if params:
            return self._conn.execute(sql, params)
        return self._conn.execute(sql)

    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Optional[dict]:
        """Fetch one row as dict.

        Args:
            sql: SELECT query.
            params: Query parameters.

        Returns:
            Dict or None if no row found.
        """
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> list[dict]:
        """Fetch all rows as list of dicts.

        Args:
            sql: SELECT query.
            params: Query parameters.

        Returns:
            List of dicts.
        """
        cursor = self.execute(sql, params)
        return [dict(r) for r in cursor.fetchall()]

    def insert(self, table: str, data: dict[str, Any]) -> int:
        """Insert a row into a table.

        Args:
            table: Table name.
            data: Column -> value mapping.

        Returns:
            Last row ID.
        """
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        cursor = self._conn.execute(sql, tuple(data.values()))
        self._conn.commit()
        return cursor.lastrowid or 0

    def insert_or_replace(self, table: str, data: dict[str, Any]) -> int:
        """Insert or replace a row.

        Args:
            table: Table name.
            data: Column -> value mapping.

        Returns:
            Last row ID.
        """
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
        cursor = self._conn.execute(sql, tuple(data.values()))
        self._conn.commit()
        return cursor.lastrowid or 0

    def update(
        self, table: str, data: dict[str, Any], where: str, params: tuple,
    ) -> int:
        """Update rows matching condition.

        Args:
            table: Table name.
            data: Column -> new value mapping.
            where: WHERE clause (without WHERE keyword).
            params: Parameters for WHERE clause.

        Returns:
            Number of rows updated.
        """
        set_clause = ", ".join(f"{k} = ?" for k in data.keys())
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        all_params = tuple(data.values()) + params
        cursor = self._conn.execute(sql, all_params)
        self._conn.commit()
        return cursor.rowcount

    def delete(self, table: str, where: str, params: tuple) -> int:
        """Delete rows matching condition.

        Args:
            table: Table name.
            where: WHERE clause.
            params: Parameters for WHERE clause.

        Returns:
            Number of rows deleted.
        """
        sql = f"DELETE FROM {table} WHERE {where}"
        cursor = self._conn.execute(sql, params)
        self._conn.commit()
        return cursor.rowcount

    def count(self, table: str, where: Optional[str] = None, params: Optional[tuple] = None) -> int:
        """Count rows in a table.

        Args:
            table: Table name.
            where: Optional WHERE clause.
            params: Optional parameters.

        Returns:
            Row count.
        """
        sql = f"SELECT COUNT(*) as cnt FROM {table}"
        if where:
            sql += f" WHERE {where}"
        row = self.fetchone(sql, params)
        return row["cnt"] if row else 0

    def table_stats(self) -> dict[str, int]:
        """Get row counts for all tables.

        Returns:
            Dict of table_name -> row_count.
        """
        tables = self.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        stats: dict[str, int] = {}
        for t in tables:
            name = t["name"]
            stats[name] = self.count(name)
        return stats

    def db_size_bytes(self) -> int:
        """Get database file size in bytes.

        Returns:
            File size in bytes.
        """
        if self._db_path.exists():
            return self._db_path.stat().st_size
        return 0

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._initialized = False
            Database._instance = None

    # ── Convenience methods for common operations ──

    def insert_trade(self, trade: dict[str, Any]) -> int:
        """Insert a trade record.

        Args:
            trade: Trade data dict.

        Returns:
            Row ID.
        """
        if "id" not in trade:
            trade["id"] = str(uuid.uuid4())[:8]
        if "timestamp" not in trade:
            trade["timestamp"] = datetime.now().isoformat()
        return self.insert("trades", trade)

    def get_open_trades(self) -> list[dict]:
        """Get all open trades."""
        return self.fetchall("SELECT * FROM trades WHERE status = 'open' ORDER BY timestamp DESC")

    def get_closed_trades(self, limit: int = 100) -> list[dict]:
        """Get recent closed trades."""
        return self.fetchall(
            "SELECT * FROM trades WHERE status = 'closed' ORDER BY closed_at DESC LIMIT ?",
            (limit,),
        )

    def get_all_trades(self) -> list[dict]:
        """Get all trades."""
        return self.fetchall("SELECT * FROM trades ORDER BY timestamp DESC")

    def close_trade(self, trade_id: str, pnl: float, pnl_pct: float) -> None:
        """Close a trade with P&L.

        Args:
            trade_id: Trade ID.
            pnl: Profit/loss amount.
            pnl_pct: Profit/loss percentage.
        """
        self.update(
            "trades",
            {"status": "closed", "pnl": pnl, "pnl_pct": pnl_pct, "closed_at": datetime.now().isoformat()},
            "id = ?", (trade_id,),
        )

    def insert_portfolio_snapshot(self, snapshot: dict[str, Any]) -> int:
        """Insert daily portfolio snapshot."""
        return self.insert_or_replace("portfolio_snapshots", snapshot)

    def get_latest_snapshot(self) -> Optional[dict]:
        """Get the most recent portfolio snapshot."""
        return self.fetchone("SELECT * FROM portfolio_snapshots ORDER BY date DESC LIMIT 1")

    def get_equity_curve(self, days: int = 365) -> list[dict]:
        """Get equity curve for the last N days."""
        return self.fetchall(
            "SELECT date, total_value, daily_return, drawdown FROM portfolio_snapshots "
            "ORDER BY date DESC LIMIT ?",
            (days,),
        )

    def insert_learning_entry(self, entry: dict[str, Any]) -> int:
        """Insert learning log entry."""
        if "timestamp" not in entry:
            entry["timestamp"] = datetime.now().isoformat()
        return self.insert("learning_log", entry)

    def insert_alert(self, level: str, alert_type: str, message: str, ticker: Optional[str] = None) -> int:
        """Insert an alert."""
        return self.insert("alerts", {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "type": alert_type,
            "ticker": ticker or "",
            "message": message,
        })

    def get_unacknowledged_alerts(self) -> list[dict]:
        """Get all unacknowledged alerts."""
        return self.fetchall("SELECT * FROM alerts WHERE acknowledged = 0 ORDER BY timestamp DESC")

    def acknowledge_alert(self, alert_id: int) -> None:
        """Acknowledge an alert."""
        self.update("alerts", {"acknowledged": 1}, "id = ?", (alert_id,))

    def set_config(self, key: str, value: Any) -> None:
        """Set a config key-value pair."""
        val_str = json.dumps(value) if not isinstance(value, str) else value
        self.insert_or_replace("config", {
            "key": key, "value": val_str, "updated_at": datetime.now().isoformat(),
        })

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a config value by key."""
        row = self.fetchone("SELECT value FROM config WHERE key = ?", (key,))
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]
