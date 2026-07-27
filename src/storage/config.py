"""Storage configuration — all credentials from environment variables.

Never hardcode credentials. Uses .env locally, Streamlit secrets in cloud.
If any var is missing, that backend falls back gracefully.
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)


class StorageConfig:
    """Centralized config for all storage backends."""

    def __init__(self) -> None:
        self.supabase_url: str = self._setting("SUPABASE_URL")
        self.supabase_key: str = self._setting("SUPABASE_KEY")

        self.firebase_creds: str = self._setting("FIREBASE_CREDENTIALS")

        self.clickhouse_host: str = self._setting("CLICKHOUSE_HOST")
        self.clickhouse_user: str = self._setting("CLICKHOUSE_USER", "default")
        self.clickhouse_password: str = self._setting("CLICKHOUSE_PASSWORD")

        self.r2_endpoint: str = self._setting("R2_ENDPOINT")
        self.r2_access_key: str = self._setting("R2_ACCESS_KEY")
        self.r2_secret_key: str = self._setting("R2_SECRET_KEY")
        self.r2_bucket: str = os.getenv("R2_BUCKET", "fly-data")

        self.redis_url: str = self._setting("REDIS_URL")

    @staticmethod
    def _setting(name: str, default: str = "") -> str:
        """Read Streamlit secrets first, then environment variables."""
        if "streamlit" in sys.modules:
            import streamlit as st

            try:
                value = st.secrets.get(name)
                if value:
                    return str(value)
            except Exception:
                pass
        return os.getenv(name, default)

    @property
    def supabase_available(self) -> bool:
        """Whether Supabase credentials are configured."""
        return bool(self.supabase_url and self.supabase_key)

    @property
    def firebase_available(self) -> bool:
        """Whether Firebase credentials are configured."""
        return bool(self.firebase_creds)

    @property
    def clickhouse_available(self) -> bool:
        """Whether ClickHouse credentials are configured."""
        return bool(self.clickhouse_host and self.clickhouse_password)

    @property
    def r2_available(self) -> bool:
        """Whether Cloudflare R2 credentials are configured."""
        return bool(self.r2_endpoint and self.r2_access_key and self.r2_secret_key)

    @property
    def redis_available(self) -> bool:
        """Whether Redis URL is configured."""
        return bool(self.redis_url)

    def status_report(self) -> dict[str, bool]:
        """Report which backends are available.

        Returns:
            Dict of backend_name -> is_available.
        """
        return {
            "supabase": self.supabase_available,
            "firebase": self.firebase_available,
            "clickhouse": self.clickhouse_available,
            "r2": self.r2_available,
            "redis": self.redis_available,
            "sqlite": True,
            "duckdb": True,
        }

    def log_status(self) -> None:
        """Log which backends are available."""
        status = self.status_report()
        cloud = [k for k, v in status.items() if v and k not in ("sqlite", "duckdb")]
        local = [k for k, v in status.items() if v and k in ("sqlite", "duckdb")]
        missing = [k for k, v in status.items() if not v]
        logger.info("Storage backends — local: %s, cloud: %s, disabled: %s", local, cloud, missing)
