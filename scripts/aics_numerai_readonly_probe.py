#!/usr/bin/env python3
"""Secret-safe, READ-ONLY Numerai authentication probe for AICS research.

Numerai's account ID query checks only credential acceptance. No account ID,
key, error response body, model name, prediction, market observation, or
proprietary data is persisted. This is NOT a point-in-time data attestation.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Mapping

API_URL = "https://api-tournament.numer.ai/"
QUERY = "query AICSReadOnlyHealth { account { id } }"
REPORT_PATH = Path("aics_data/progress/numerai_readonly_connection_check.json")
SCHEMA = "aics-numerai-readonly-connectivity-v1"


def check_credentials(
    environ: Mapping[str, str],
    transport: Callable = urllib.request.urlopen,
) -> str:
    """Return one non-sensitive status string; never return an API response."""
    public_id = environ.get("NUMERAI_PUBLIC_ID", "").strip()
    secret_key = environ.get("NUMERAI_SECRET_KEY", "").strip()
    if not public_id or not secret_key:
        return "MISSING_CREDENTIALS"
    # Never log a urllib Request: its headers contain confidential credentials.
    request = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": QUERY}, separators=(",", ":")).encode("utf-8"),
        headers={
            "Authorization": f"Token {public_id}${secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AICS-Research-Numerai-ReadOnly/1.0",
        },
        method="POST",
    )
    try:
        with transport(request, timeout=20) as response:
            if getattr(response, "status", 200) != 200:
                return "UPSTREAM_HTTP_ERROR"
            payload = json.loads(response.read(131072).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            return "AUTHENTICATION_REJECTED"
        if exc.code == 429:
            return "RATE_LIMITED"
        return "UPSTREAM_HTTP_ERROR"
    except (urllib.error.URLError, TimeoutError, OSError):
        return "NETWORK_ERROR"
    except (ValueError, UnicodeError, json.JSONDecodeError):
        return "BAD_RESPONSE"
    except Exception:
        # Some library exceptions embed the Authorization header. Never log it.
        return "CLIENT_ERROR"

    if not isinstance(payload, dict) or payload.get("errors"):
        return "API_GRAPHQL_ERROR"
    data = payload.get("data")
    account = data.get("account") if isinstance(data, dict) else None
    if not isinstance(account, dict) or not isinstance(account.get("id"), str):
        return "BAD_RESPONSE"
    if not account["id"]:
        return "BAD_RESPONSE"
    return "CONNECTED_READ_ONLY"


def make_report(status: str, checked_at: dt.datetime | None = None) -> dict:
    now = checked_at or dt.datetime.now(dt.timezone.utc)
    if now.utcoffset() != dt.timedelta(0):
        now = now.astimezone(dt.timezone.utc)
    return {
        "schema_version": SCHEMA,
        "checked_at_utc": now.isoformat().replace("+00:00", "Z"),
        "provider": "numerai",
        "method": "graphql_readonly_account_id_presence_check",
        "status": status,
        "account_id_stored": False,
        "credentials_stored": False,
        "permission_required": "view_user_info",
        "market_observations_archived": 0,
        "historical_pit_vintage_attested": False,
        "aics_node_score": None,
        "certified_aics": None,
        "aics_promotion": "BLOCKED",
        "limitations": "Connectivity is not economic time-series data or independent AICS certification.",
    }


def main() -> int:
    result = check_credentials(os.environ)
    path = REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(make_report(result), indent=2) + "\n", encoding="utf-8")
    # Print only static enumerated status. No request/response/account data.
    print(f"Numerai AICS connection: {result}")
    return 0 if result == "CONNECTED_READ_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
