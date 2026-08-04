"""Validate immutable safety and health artifacts before deployment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_release_gate(health: dict, safety: dict) -> dict:
    """Return a deployment decision without changing model or trading state."""
    safety_checks = {
        "research_only": safety.get("mode") == "research_only",
        "weights_unchanged": safety.get("production_weights_changed") is False,
        "verdict_unchanged": safety.get("verdict_mutated") is False,
        "trades_not_created": safety.get("trades_created") is False,
        "human_review": safety.get("requires_human_review_for_merge") is True,
    }
    health_checks = {
        "health_passed": health.get("status") == "healthy",
        "production_safety": health.get("checks", {}).get("production_safety") is True,
    }
    checks = {**safety_checks, **health_checks}
    return {
        "passed": all(checks.values()),
        "status": "approved" if all(checks.values()) else "blocked",
        "checks": checks,
        "reason": (
            "release_artifacts_passed"
            if all(checks.values())
            else "release_artifacts_failed"
        ),
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", type=Path, required=True)
    parser.add_argument("--safety", type=Path, required=True)
    args = parser.parse_args()
    result = validate_release_gate(
        json.loads(args.health.read_text()),
        json.loads(args.safety.read_text()),
    )
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
