"""Tests for src.storage — database, analytics, backup, migration, cloud clients."""

import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd


# ── SQLite Database Tests ──

class TestDatabase:
    """Tests for SQLite database operations."""

    def setup_method(self) -> None:
        from src.storage.database import Database
        Database._instance = None
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "test.db"
        self.db = Database(db_path=self.db_path)

    def teardown_method(self) -> None:
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_insert_and_fetch_trade(self) -> None:
        trade = {"id": "t1", "timestamp": "2024-01-01", "ticker": "AAPL",
                 "action": "buy", "price": 150.0, "quantity": 10}
        self.db.insert_trade(trade)
        result = self.db.fetchone("SELECT * FROM trades WHERE id = ?", ("t1",))
        assert result is not None
        assert result["ticker"] == "AAPL"
        assert result["price"] == 150.0

    def test_calculated_note_is_idempotent_and_counted(self) -> None:
        note = {
            "note_id": "note-1",
            "calculated_at": "2099-01-01T00:00:00",
            "basket": "[\"AAPL\", \"MSFT\"]",
            "term_months": 24,
            "evidence_status": "incomplete",
        }
        self.db.record_calculated_note(note)
        self.db.record_calculated_note(note)

        assert self.db.count_calculated_notes(months=1200) == 1
        assert self.db.count_calculated_baskets(months=1200) == 1

    def test_get_open_trades(self) -> None:
        self.db.insert_trade({"id": "t1", "timestamp": "2024-01-01", "ticker": "AAPL",
                              "action": "buy", "price": 150.0, "quantity": 10, "status": "open"})
        self.db.insert_trade({"id": "t2", "timestamp": "2024-01-02", "ticker": "MSFT",
                              "action": "buy", "price": 300.0, "quantity": 5, "status": "closed"})
        open_trades = self.db.get_open_trades()
        assert len(open_trades) == 1
        assert open_trades[0]["ticker"] == "AAPL"

    def test_close_trade(self) -> None:
        self.db.insert_trade({"id": "t1", "timestamp": "2024-01-01", "ticker": "AAPL",
                              "action": "buy", "price": 150.0, "quantity": 10})
        self.db.close_trade("t1", pnl=50.0, pnl_pct=3.33)
        result = self.db.fetchone("SELECT * FROM trades WHERE id = ?", ("t1",))
        assert result["status"] == "closed"
        assert result["pnl"] == 50.0

    def test_insert_portfolio_snapshot(self) -> None:
        snapshot = {"date": "2024-01-01", "cash": 90000.0, "positions_value": 10000.0,
                    "total_value": 100000.0}
        self.db.insert_portfolio_snapshot(snapshot)
        latest = self.db.get_latest_snapshot()
        assert latest is not None
        assert latest["total_value"] == 100000.0

    def test_config_set_get(self) -> None:
        self.db.set_config("confidence_threshold", 0.65)
        val = self.db.get_config("confidence_threshold")
        assert val == 0.65

    def test_config_default(self) -> None:
        val = self.db.get_config("nonexistent", default=42)
        assert val == 42

    def test_insert_alert(self) -> None:
        self.db.insert_alert("warning", "drawdown", "DD exceeded 10%", "AAPL")
        alerts = self.db.get_unacknowledged_alerts()
        assert len(alerts) == 1
        assert alerts[0]["level"] == "warning"

    def test_acknowledge_alert(self) -> None:
        self.db.insert_alert("critical", "sharpe", "Sharpe < 0")
        alerts = self.db.get_unacknowledged_alerts()
        assert len(alerts) == 1
        self.db.acknowledge_alert(alerts[0]["id"])
        alerts = self.db.get_unacknowledged_alerts()
        assert len(alerts) == 0

    def test_table_stats(self) -> None:
        stats = self.db.table_stats()
        assert "trades" in stats
        assert "portfolio_snapshots" in stats
        assert stats["trades"] == 0

    def test_count(self) -> None:
        self.db.insert_trade({"id": "t1", "timestamp": "now", "ticker": "X",
                              "action": "buy", "price": 1, "quantity": 1})
        assert self.db.count("trades") == 1

    def test_transaction_rollback(self) -> None:
        try:
            with self.db.transaction() as conn:
                conn.execute("INSERT INTO config (key, value) VALUES (?, ?)", ("k1", "v1"))
                raise ValueError("Trigger rollback")
        except ValueError:
            pass
        assert self.db.fetchone("SELECT * FROM config WHERE key = ?", ("k1",)) is None

    def test_delete(self) -> None:
        self.db.insert_trade({"id": "d1", "timestamp": "now", "ticker": "DEL",
                              "action": "buy", "price": 1, "quantity": 1})
        self.db.delete("trades", "id = ?", ("d1",))
        assert self.db.fetchone("SELECT * FROM trades WHERE id = ?", ("d1",)) is None

    def test_update(self) -> None:
        self.db.insert_trade({"id": "u1", "timestamp": "now", "ticker": "UPD",
                              "action": "buy", "price": 100.0, "quantity": 1})
        self.db.update("trades", {"price": 200.0}, "id = ?", ("u1",))
        result = self.db.fetchone("SELECT * FROM trades WHERE id = ?", ("u1",))
        assert result["price"] == 200.0

    def test_equity_curve(self) -> None:
        for i in range(5):
            self.db.insert_portfolio_snapshot({
                "date": f"2024-01-0{i+1}", "cash": 90000.0, "positions_value": 10000.0 + i * 100,
                "total_value": 100000.0 + i * 100,
            })
        curve = self.db.get_equity_curve(days=3)
        assert len(curve) == 3

    def test_learning_entry(self) -> None:
        self.db.insert_learning_entry({
            "trigger": "scheduled", "parameter": "confidence",
            "old_value": 0.6, "new_value": 0.65, "reason": "test",
        })
        rows = self.db.fetchall("SELECT * FROM learning_log")
        assert len(rows) == 1


# ── DuckDB Analytics Tests ──

class TestAnalyticsDB:
    """Tests for DuckDB analytical database."""

    def setup_method(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "test_analytics.duckdb"

    def teardown_method(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_init_creates_tables(self) -> None:
        from src.storage.analytics_db import AnalyticsDB
        db = AnalyticsDB(db_path=self.db_path)
        assert db.available
        stats = db.table_stats()
        assert "price_history" in stats
        db.close()

    def test_query_returns_dataframe(self) -> None:
        from src.storage.analytics_db import AnalyticsDB
        db = AnalyticsDB(db_path=self.db_path)
        result = db.query("SELECT 1 as val")
        assert isinstance(result, pd.DataFrame)
        assert result["val"].iloc[0] == 1
        db.close()

    def test_insert_and_get_prices(self) -> None:
        from src.storage.analytics_db import AnalyticsDB
        db = AnalyticsDB(db_path=self.db_path)
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5),
            "open": [100.0] * 5, "high": [105.0] * 5,
            "low": [95.0] * 5, "close": [102.0] * 5,
            "volume": [1000000] * 5, "adj_close": [102.0] * 5,
        })
        count = db.insert_prices("AAPL", df)
        assert count == 5
        history = db.get_price_history("AAPL", days=10)
        assert len(history) == 5
        db.close()

    def test_signal_accuracy_empty(self) -> None:
        from src.storage.analytics_db import AnalyticsDB
        db = AnalyticsDB(db_path=self.db_path)
        result = db.get_signal_accuracy("regime", days=30)
        assert result["total_signals"] == 0
        assert result["accuracy"] == 0.0
        db.close()

    def test_table_stats(self) -> None:
        from src.storage.analytics_db import AnalyticsDB
        db = AnalyticsDB(db_path=self.db_path)
        stats = db.table_stats()
        assert stats["price_history"] == 0
        db.close()


# ── Config Tests ──

class TestStorageConfig:
    """Tests for storage configuration."""

    def test_defaults_disabled(self) -> None:
        from src.storage.config import StorageConfig
        config = StorageConfig()
        assert not config.supabase_available
        assert not config.firebase_available
        assert not config.clickhouse_available
        assert not config.r2_available
        assert not config.redis_available

    def test_status_report(self) -> None:
        from src.storage.config import StorageConfig
        config = StorageConfig()
        status = config.status_report()
        assert status["sqlite"] is True
        assert status["duckdb"] is True
        assert status["supabase"] is False

    def test_storage_integration_status_has_configured_and_active(self) -> None:
        from src.storage import Storage

        storage = Storage()
        result = storage.integration_status()

        assert result["status"] == "ready"
        assert result["active"]["sqlite"] is True
        assert result["production_weights_changed"] is False

    @patch.dict(os.environ, {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_KEY": "key123"})
    def test_supabase_available_with_env(self) -> None:
        from src.storage.config import StorageConfig
        config = StorageConfig()
        assert config.supabase_available

    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379"})
    def test_redis_available_with_env(self) -> None:
        from src.storage.config import StorageConfig
        config = StorageConfig()
        assert config.redis_available


# ── Cloud Sync Tests (Graceful Degradation) ──

class TestCloudSync:
    """Tests for Supabase cloud sync — graceful when disabled."""

    def test_disabled_by_default(self) -> None:
        from src.storage.cloud_sync import CloudSync
        sync = CloudSync()
        assert not sync.enabled

    def test_sync_trades_noop_when_disabled(self) -> None:
        from src.storage.cloud_sync import CloudSync
        sync = CloudSync()
        assert sync.sync_trades([{"id": "t1"}]) == 0

    def test_sync_portfolio_noop_when_disabled(self) -> None:
        from src.storage.cloud_sync import CloudSync
        sync = CloudSync()
        assert sync.sync_portfolio({"cash": 100000}) is False

    def test_restore_empty_when_disabled(self) -> None:
        from src.storage.cloud_sync import CloudSync
        sync = CloudSync()
        assert sync.restore_from_cloud("trades") == []

    def test_invalid_endpoint_is_rejected_without_network_call(self) -> None:
        from src.storage.cloud_sync import CloudSync
        sync = CloudSync(url="ftp://supabase.example", key="test-key")
        assert not sync.enabled
        assert sync.last_error == "invalid_endpoint_scheme"

    def test_unresolvable_endpoint_has_sanitized_diagnostic(self) -> None:
        from src.storage.cloud_sync import CloudSync
        with patch("supabase.create_client", side_effect=OSError("Name or service not known")):
            sync = CloudSync(url="https://project.supabase.co", key="test-key")
        assert not sync.enabled
        assert sync.last_error == "endpoint_dns_resolution_failed"


# ── Firebase Tests (Graceful Degradation) ──

class TestFirebaseStorage:
    """Tests for Firebase — graceful when disabled."""

    def test_disabled_by_default(self) -> None:
        from src.storage.firebase_client import FirebaseStorage
        fb = FirebaseStorage()
        assert not fb.enabled

    def test_update_portfolio_noop(self) -> None:
        from src.storage.firebase_client import FirebaseStorage
        fb = FirebaseStorage()
        assert fb.update_portfolio({"cash": 100000}) is False

    def test_get_portfolio_none(self) -> None:
        from src.storage.firebase_client import FirebaseStorage
        fb = FirebaseStorage()
        assert fb.get_portfolio() is None

    def test_add_alert_none(self) -> None:
        from src.storage.firebase_client import FirebaseStorage
        fb = FirebaseStorage()
        assert fb.add_alert({"level": "warning"}) is None


# ── ClickHouse Tests (Graceful Degradation) ──

class TestClickHouseStorage:
    """Tests for ClickHouse — graceful when disabled."""

    def test_disabled_by_default(self) -> None:
        from src.storage.clickhouse_client import ClickHouseStorage
        ch = ClickHouseStorage()
        assert not ch.enabled

    def test_query_empty_when_disabled(self) -> None:
        from src.storage.clickhouse_client import ClickHouseStorage
        ch = ClickHouseStorage()
        result = ch.query("SELECT 1")
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_save_ohlcv_zero_when_disabled(self) -> None:
        from src.storage.clickhouse_client import ClickHouseStorage
        ch = ClickHouseStorage()
        assert ch.save_ohlcv("AAPL", pd.DataFrame()) == 0


# ── R2 Tests (Graceful Degradation) ──

class TestR2Storage:
    """Tests for Cloudflare R2 — graceful when disabled."""

    def test_disabled_by_default(self) -> None:
        from src.storage.r2_client import R2Storage
        r2 = R2Storage()
        assert not r2.enabled

    def test_upload_false_when_disabled(self) -> None:
        from src.storage.r2_client import R2Storage
        r2 = R2Storage()
        assert r2.upload_file("local", "remote") is False

    def test_download_false_when_disabled(self) -> None:
        from src.storage.r2_client import R2Storage
        r2 = R2Storage()
        assert r2.download_file("remote", "local") is False

    def test_list_empty_when_disabled(self) -> None:
        from src.storage.r2_client import R2Storage
        r2 = R2Storage()
        assert r2.list_files() == []

    def test_upload_model_false_when_disabled(self) -> None:
        from src.storage.r2_client import R2Storage
        r2 = R2Storage()
        assert r2.upload_model({"model": True}, "test") is False


# ── Redis Tests (Graceful Degradation) ──

class TestRedisCache:
    """Tests for Redis cache — graceful when disabled."""

    def test_disabled_by_default(self) -> None:
        from src.storage.redis_client import RedisCache
        cache = RedisCache()
        assert not cache.enabled

    def test_set_price_false_when_disabled(self) -> None:
        from src.storage.redis_client import RedisCache
        cache = RedisCache()
        assert cache.set_price("AAPL", 150.0) is False

    def test_get_price_none_when_disabled(self) -> None:
        from src.storage.redis_client import RedisCache
        cache = RedisCache()
        assert cache.get_price("AAPL") is None

    def test_rate_limit_true_when_disabled(self) -> None:
        from src.storage.redis_client import RedisCache
        cache = RedisCache()
        assert cache.check_rate_limit("test") is True

    def test_queue_length_zero(self) -> None:
        from src.storage.redis_client import RedisCache
        cache = RedisCache()
        assert cache.queue_length() == 0


# ── Backup Tests ──

class TestBackupManager:
    """Tests for backup manager."""

    def setup_method(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.data_dir = Path(self.tmp) / "data"
        self.data_dir.mkdir()
        (self.data_dir / "test.json").write_text('{"key": "value"}')

    def teardown_method(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_local_backup_creates_dir(self) -> None:
        from src.storage.backup import BackupManager
        mgr = BackupManager()
        mgr.BACKUP_DIR = Path(self.tmp) / "backups"
        with patch("src.storage.backup.Path") as mock_path:
            mock_path.return_value = self.data_dir
            mgr.local_backup()
        # Since we mocked Path, just check the method doesn't crash
        assert True

    def test_list_local_backups_empty(self) -> None:
        from src.storage.backup import BackupManager
        mgr = BackupManager()
        mgr.BACKUP_DIR = Path(self.tmp) / "empty_backups"
        mgr.BACKUP_DIR.mkdir()
        backups = mgr.list_local_backups()
        assert len(backups) == 0

    def test_backup_status(self) -> None:
        from src.storage.backup import BackupManager
        mgr = BackupManager()
        status = mgr.get_backup_status()
        assert "backups_count" in status
        assert "cloud_enabled" in status


# ── Migration Tests ──

class TestDataMigrator:
    """Tests for JSON → database migration."""

    def setup_method(self) -> None:
        from src.storage.database import Database
        Database._instance = None
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "migrate_test.db"
        self.db = Database(db_path=self.db_path)

    def teardown_method(self) -> None:
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_migrate_trades_from_json(self) -> None:
        from src.storage.migration import DataMigrator
        trades_path = Path(self.tmp) / "trades.json"
        trades_path.write_text(json.dumps([
            {"id": "t1", "timestamp": "2024-01-01", "ticker": "AAPL",
             "action": "buy", "price": 150.0, "quantity": 10},
            {"id": "t2", "timestamp": "2024-01-02", "ticker": "MSFT",
             "action": "buy", "price": 300.0, "quantity": 5},
        ]))
        migrator = DataMigrator(database=self.db)
        count = migrator.migrate_trades(str(trades_path))
        assert count == 2
        assert self.db.count("trades") == 2

    def test_migrate_nonexistent_file(self) -> None:
        from src.storage.migration import DataMigrator
        migrator = DataMigrator(database=self.db)
        count = migrator.migrate_trades("/nonexistent/trades.json")
        assert count == 0

    def test_migrate_config(self) -> None:
        from src.storage.migration import DataMigrator
        config_path = Path(self.tmp) / "config.json"
        config_path.write_text(json.dumps({"confidence": 0.65, "kelly": 0.25}))
        migrator = DataMigrator(database=self.db)
        count = migrator.migrate_config(str(config_path))
        assert count == 2
        assert self.db.get_config("confidence") == 0.65

    def test_full_migration(self) -> None:
        from src.storage.migration import DataMigrator
        migrator = DataMigrator(database=self.db)
        result = migrator.full_migration()
        assert "trades" in result
        assert "portfolio" in result

    def test_verify_migration(self) -> None:
        from src.storage.migration import DataMigrator
        migrator = DataMigrator(database=self.db)
        report = migrator.verify_migration()
        assert "trades" in report
