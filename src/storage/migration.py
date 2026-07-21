"""Data migration — migrate existing JSON files to database + cloud.

Migrates data from flat JSON files (data/*.json) into:
1. SQLite (local OLTP)
2. Supabase (cloud backup)

Safe to run multiple times — uses upsert logic.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DataMigrator:
    """Migrate existing JSON data to structured storage."""

    def __init__(
        self,
        database: Optional[object] = None,
        cloud_sync: Optional[object] = None,
    ) -> None:
        self._db = database
        self._cloud = cloud_sync

    def migrate_trades(self, json_path: str = "data/paper_trading/trades.json") -> int:
        """Migrate trades from JSON to SQLite + Supabase.

        Args:
            json_path: Path to trades JSON file.

        Returns:
            Number of trades migrated.
        """
        path = Path(json_path)
        if not path.exists():
            logger.info("No trades file found at %s", json_path)
            return 0

        try:
            trades = json.loads(path.read_text())
            if not isinstance(trades, list):
                trades = [trades]

            count = 0
            for trade in trades:
                if self._db:
                    self._db.insert_or_replace("trades", self._flatten_trade(trade))
                    count += 1

            if self._cloud and getattr(self._cloud, "enabled", False):
                self._cloud.sync_trades(trades)

            logger.info("Migrated %d trades from %s", count, json_path)
            return count
        except Exception as exc:
            logger.warning("Trade migration failed: %s", exc)
            return 0

    def migrate_portfolio(self, json_path: str = "data/paper_trading/portfolio.json") -> bool:
        """Migrate portfolio snapshot from JSON.

        Args:
            json_path: Path to portfolio JSON.

        Returns:
            True if migrated.
        """
        path = Path(json_path)
        if not path.exists():
            return False

        try:
            data = json.loads(path.read_text())
            if self._db:
                snapshot = {
                    "date": data.get("date", "unknown"),
                    "cash": data.get("cash", data.get("current_capital", 0)),
                    "positions_value": data.get("positions_value", 0),
                    "total_value": data.get("total_value", data.get("current_capital", 0)),
                    "daily_return": data.get("daily_return", 0),
                    "cumulative_return": data.get("total_pnl_pct", 0),
                    "drawdown": data.get("max_drawdown", 0),
                    "num_positions": len(data.get("open_positions", [])),
                }
                self._db.insert_portfolio_snapshot(snapshot)

            if self._cloud and getattr(self._cloud, "enabled", False):
                self._cloud.sync_portfolio(data)

            logger.info("Migrated portfolio from %s", json_path)
            return True
        except Exception as exc:
            logger.warning("Portfolio migration failed: %s", exc)
            return False

    def migrate_learning_log(self, json_path: str = "data/paper_trading/learning_log.json") -> int:
        """Migrate learning log from JSON.

        Args:
            json_path: Path to learning log JSON.

        Returns:
            Number of entries migrated.
        """
        path = Path(json_path)
        if not path.exists():
            return 0

        try:
            entries = json.loads(path.read_text())
            if not isinstance(entries, list):
                return 0

            count = 0
            for entry in entries:
                if self._db:
                    self._db.insert_learning_entry({
                        "timestamp": entry.get("timestamp", ""),
                        "trigger": entry.get("trigger", "migration"),
                        "parameter": entry.get("metric", entry.get("parameter", "")),
                        "old_value": entry.get("old_value", 0),
                        "new_value": entry.get("new_value", 0),
                        "reason": entry.get("reason", entry.get("adjustment", "")),
                        "trades_analyzed": entry.get("trades_analyzed", 0),
                    })
                    count += 1

            if self._cloud and getattr(self._cloud, "enabled", False):
                self._cloud.sync_learning_log(entries)

            logger.info("Migrated %d learning entries from %s", count, json_path)
            return count
        except Exception as exc:
            logger.warning("Learning log migration failed: %s", exc)
            return 0

    def migrate_basket_weights(self, json_path: str = "data/basket_weights.json") -> bool:
        """Migrate basket weights from JSON.

        Args:
            json_path: Path to basket weights JSON.

        Returns:
            True if migrated.
        """
        path = Path(json_path)
        if not path.exists():
            return False

        try:
            data = json.loads(path.read_text())
            if self._db:
                self._db.insert("basket_weights", {
                    "timestamp": data.get("timestamp", "migration"),
                    "weights": json.dumps(data.get("weights", data)),
                    "accuracy": data.get("accuracy", 0),
                    "trigger": "migration",
                })

            if self._cloud and getattr(self._cloud, "enabled", False):
                self._cloud.sync_basket_weights(data)

            logger.info("Migrated basket weights from %s", json_path)
            return True
        except Exception as exc:
            logger.warning("Basket weights migration failed: %s", exc)
            return False

    def migrate_config(self, json_path: str = "data/paper_trading/config.json") -> int:
        """Migrate config key-value pairs from JSON.

        Args:
            json_path: Path to config JSON.

        Returns:
            Number of config keys migrated.
        """
        path = Path(json_path)
        if not path.exists():
            return 0

        try:
            data = json.loads(path.read_text())
            count = 0
            if self._db:
                for key, value in data.items():
                    self._db.set_config(key, value)
                    count += 1
            logger.info("Migrated %d config keys from %s", count, json_path)
            return count
        except Exception as exc:
            logger.warning("Config migration failed: %s", exc)
            return 0

    def full_migration(self) -> dict:
        """Run all migrations. Log progress.

        Returns:
            Dict with counts for each migration type.
        """
        result = {
            "trades": self.migrate_trades(),
            "portfolio": self.migrate_portfolio(),
            "learning_log": self.migrate_learning_log(),
            "basket_weights": self.migrate_basket_weights(),
            "config": self.migrate_config(),
        }
        logger.info("Full migration complete: %s", result)
        return result

    def verify_migration(self) -> dict:
        """Compare JSON file counts vs database counts.

        Returns:
            Dict with source counts and db counts for verification.
        """
        report: dict = {}

        for name, path in [
            ("trades", "data/paper_trading/trades.json"),
            ("learning_log", "data/paper_trading/learning_log.json"),
        ]:
            json_count = 0
            p = Path(path)
            if p.exists():
                try:
                    data = json.loads(p.read_text())
                    json_count = len(data) if isinstance(data, list) else 1
                except Exception:
                    pass

            db_count = 0
            if self._db:
                db_count = self._db.count(name)

            report[name] = {
                "json_count": json_count,
                "db_count": db_count,
                "match": json_count == db_count,
            }

        return report

    def _flatten_trade(self, trade: dict) -> dict:
        """Flatten a trade dict for SQLite insertion.

        Args:
            trade: Trade dict (may have nested fields).

        Returns:
            Flat dict matching trades table schema.
        """
        return {
            "id": trade.get("id", trade.get("trade_id", "")),
            "timestamp": trade.get("timestamp", trade.get("timestamp_open", "")),
            "ticker": trade.get("ticker", ""),
            "action": trade.get("action", trade.get("side", "")),
            "price": trade.get("price", trade.get("entry_price", 0)),
            "quantity": trade.get("quantity", trade.get("size", 0)),
            "pnl": trade.get("pnl"),
            "pnl_pct": trade.get("pnl_pct"),
            "status": trade.get("status", "open"),
            "strategy": trade.get("strategy", ""),
            "confidence": trade.get("confidence", 0),
            "regime": trade.get("regime", trade.get("regime_at_entry", "")),
            "stop_loss": trade.get("stop_loss"),
            "take_profit": trade.get("take_profit"),
            "entry_features": json.dumps(trade.get("signals", trade.get("entry_features", {}))),
            "closed_at": trade.get("closed_at", trade.get("timestamp_close")),
        }
