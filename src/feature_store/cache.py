"""Feature cache with TTL. DuckDB-backed with in-memory fallback.

If duckdb is unavailable, transparently falls back to an in-process dict
so the feature store keeps working (values just aren't persisted).
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DB_DIR = Path("data")
DB_PATH = DB_DIR / "feature_cache.duckdb"
DEFAULT_TTL_HOURS = 4  # recompute after 4 hours


class FeatureCache:
    """TTL cache for computed features.

    Backend priority: DuckDB (persistent) -> in-memory dict (fallback).
    """

    def __init__(self, ttl_hours: int = DEFAULT_TTL_HOURS):
        self.ttl_hours = ttl_hours
        self.conn = None
        self._mem: dict[tuple[str, str, str], tuple[float, datetime]] = {}
        self._connect()

    def _connect(self) -> None:
        try:
            import duckdb

            DB_DIR.mkdir(parents=True, exist_ok=True)
            self.conn = duckdb.connect(str(DB_PATH))
            self._create_table()
            logger.info("FeatureCache using DuckDB at %s", DB_PATH)
        except ImportError:
            logger.info("duckdb not available — FeatureCache using in-memory fallback")
            self.conn = None
        except Exception as exc:
            logger.warning("FeatureCache DuckDB init failed (%s) — using in-memory", exc)
            self.conn = None

    def _create_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS features (
                ticker VARCHAR,
                date VARCHAR,
                feature_name VARCHAR,
                value DOUBLE,
                computed_at TIMESTAMP,
                PRIMARY KEY (ticker, date, feature_name)
            )
            """
        )

    def _is_fresh(self, computed_at: datetime) -> bool:
        return datetime.now() - computed_at <= timedelta(hours=self.ttl_hours)

    def get(self, ticker: str, date: str, feature_name: str) -> float | None:
        """Return cached value if fresh (within TTL), else None."""
        if self.conn is not None:
            row = self.conn.execute(
                "SELECT value, computed_at FROM features WHERE ticker=? AND date=? AND feature_name=?",
                [ticker, date, feature_name],
            ).fetchone()
            if row is None:
                return None
            value, computed_at = row
            return value if self._is_fresh(computed_at) else None
        entry = self._mem.get((ticker, date, feature_name))
        if entry is None:
            return None
        value, computed_at = entry
        return value if self._is_fresh(computed_at) else None

    def set(self, ticker: str, date: str, feature_name: str, value: float) -> None:
        """Upsert a feature value."""
        now = datetime.now()
        if self.conn is not None:
            self.conn.execute(
                """INSERT OR REPLACE INTO features (ticker, date, feature_name, value, computed_at)
                   VALUES (?, ?, ?, ?, ?)""",
                [ticker, date, feature_name, value, now],
            )
        else:
            self._mem[(ticker, date, feature_name)] = (value, now)

    def get_vector(self, ticker: str, date: str) -> dict[str, float]:
        """Return all fresh cached features for ticker+date."""
        if self.conn is not None:
            rows = self.conn.execute(
                "SELECT feature_name, value, computed_at FROM features WHERE ticker=? AND date=?",
                [ticker, date],
            ).fetchall()
            return {name: val for name, val, ts in rows if self._is_fresh(ts)}
        out: dict[str, float] = {}
        for (t, d, name), (val, ts) in self._mem.items():
            if t == ticker and d == date and self._is_fresh(ts):
                out[name] = val
        return out

    def invalidate(self, ticker: str | None = None) -> None:
        """Clear cache. If ticker given, only that ticker."""
        if self.conn is not None:
            if ticker:
                self.conn.execute("DELETE FROM features WHERE ticker=?", [ticker])
            else:
                self.conn.execute("DELETE FROM features")
        else:
            if ticker:
                self._mem = {k: v for k, v in self._mem.items() if k[0] != ticker}
            else:
                self._mem = {}

    def stats(self) -> dict:
        """Return cache statistics."""
        if self.conn is not None:
            total = self.conn.execute("SELECT COUNT(*) FROM features").fetchone()[0]
            stale = self.conn.execute(
                "SELECT COUNT(*) FROM features WHERE computed_at < ?",
                [datetime.now() - timedelta(hours=self.ttl_hours)],
            ).fetchone()[0]
        else:
            total = len(self._mem)
            stale = sum(1 for _, ts in self._mem.values() if not self._is_fresh(ts))
        return {
            "backend": "duckdb" if self.conn is not None else "memory",
            "total_entries": total,
            "stale_entries": stale,
            "fresh_entries": total - stale,
        }
