"""Database migrations — CREATE TABLE statements for SQLite.

Safe to run multiple times (IF NOT EXISTS).
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)

TABLES_SQL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS trades (
        id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        ticker TEXT NOT NULL,
        action TEXT NOT NULL,
        price REAL NOT NULL,
        quantity REAL NOT NULL,
        pnl REAL,
        pnl_pct REAL,
        status TEXT DEFAULT 'open',
        strategy TEXT,
        confidence REAL,
        regime TEXT,
        stop_loss REAL,
        take_profit REAL,
        entry_features TEXT,
        exit_features TEXT,
        closed_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker)",
    "CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)",
    "CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)",
    """
    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT UNIQUE NOT NULL,
        cash REAL NOT NULL,
        positions_value REAL NOT NULL,
        total_value REAL NOT NULL,
        daily_return REAL,
        cumulative_return REAL,
        drawdown REAL,
        num_positions INTEGER,
        sharpe_30d REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        trigger TEXT NOT NULL,
        parameter TEXT NOT NULL,
        old_value REAL,
        new_value REAL,
        reason TEXT,
        trades_analyzed INTEGER,
        sharpe_before REAL,
        sharpe_after REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS basket_weights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        weights TEXT NOT NULL,
        accuracy REAL,
        trigger TEXT,
        baskets_analyzed INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        level TEXT NOT NULL,
        type TEXT NOT NULL,
        ticker TEXT,
        message TEXT NOT NULL,
        acknowledged INTEGER DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS basket_evolution_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        generation INTEGER,
        weights TEXT NOT NULL,
        fitness REAL,
        accuracy REAL,
        sharpe REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS calculated_notes (
        note_id TEXT PRIMARY KEY,
        calculated_at TEXT NOT NULL,
        basket TEXT NOT NULL,
        barrier REAL,
        term_months INTEGER NOT NULL,
        coupon_pa REAL,
        p_ki REAL,
        verdict TEXT,
        evidence_status TEXT,
        lifecycle_status TEXT DEFAULT 'calculated',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_calculated_notes_at ON calculated_notes(calculated_at)",
]


def run_migrations(conn: sqlite3.Connection) -> None:
    """Create all tables if not exist. Safe to run multiple times.

    Args:
        conn: SQLite connection.
    """
    cursor = conn.cursor()
    for sql in TABLES_SQL:
        try:
            cursor.execute(sql)
        except sqlite3.Error as exc:
            logger.warning("Migration error: %s", exc)
    conn.commit()
    logger.info("Database migrations complete (%d statements)", len(TABLES_SQL))
