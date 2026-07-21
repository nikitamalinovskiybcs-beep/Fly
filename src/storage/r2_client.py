"""Cloudflare R2 client — S3-compatible object storage for large files.

Free tier: 10GB storage, 1M requests/month, $0 egress.
Used for: trained models (.pkl), Numerai parquets, database backups.

Environment variables:
    R2_ENDPOINT=https://xxx.r2.cloudflarestorage.com
    R2_ACCESS_KEY=xxx
    R2_SECRET_KEY=xxx
    R2_BUCKET=fly-data
"""

import io
import logging
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class R2Storage:
    """Object storage via Cloudflare R2 (S3-compatible).

    Buckets (logical prefixes):
        models/   — trained ML models (.pkl, .joblib)
        data/     — Numerai parquets, CSV exports
        backups/  — daily database backups
    """

    def __init__(
        self,
        endpoint: str = "",
        access_key: str = "",
        secret_key: str = "",
        bucket: str = "fly-data",
    ) -> None:
        self._s3 = None
        self._bucket = bucket
        self._enabled = False

        if not endpoint or not access_key or not secret_key:
            logger.info("R2 not configured, object storage disabled")
            return

        try:
            import boto3
            self._s3 = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
            self._enabled = True
            logger.info("Cloudflare R2 connected: %s", endpoint)
        except ImportError:
            logger.info("boto3 not installed, R2 disabled")
        except Exception as exc:
            logger.warning("R2 init failed: %s", exc)

    @property
    def enabled(self) -> bool:
        """Whether R2 is available."""
        return self._enabled

    def upload_file(self, local_path: str, remote_key: str) -> bool:
        """Upload a local file to R2.

        Args:
            local_path: Path to local file.
            remote_key: Object key in R2 (e.g. "models/xgb_v1.pkl").

        Returns:
            True if uploaded successfully.
        """
        if not self._enabled:
            return False
        try:
            self._s3.upload_file(local_path, self._bucket, remote_key)
            logger.info("Uploaded %s → R2:%s", local_path, remote_key)
            return True
        except Exception as exc:
            logger.warning("R2 upload failed: %s", exc)
            return False

    def download_file(self, remote_key: str, local_path: str) -> bool:
        """Download a file from R2.

        Args:
            remote_key: Object key in R2.
            local_path: Local destination path.

        Returns:
            True if downloaded successfully.
        """
        if not self._enabled:
            return False
        try:
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            self._s3.download_file(self._bucket, remote_key, local_path)
            logger.info("Downloaded R2:%s → %s", remote_key, local_path)
            return True
        except Exception as exc:
            logger.warning("R2 download failed: %s", exc)
            return False

    def upload_model(self, model: Any, name: str) -> bool:
        """Serialize and upload a Python model.

        Args:
            model: Picklable model object.
            name: Model name (without extension).

        Returns:
            True if uploaded.
        """
        if not self._enabled:
            return False
        try:
            buf = io.BytesIO()
            pickle.dump(model, buf)
            buf.seek(0)
            key = f"models/{name}.pkl"
            self._s3.upload_fileobj(buf, self._bucket, key)
            logger.info("Uploaded model → R2:%s", key)
            return True
        except Exception as exc:
            logger.warning("R2 model upload failed: %s", exc)
            return False

    def download_model(self, name: str) -> Optional[Any]:
        """Download and deserialize a model from R2.

        Args:
            name: Model name (without extension).

        Returns:
            Deserialized model or None.
        """
        if not self._enabled:
            return None
        try:
            buf = io.BytesIO()
            key = f"models/{name}.pkl"
            self._s3.download_fileobj(self._bucket, key, buf)
            buf.seek(0)
            return pickle.load(buf)  # noqa: S301
        except Exception as exc:
            logger.warning("R2 model download failed: %s", exc)
            return None

    def list_files(self, prefix: str = "") -> list[dict]:
        """List objects in R2 with optional prefix filter.

        Args:
            prefix: Key prefix filter (e.g. "models/", "backups/").

        Returns:
            List of dicts with key, size, last_modified.
        """
        if not self._enabled:
            return []
        try:
            response = self._s3.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
            contents = response.get("Contents", [])
            return [
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                }
                for obj in contents
            ]
        except Exception as exc:
            logger.warning("R2 list files failed: %s", exc)
            return []

    def delete(self, remote_key: str) -> bool:
        """Delete an object from R2.

        Args:
            remote_key: Object key to delete.

        Returns:
            True if deleted.
        """
        if not self._enabled:
            return False
        try:
            self._s3.delete_object(Bucket=self._bucket, Key=remote_key)
            return True
        except Exception as exc:
            logger.warning("R2 delete failed: %s", exc)
            return False

    def create_backup(self, data_dir: str = "data/") -> Optional[str]:
        """Upload database files to R2 as a timestamped backup.

        Args:
            data_dir: Local data directory.

        Returns:
            Backup key prefix or None.
        """
        if not self._enabled:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"backups/{timestamp}/"
        data_path = Path(data_dir)
        uploaded = 0
        for f in data_path.rglob("*.db"):
            key = f"{prefix}{f.name}"
            if self.upload_file(str(f), key):
                uploaded += 1
        for f in data_path.rglob("*.duckdb"):
            key = f"{prefix}{f.name}"
            if self.upload_file(str(f), key):
                uploaded += 1
        for f in data_path.rglob("*.json"):
            key = f"{prefix}{f.relative_to(data_path)}"
            if self.upload_file(str(f), key):
                uploaded += 1
        logger.info("Backup created: %s (%d files)", prefix, uploaded)
        return prefix if uploaded > 0 else None

    def list_backups(self) -> list[dict]:
        """List all available backups.

        Returns:
            List of backup dicts with prefix and file count.
        """
        files = self.list_files(prefix="backups/")
        backups: dict[str, int] = {}
        for f in files:
            parts = f["key"].split("/")
            if len(parts) >= 2:
                ts = parts[1]
                backups[ts] = backups.get(ts, 0) + 1
        return [{"timestamp": ts, "file_count": cnt} for ts, cnt in sorted(backups.items(), reverse=True)]

    def restore_backup(self, backup_timestamp: str, dest_dir: str = "data/") -> int:
        """Restore a backup from R2.

        Args:
            backup_timestamp: Timestamp string from list_backups.
            dest_dir: Local destination directory.

        Returns:
            Number of files restored.
        """
        files = self.list_files(prefix=f"backups/{backup_timestamp}/")
        restored = 0
        for f in files:
            key = f["key"]
            rel = key.replace(f"backups/{backup_timestamp}/", "")
            local = os.path.join(dest_dir, rel)
            if self.download_file(key, local):
                restored += 1
        logger.info("Restored %d files from backup %s", restored, backup_timestamp)
        return restored
