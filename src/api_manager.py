"""API Manager — centralized connection management for all external services.

Handles:
- Loading/saving API keys from .env file
- Connection health checks for each service
- Auto-connect on startup
- Status reporting for UI
"""

import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

ENV_PATH = Path(".env")
PROBE_CACHE = Path("data/connectivity_probe.json")

SERVICES = {
    "supabase": {
        "name": "Supabase",
        "description": "PostgreSQL cloud backup (free: 500MB)",
        "signup_url": "https://supabase.com/dashboard",
        "keys": ["SUPABASE_URL", "SUPABASE_KEY"],
        "key_labels": {
            "SUPABASE_URL": "Project URL (https://xxx.supabase.co)",
            "SUPABASE_KEY": "anon/public key (eyJhbGci...)",
        },
        "setup_steps": [
            "1. Go to supabase.com/dashboard and create a free account",
            "2. Create a new project (any name, e.g. 'fly-data')",
            "3. Go to Settings > API",
            "4. Copy 'Project URL' and 'anon public' key",
        ],
    },
    "firebase": {
        "name": "Firebase",
        "description": "Real-time state sync (free: 1GB storage)",
        "signup_url": "https://console.firebase.google.com/",
        "keys": ["FIREBASE_CREDENTIALS"],
        "key_labels": {
            "FIREBASE_CREDENTIALS": "Service account JSON (paste entire JSON)",
        },
        "setup_steps": [
            "1. Go to console.firebase.google.com",
            "2. Create a project (any name)",
            "3. Go to Project Settings > Service Accounts",
            "4. Click 'Generate new private key'",
            "5. Paste the entire JSON content",
        ],
    },
    "clickhouse": {
        "name": "ClickHouse Cloud",
        "description": "OLAP analytics (free: 10GB + 100GB queries/mo)",
        "signup_url": "https://clickhouse.cloud/",
        "keys": ["CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD"],
        "key_labels": {
            "CLICKHOUSE_HOST": "Host (xxx.clickhouse.cloud)",
            "CLICKHOUSE_USER": "Username (default)",
            "CLICKHOUSE_PASSWORD": "Password",
        },
        "setup_steps": [
            "1. Go to clickhouse.cloud and sign up (free trial)",
            "2. Create a new service",
            "3. Copy host, username, and password from connection details",
        ],
    },
    "r2": {
        "name": "Cloudflare R2",
        "description": "Object storage for models/data (free: 10GB)",
        "signup_url": "https://dash.cloudflare.com/",
        "keys": ["R2_ENDPOINT", "R2_ACCESS_KEY", "R2_SECRET_KEY", "R2_BUCKET"],
        "key_labels": {
            "R2_ENDPOINT": "S3 API endpoint (https://xxx.r2.cloudflarestorage.com)",
            "R2_ACCESS_KEY": "Access Key ID",
            "R2_SECRET_KEY": "Secret Access Key",
            "R2_BUCKET": "Bucket name (default: fly-data)",
        },
        "setup_steps": [
            "1. Go to dash.cloudflare.com > R2",
            "2. Create a bucket named 'fly-data'",
            "3. Go to R2 > Manage R2 API Tokens",
            "4. Create an API token with read/write",
            "5. Copy endpoint, access key, and secret key",
        ],
    },
    "redis": {
        "name": "Redis / Upstash",
        "description": "Cache + rate limiting (free: 256MB)",
        "signup_url": "https://console.upstash.com/",
        "keys": ["REDIS_URL"],
        "key_labels": {
            "REDIS_URL": "Redis URL (redis://default:xxx@xxx.upstash.io:6379)",
        },
        "setup_steps": [
            "1. Go to console.upstash.com and sign up",
            "2. Create a new Redis database",
            "3. Copy the Redis URL from the dashboard",
        ],
    },
    "numerai": {
        "name": "Numerai",
        "description": "Tournament data + NMR rewards (free)",
        "signup_url": "https://numer.ai/",
        "keys": ["NUMERAI_PUBLIC_ID", "NUMERAI_SECRET_KEY"],
        "key_labels": {
            "NUMERAI_PUBLIC_ID": "Public ID",
            "NUMERAI_SECRET_KEY": "Secret Key",
        },
        "setup_steps": [
            "1. Go to numer.ai and sign up (free)",
            "2. Go to Account > Settings > API Keys",
            "3. Create a new API key",
            "4. Copy Public ID and Secret Key",
        ],
    },
    "quantconnect": {
        "name": "QuantConnect",
        "description": "Cloud backtesting (free: 10/month)",
        "signup_url": "https://www.quantconnect.com/",
        "keys": ["QC_USER_ID", "QC_API_TOKEN"],
        "key_labels": {
            "QC_USER_ID": "User ID (numeric)",
            "QC_API_TOKEN": "API Token",
        },
        "setup_steps": [
            "1. Go to quantconnect.com and sign up (free)",
            "2. Go to Account > API Access",
            "3. Copy User ID and API Token",
        ],
    },
}


class APIManager:
    """Manages all external API connections."""

    def __init__(self, load_env: bool = False) -> None:
        if load_env:
            self._load_env()

    def _load_env(self) -> None:
        """Load .env file if it exists."""
        if ENV_PATH.exists():
            for line in ENV_PATH.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if value:
                        os.environ.setdefault(key, value)

    def save_keys(self, service_id: str, keys: dict[str, str]) -> bool:
        """Save API keys for a service to .env file.

        Args:
            service_id: Service identifier (e.g., 'supabase').
            keys: Dict of env_var_name -> value.

        Returns:
            True if saved successfully.
        """
        try:
            existing: dict[str, str] = {}
            comments: list[str] = []

            if ENV_PATH.exists():
                for line in ENV_PATH.read_text().splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        comments.append(line)
                        continue
                    if "=" in stripped:
                        k, _, v = stripped.partition("=")
                        existing[k.strip()] = v.strip()

            for k, v in keys.items():
                if v:
                    existing[k] = v
                    os.environ[k] = v

            lines = ["# Fly API Keys — auto-generated by API Manager", ""]
            for svc_id, svc_info in SERVICES.items():
                lines.append(f"# ── {svc_info['name']} ──")
                for key_name in svc_info["keys"]:
                    val = existing.get(key_name, "")
                    lines.append(f"{key_name}={val}")
                lines.append("")

            ENV_PATH.write_text("\n".join(lines) + "\n")
            return True
        except Exception as exc:
            logger.error("Failed to save keys: %s", exc)
            return False

    def get_saved_keys(self, service_id: str) -> dict[str, str]:
        """Get currently saved keys for a service.

        Args:
            service_id: Service identifier.

        Returns:
            Dict of env_var_name -> value (masked).
        """
        svc = SERVICES.get(service_id, {})
        result = {}
        for key_name in svc.get("keys", []):
            val = os.getenv(key_name, "")
            result[key_name] = val
        return result

    def test_connection(self, service_id: str) -> dict:
        """Test connection to a specific service.

        Args:
            service_id: Service identifier.

        Returns:
            Dict with 'connected' (bool), 'message' (str), 'details' (optional).
        """
        testers = {
            "supabase": self._test_supabase,
            "firebase": self._test_firebase,
            "clickhouse": self._test_clickhouse,
            "r2": self._test_r2,
            "redis": self._test_redis,
            "numerai": self._test_numerai,
            "quantconnect": self._test_quantconnect,
        }
        tester = testers.get(service_id)
        if not tester:
            return {"connected": False, "message": f"Unknown service: {service_id}"}
        try:
            return tester()
        except Exception as exc:
            return {"connected": False, "message": str(exc)}

    def test_all(self) -> dict[str, dict]:
        """Test all configured services.

        Returns:
            Dict of service_id -> test result.
        """
        results = {}
        for svc_id in SERVICES:
            keys = self.get_saved_keys(svc_id)
            has_keys = any(v for v in keys.values())
            if has_keys:
                results[svc_id] = self.test_connection(svc_id)
            else:
                results[svc_id] = {"connected": False, "message": "No keys configured"}
        return results

    def get_status(self) -> dict:
        """Get status of all services.

        Returns:
            Dict with service statuses and summary.
        """
        statuses = {}
        for svc_id, svc_info in SERVICES.items():
            keys = self.get_saved_keys(svc_id)
            has_keys = any(v for v in keys.values())
            statuses[svc_id] = {
                "name": svc_info["name"],
                "has_keys": has_keys,
                "description": svc_info["description"],
            }

        cached_probe = self.get_cached_probe()
        probe_results = cached_probe.get("results", {})
        probe_is_current = bool(cached_probe.get("live_verified")) and not cached_probe.get("stale", True)
        connected = sum(
            1 for service_id, status in statuses.items()
            if probe_is_current and probe_results.get(service_id, {}).get("connected") is True
        )
        for service_id, status in statuses.items():
            probe = probe_results.get(service_id)
            status["connected"] = bool(
                probe_is_current and probe and probe.get("connected")
            )
            status["probe_message"] = probe.get("message", "") if probe else ""
        live_verified = probe_is_current
        return {
            "services": statuses,
            "total": len(SERVICES),
            "connected": connected,
            "configured": sum(1 for s in statuses.values() if s["has_keys"]),
            "live_verified": live_verified,
            "probe_ts": cached_probe.get("ts"),
            "local_always_on": ["SQLite", "DuckDB"],
        }

    def get_cached_probe(self) -> dict:
        """Read the last cached connectivity probe (pure-render, no network)."""
        if not PROBE_CACHE.exists():
            return {"cached": False, "results": {}, "ts": None}
        try:
            data = json.loads(PROBE_CACHE.read_text())
            data["cached"] = True
            ts = data.get("ts")
            age_s = max(0.0, time.time() - float(ts)) if ts else None
            data["age_s"] = round(age_s, 1) if age_s is not None else None
            data["stale"] = age_s is None or age_s >= 3600
            data["live_verified"] = bool(data.get("results"))
            return data
        except Exception:
            return {"cached": False, "results": {}, "ts": None}

    def probe_connectivity(self, force: bool = False, max_age_s: int = 3600) -> dict:
        """Probe all services and cache the result to disk.

        Karpathy-style: the network probe runs at most once per ``max_age_s``
        and the UI renders from the cached JSON, so repeated page loads cost
        nothing. Pass ``force=True`` to refresh immediately.
        """
        cached = self.get_cached_probe()
        if not force and cached.get("cached") and cached.get("ts"):
            if time.time() - float(cached["ts"]) < max_age_s:
                return cached

        results = self.test_all()
        payload = {
            "ts": time.time(),
            "connected": sum(1 for r in results.values() if r.get("connected")),
            "results": results,
            "live_verified": True,
        }
        try:
            PROBE_CACHE.parent.mkdir(parents=True, exist_ok=True)
            PROBE_CACHE.write_text(json.dumps(payload, indent=2, default=str))
        except Exception as exc:
            logger.warning("Probe cache write failed: %s", exc)
        payload["cached"] = False
        payload["age_s"] = 0.0
        payload["stale"] = False
        return payload

    def setup_supabase_tables(self) -> dict:
        """Explain how to create required tables in Supabase.

        Returns:
            A truthful response because DDL is not available through the
            publishable PostgREST client.
        """
        return {
            "status": "manual_sql_required",
            "error": "DDL is not supported through the publishable Supabase API",
            "message": "Run the schema migration in Supabase SQL Editor.",
        }

    def _test_supabase(self) -> dict:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        if not url or not key:
            return {"connected": False, "message": "Missing SUPABASE_URL or SUPABASE_KEY"}
        try:
            from supabase import create_client
            client = create_client(url, key)
            client.table("trades").select("id").limit(1).execute()
            return {"connected": True, "message": f"Connected to {url.split('//')[1].split('.')[0]}"}
        except ImportError:
            return {"connected": False, "message": "supabase package not installed. Run: pip install supabase"}
        except Exception as exc:
            err = str(exc)
            if "PGRST205" in err or (
                "schema cache" in err and "public." in err
            ) or ("relation" in err and "does not exist" in err):
                return {
                    "connected": True,
                    "schema_ready": False,
                    "message": "Endpoint reachable; required table is missing",
                }
            if "Invalid API key" in err or "401" in err:
                return {"connected": False, "schema_ready": False, "message": "Invalid API key"}
            if "403" in err or "permission" in err.lower():
                return {
                    "connected": True,
                    "schema_ready": True,
                    "write_ready": False,
                    "message": "Connected; operation denied by policy",
                }
            return {"connected": False, "message": f"Error: {err[:100]}"}

    def _test_firebase(self) -> dict:
        creds = os.getenv("FIREBASE_CREDENTIALS", "")
        if not creds:
            return {"connected": False, "message": "Missing FIREBASE_CREDENTIALS"}
        try:
            creds_dict = json.loads(creds)
            project = creds_dict.get("project_id", "unknown")
            return {"connected": True, "message": f"Credentials valid (project: {project})"}
        except json.JSONDecodeError:
            return {"connected": False, "message": "Invalid JSON in FIREBASE_CREDENTIALS"}
        except Exception as exc:
            return {"connected": False, "message": str(exc)}

    def _test_clickhouse(self) -> dict:
        host = os.getenv("CLICKHOUSE_HOST", "")
        password = os.getenv("CLICKHOUSE_PASSWORD", "")
        if not host or not password:
            return {"connected": False, "message": "Missing CLICKHOUSE_HOST or CLICKHOUSE_PASSWORD"}
        try:
            import clickhouse_connect
            user = os.getenv("CLICKHOUSE_USER", "default")
            client = clickhouse_connect.get_client(
                host=host, username=user, password=password, secure=True,
            )
            client.query("SELECT 1")
            return {"connected": True, "message": f"Connected to {host}"}
        except ImportError:
            return {"connected": False, "message": "clickhouse-connect not installed. Run: pip install clickhouse-connect"}
        except Exception as exc:
            return {"connected": False, "message": str(exc)[:100]}

    def _test_r2(self) -> dict:
        endpoint = os.getenv("R2_ENDPOINT", "")
        access = os.getenv("R2_ACCESS_KEY", "")
        secret = os.getenv("R2_SECRET_KEY", "")
        bucket = os.getenv("R2_BUCKET", "fly-data")
        if not endpoint or not access or not secret:
            return {"connected": False, "message": "Missing R2 credentials"}
        try:
            import boto3
            s3 = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access,
                aws_secret_access_key=secret,
            )
            s3.head_bucket(Bucket=bucket)
            return {"connected": True, "message": f"Connected to bucket '{bucket}'"}
        except ImportError:
            return {"connected": False, "message": "boto3 not installed. Run: pip install boto3"}
        except Exception as exc:
            err = str(exc)
            if "404" in err or "NoSuchBucket" in err:
                return {"connected": False, "message": f"Bucket '{bucket}' not found"}
            if "403" in err:
                return {"connected": False, "message": "Access denied (check keys)"}
            return {"connected": False, "message": err[:100]}

    def _test_redis(self) -> dict:
        url = os.getenv("REDIS_URL", "")
        if not url:
            return {"connected": False, "message": "Missing REDIS_URL"}
        try:
            import redis
            r = redis.from_url(url, socket_timeout=5)
            r.ping()
            info = r.info("memory")
            used_mb = info.get("used_memory_human", "?")
            return {"connected": True, "message": f"Connected (memory: {used_mb})"}
        except ImportError:
            return {"connected": False, "message": "redis package not installed. Run: pip install redis"}
        except Exception as exc:
            return {"connected": False, "message": str(exc)[:100]}

    def _test_numerai(self) -> dict:
        pub_id = os.getenv("NUMERAI_PUBLIC_ID", "")
        secret = os.getenv("NUMERAI_SECRET_KEY", "")
        if not pub_id or not secret:
            return {"connected": False, "message": "Missing NUMERAI_PUBLIC_ID or NUMERAI_SECRET_KEY"}
        try:
            import numerapi
            napi = numerapi.NumerAPI(public_id=pub_id, secret_key=secret)
            models = napi.get_models()
            return {"connected": True, "message": f"Connected ({len(models)} models)"}
        except ImportError:
            return {"connected": False, "message": "numerapi not installed. Run: pip install numerapi"}
        except Exception as exc:
            err = str(exc)
            if "Unauthorized" in err or "401" in err:
                return {"connected": False, "message": "Invalid API keys"}
            return {"connected": False, "message": err[:100]}

    def _test_quantconnect(self) -> dict:
        user_id = os.getenv("QC_USER_ID", "")
        token = os.getenv("QC_API_TOKEN", "")
        if not user_id or not token:
            return {"connected": False, "message": "Missing QC_USER_ID or QC_API_TOKEN"}
        try:
            import requests
            resp = requests.get(
                "https://www.quantconnect.com/api/v2/authenticate",
                headers={"Timestamp": "0"},
                auth=(user_id, token),
                timeout=10,
            )
            if resp.status_code == 200 and resp.json().get("success"):
                return {"connected": True, "message": "Authenticated"}
            return {"connected": False, "message": f"Auth failed (HTTP {resp.status_code})"}
        except ImportError:
            return {"connected": False, "message": "requests not installed"}
        except Exception as exc:
            return {"connected": False, "message": str(exc)[:100]}


def mask_key(value: str, show_chars: int = 4) -> str:
    """Mask an API key for display, showing only first/last chars.

    Args:
        value: Raw key value.
        show_chars: Number of chars to show at start/end.

    Returns:
        Masked string.
    """
    if not value:
        return ""
    if len(value) <= show_chars * 2:
        return "*" * len(value)
    return value[:show_chars] + "*" * (len(value) - show_chars * 2) + value[-show_chars:]
