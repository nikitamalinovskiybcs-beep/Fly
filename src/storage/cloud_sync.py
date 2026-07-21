"""Cloud sync — Supabase (PostgreSQL) for critical data backup.

Free tier: 500MB database + 1GB files + 50K requests/month.
Graceful degradation: if no keys configured, all operations are no-ops.

Environment variables:
    SUPABASE_URL=https://xxx.supabase.co
    SUPABASE_KEY=eyJhbGci...
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CloudSync:
    """Sync critical data to Supabase PostgreSQL."""

    def __init__(self) -> None:
        self._url = os.getenv("SUPABASE_URL", "")
        self._key = os.getenv("SUPABASE_KEY", "")
        self._client = None
        self._enabled = False

        if self._url and self._key:
            try:
                from supabase import create_client
                self._client = create_client(self._url, self._key)
                self._enabled = True
                logger.info("Supabase cloud sync enabled")
            except ImportError:
                logger.info("supabase package not installed, cloud sync disabled")
            except Exception as exc:
                logger.warning("Supabase init failed: %s", exc)

    @property
    def enabled(self) -> bool:
        """Whether cloud sync is active."""
        return self._enabled

    def sync_trades(self, trades: list[dict]) -> int:
        """Sync trades to Supabase.

        Args:
            trades: List of trade dicts.

        Returns:
            Number of trades synced.
        """
        if not self._enabled or not trades:
            return 0
        try:
            clean = [self._clean_for_json(t) for t in trades]
            self._client.table("trades").upsert(clean).execute()
            logger.info("Synced %d trades to Supabase", len(clean))
            return len(clean)
        except Exception as exc:
            logger.warning("Trade sync failed: %s", exc)
            return 0

    def sync_portfolio(self, snapshot: dict) -> bool:
        """Sync portfolio snapshot to Supabase.

        Args:
            snapshot: Portfolio snapshot dict.

        Returns:
            True if synced successfully.
        """
        if not self._enabled:
            return False
        try:
            clean = self._clean_for_json(snapshot)
            self._client.table("portfolio_snapshots").upsert(clean).execute()
            return True
        except Exception as exc:
            logger.warning("Portfolio sync failed: %s", exc)
            return False

    def sync_learning_log(self, entries: list[dict]) -> int:
        """Sync learning log entries to Supabase.

        Args:
            entries: List of learning log dicts.

        Returns:
            Number of entries synced.
        """
        if not self._enabled or not entries:
            return 0
        try:
            clean = [self._clean_for_json(e) for e in entries]
            self._client.table("learning_log").insert(clean).execute()
            return len(clean)
        except Exception as exc:
            logger.warning("Learning log sync failed: %s", exc)
            return 0

    def sync_basket_weights(self, weights: dict) -> bool:
        """Sync basket weights to Supabase.

        Args:
            weights: Basket weights dict.

        Returns:
            True if synced successfully.
        """
        if not self._enabled:
            return False
        try:
            data = {
                "timestamp": datetime.now().isoformat(),
                "weights": json.dumps(weights),
            }
            self._client.table("basket_weights").insert(data).execute()
            return True
        except Exception as exc:
            logger.warning("Basket weights sync failed: %s", exc)
            return False

    def sync_daily_pnl(self, pnl_data: dict) -> bool:
        """Sync daily P&L to Supabase.

        Args:
            pnl_data: Daily P&L dict.

        Returns:
            True if synced.
        """
        if not self._enabled:
            return False
        try:
            clean = self._clean_for_json(pnl_data)
            self._client.table("daily_pnl").upsert(clean).execute()
            return True
        except Exception as exc:
            logger.warning("Daily PnL sync failed: %s", exc)
            return False

    def restore_from_cloud(self, table: str, limit: int = 10000) -> list[dict]:
        """Download data from Supabase for disaster recovery.

        Args:
            table: Table name to restore.
            limit: Max rows to fetch.

        Returns:
            List of row dicts from Supabase.
        """
        if not self._enabled:
            return []
        try:
            response = self._client.table(table).select("*").limit(limit).execute()
            return response.data or []
        except Exception as exc:
            logger.warning("Restore from cloud failed: %s", exc)
            return []

    def get_last_sync_time(self) -> Optional[str]:
        """Get timestamp of last successful sync.

        Returns:
            ISO timestamp string or None.
        """
        if not self._enabled:
            return None
        try:
            response = (
                self._client.table("portfolio_snapshots")
                .select("created_at")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0].get("created_at")
            return None
        except Exception:
            return None

    def _clean_for_json(self, data: dict) -> dict:
        """Remove non-serializable values from a dict.

        Args:
            data: Input dict.

        Returns:
            Cleaned dict safe for JSON serialization.
        """
        clean: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, (str, int, float, bool, type(None))):
                clean[k] = v
            elif isinstance(v, dict):
                clean[k] = json.dumps(v)
            elif isinstance(v, (list, tuple)):
                clean[k] = json.dumps(v)
            else:
                clean[k] = str(v)
        return clean
