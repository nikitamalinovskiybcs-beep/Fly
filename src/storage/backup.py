"""Backup manager — local + cloud automated backups.

Triggers:
    - Every 50 closed trades → local backup
    - Every hour → Supabase sync
    - Every day → R2 full backup
    - Manual → from Streamlit UI or CLI
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class BackupManager:
    """Automated backup system with local and cloud support."""

    BACKUP_DIR = Path("data/backups")
    MAX_LOCAL_BACKUPS = 10

    def __init__(
        self,
        cloud_sync: Optional[object] = None,
        r2_storage: Optional[object] = None,
    ) -> None:
        self._cloud = cloud_sync
        self._r2 = r2_storage
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def local_backup(self) -> Optional[str]:
        """Create local backup of data/ directory.

        Returns:
            Path to backup directory, or None on failure.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.BACKUP_DIR / timestamp
        source = Path("data")
        try:
            files_to_backup = []
            for pattern in ("*.json", "*.db", "*.duckdb"):
                files_to_backup.extend(source.rglob(pattern))

            if not files_to_backup:
                logger.warning("No data files found to backup")
                return None

            backup_path.mkdir(parents=True, exist_ok=True)
            for f in files_to_backup:
                if "backups" in str(f):
                    continue
                rel = f.relative_to(source)
                dest = backup_path / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(f), str(dest))

            logger.info("Local backup created: %s", backup_path)
            self._cleanup_old_backups()
            return str(backup_path)
        except Exception as exc:
            logger.warning("Local backup failed: %s", exc)
            return None

    def cloud_backup(self) -> bool:
        """Sync critical data to Supabase.

        Returns:
            True if synced successfully.
        """
        if not self._cloud or not getattr(self._cloud, "enabled", False):
            return False
        try:
            db_path = Path("data/fly.db")
            if not db_path.exists():
                return False

            import sqlite3
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            trades = [dict(r) for r in conn.execute("SELECT * FROM trades").fetchall()]
            if trades:
                self._cloud.sync_trades(trades)

            snapshot = conn.execute(
                "SELECT * FROM portfolio_snapshots ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if snapshot:
                self._cloud.sync_portfolio(dict(snapshot))

            learning = [dict(r) for r in conn.execute("SELECT * FROM learning_log").fetchall()]
            if learning:
                self._cloud.sync_learning_log(learning)

            conn.close()
            logger.info("Cloud backup completed")
            return True
        except Exception as exc:
            logger.warning("Cloud backup failed: %s", exc)
            return False

    def full_backup(self) -> dict:
        """Run both local and cloud backups.

        Returns:
            Dict with local_path, cloud_synced, r2_uploaded.
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "local_path": self.local_backup(),
            "cloud_synced": self.cloud_backup(),
            "r2_uploaded": False,
        }
        if self._r2 and getattr(self._r2, "enabled", False):
            prefix = self._r2.create_backup("data/")
            result["r2_uploaded"] = prefix is not None
        return result

    def restore_from_local(self, backup_name: str) -> bool:
        """Restore from a local backup.

        Args:
            backup_name: Backup directory name (timestamp).

        Returns:
            True if restored successfully.
        """
        backup_path = self.BACKUP_DIR / backup_name
        if not backup_path.exists():
            logger.warning("Backup not found: %s", backup_path)
            return False
        try:
            dest = Path("data")
            for f in backup_path.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(backup_path)
                    target = dest / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(f), str(target))
            logger.info("Restored from backup: %s", backup_name)
            return True
        except Exception as exc:
            logger.warning("Restore failed: %s", exc)
            return False

    def list_local_backups(self) -> list[dict]:
        """List available local backups.

        Returns:
            List of dicts with name, timestamp, file_count, size_mb.
        """
        backups = []
        if not self.BACKUP_DIR.exists():
            return backups
        for d in sorted(self.BACKUP_DIR.iterdir(), reverse=True):
            if d.is_dir() and d.name != "__pycache__":
                files = list(d.rglob("*"))
                file_count = sum(1 for f in files if f.is_file())
                size = sum(f.stat().st_size for f in files if f.is_file())
                backups.append({
                    "name": d.name,
                    "timestamp": d.name,
                    "file_count": file_count,
                    "size_mb": round(size / 1024 / 1024, 2),
                })
        return backups

    def _cleanup_old_backups(self) -> None:
        """Remove oldest backups keeping only MAX_LOCAL_BACKUPS."""
        if not self.BACKUP_DIR.exists():
            return
        dirs = sorted(
            [d for d in self.BACKUP_DIR.iterdir() if d.is_dir()],
            key=lambda d: d.name,
        )
        while len(dirs) > self.MAX_LOCAL_BACKUPS:
            oldest = dirs.pop(0)
            shutil.rmtree(str(oldest))
            logger.info("Removed old backup: %s", oldest.name)

    def get_backup_status(self) -> dict:
        """Get backup system status.

        Returns:
            Dict with last_local, last_cloud, backups_count, total_size_mb.
        """
        backups = self.list_local_backups()
        total_size = sum(b["size_mb"] for b in backups)
        return {
            "last_local": backups[0]["timestamp"] if backups else None,
            "backups_count": len(backups),
            "total_size_mb": round(total_size, 2),
            "cloud_enabled": bool(self._cloud and getattr(self._cloud, "enabled", False)),
            "r2_enabled": bool(self._r2 and getattr(self._r2, "enabled", False)),
        }
