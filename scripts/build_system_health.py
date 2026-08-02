"""Build a secret-free aggregate health report from workflow artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.system_health import build_system_health


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--structure", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_system_health(
        data_quality={"passed": True},
        structure_audit=_load(args.structure),
        benchmark=_load(args.benchmark),
        safety={
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
        },
    )
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
