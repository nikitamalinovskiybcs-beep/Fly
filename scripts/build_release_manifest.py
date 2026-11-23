"""Build an immutable release/rollback manifest from CI artifacts."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def build_release_manifest(
    health: dict,
    safety: dict,
    *,
    version: str,
    rollback_ref: str,
) -> dict:
    """Create a release record without deploying or changing model state."""
    return {
        "schema_version": "release-manifest-v1",
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rollback_ref": rollback_ref,
        "health_status": health.get("status", "unknown"),
        "safety_mode": safety.get("mode", "unknown"),
        "retention_days": 30,
        "promotion": "human_review_required",
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", type=Path, required=True)
    parser.add_argument("--safety", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default=os.getenv("GITHUB_SHA", "local"))
    parser.add_argument("--rollback-ref", default=os.getenv("GITHUB_REF", "local"))
    args = parser.parse_args()
    manifest = build_release_manifest(
        json.loads(args.health.read_text()),
        json.loads(args.safety.read_text()),
        version=args.version,
        rollback_ref=args.rollback_ref,
    )
    args.output.write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
