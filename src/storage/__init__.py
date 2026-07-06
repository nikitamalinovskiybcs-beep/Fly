"""Fly Storage Layer — unified interface with 7 backends.

Local (always available):
    1. SQLite  — fast OLTP (trades, portfolio, configs, learning log)
    2. DuckDB  — fast OLAP (price history, signals, backtests)

Cloud (graceful fallback if not configured):
    3. Supabase  — PostgreSQL backup
    4. Firebase  — real-time state
    5. ClickHouse — analytics
    6. R2  — object storage (models, files)
    7. Redis — cache + rate limiting

Usage:
    storage = Storage()
    storage.save_trade({...})    # SQLite + Supabase (if configured)
    storage.get_trades()         # SQLite
    storage.cache_price("AAPL", 150.0)  # Redis (if configured)
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from src.storage.config import StorageConfig

logger = logging.getLogger(__name__)


class Storage:
    """Unified storage interface. Auto-selects available backends."""

    def __init__(self, config: Optional[StorageConfig] = None) -> None:
        self.config = config or StorageConfig()
        self.config.log_status()

        from src.storage.database import Database
        self.db = Database()

        self.analytics = None
        self.cloud = None
        self.firebase = None
        self.clickhouse = None
        self.r2 = None
        self.redis = None
        self.backup_manager = None

        self._init_analytics()
        self._init_cloud()
        self._init_firebase()
        self._init_clickhouse()
        self._init_r2()
        self._init_redis()
        self._init_backup()

    def _init_analytics(self) -> None:
        try:
            from src.storage.analytics_db import AnalyticsDB
            self.analytics = AnalyticsDB()
        except Exception as exc:
            logger.info("DuckDB unavailable: %s", exc)

    def _init_cloud(self) -> None:
        if self.config.supabase_available:
            try:
                from src.storage.cloud_sync import CloudSync
                self.cloud = CloudSync()
            except Exception as exc:
                logger.info("Supabase unavailable: %s", exc)

    def _init_firebase(self) -> None:
        if self.config.firebase_available:
            try:
                from src.storage.firebase_client import FirebaseStorage
                self.firebase = FirebaseStorage(self.config.firebase_creds)
            except Exception as exc:
                logger.info("Firebase unavailable: %s", exc)

    def _init_clickhouse(self) -> None:
        if self.config.clickhouse_available:
            try:
                from src.storage.clickhouse_client import ClickHouseStorage
                self.clickhouse = ClickHouseStorage(
                    host=self.config.clickhouse_host,
                    user=self.config.clickhouse_user,
                    password=self.config.clickhouse_password,
                )
            except Exception as exc:
                logger.info("ClickHouse unavailable: %s", exc)

    def _init_r2(self) -> None:
        if self.config.r2_available:
            try:
                from src.storage.r2_client import R2Storage
                self.r2 = R2Storage(
                    endpoint=self.config.r2_endpoint,
                    access_key=self.config.r2_access_key,
                    secret_key=self.config.r2_secret_key,
                    bucket=self.config.r2_bucket,
                )
            except Exception as exc:
                logger.info("R2 unavailable: %s", exc)

    def _init_redis(self) -> None:
        if self.config.redis_available:
            try:
                from src.storage.redis_client import RedisCache
                self.redis = RedisCache(self.config.redis_url)
            except Exception as exc:
                logger.info("Redis unavailable: %s", exc)

    def _init_backup(self) -> None:
        try:
            from src.storage.backup import BackupManager
            self.backup_manager = BackupManager(
                cloud_sync=self.cloud, r2_storage=self.r2,
            )
        except Exception as exc:
            logger.info("BackupManager unavailable: %s", exc)

    # ── Trade operations (SQLite + Supabase) ──

    def save_trade(self, trade: dict) -> int:
        """Save a trade to SQLite and optionally sync to Supabase."""
        row_id = self.db.insert_trade(trade)
        if self.cloud and getattr(self.cloud, "enabled", False):
            self.cloud.sync_trades([trade])
        return row_id

    def get_trades(self, status: Optional[str] = None, limit: int = 100) -> list[dict]:
        """Get trades from SQLite."""
        if status == "open":
            return self.db.get_open_trades()
        if status == "closed":
            return self.db.get_closed_trades(limit)
        return self.db.get_all_trades()

    def close_trade(self, trade_id: str, pnl: float, pnl_pct: float) -> None:
        """Close a trade."""
        self.db.close_trade(trade_id, pnl, pnl_pct)

    # ── Portfolio operations ──

    def save_snapshot(self, snapshot: dict) -> int:
        """Save portfolio snapshot."""
        row_id = self.db.insert_portfolio_snapshot(snapshot)
        if self.cloud and getattr(self.cloud, "enabled", False):
            self.cloud.sync_portfolio(snapshot)
        if self.firebase and getattr(self.firebase, "enabled", False):
            self.firebase.update_portfolio(snapshot)
        return row_id

    def get_latest_snapshot(self) -> Optional[dict]:
        """Get most recent portfolio snapshot."""
        return self.db.get_latest_snapshot()

    def get_equity_curve(self, days: int = 365) -> list[dict]:
        """Get equity curve data."""
        return self.db.get_equity_curve(days)

    # ── Learning log ──

    def save_learning(self, entry: dict) -> int:
        """Save learning log entry."""
        row_id = self.db.insert_learning_entry(entry)
        if self.cloud and getattr(self.cloud, "enabled", False):
            self.cloud.sync_learning_log([entry])
        return row_id

    # ── Alerts ──

    def save_alert(self, level: str, alert_type: str, message: str, ticker: str = "") -> int:
        """Save an alert."""
        row_id = self.db.insert_alert(level, alert_type, message, ticker)
        if self.firebase and getattr(self.firebase, "enabled", False):
            self.firebase.add_alert({"level": level, "type": alert_type, "message": message, "ticker": ticker})
        return row_id

    def get_alerts(self) -> list[dict]:
        """Get unacknowledged alerts."""
        return self.db.get_unacknowledged_alerts()

    # ── Config ──

    def set_config(self, key: str, value: Any) -> None:
        """Set config value."""
        self.db.set_config(key, value)

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get config value."""
        return self.db.get_config(key, default)

    # ── Cache (Redis) ──

    def cache_price(self, ticker: str, price: float) -> bool:
        """Cache a price in Redis."""
        if self.redis and getattr(self.redis, "enabled", False):
            return self.redis.set_price(ticker, price)
        return False

    def get_cached_price(self, ticker: str) -> Optional[float]:
        """Get cached price from Redis."""
        if self.redis and getattr(self.redis, "enabled", False):
            return self.redis.get_price(ticker)
        return None

    # ── Backup ──

    def backup(self) -> dict:
        """Run full backup."""
        if self.backup_manager:
            return self.backup_manager.full_backup()
        return {"error": "Backup manager not available"}

    # ── Status ──

    def status(self) -> dict:
        """Get storage system status."""
        result = self.config.status_report()
        result["sqlite_tables"] = self.db.table_stats()
        result["sqlite_size_mb"] = round(self.db.db_size_bytes() / 1024 / 1024, 2)
        if self.analytics and self.analytics.available:
            result["duckdb_tables"] = self.analytics.table_stats()
        if self.redis and getattr(self.redis, "enabled", False):
            result["redis_stats"] = self.redis.cache_stats()
        if self.backup_manager:
            result["backup_status"] = self.backup_manager.get_backup_status()
        return result
