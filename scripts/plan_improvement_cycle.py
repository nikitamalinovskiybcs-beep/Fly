"""Plan one safe iteration of the continuous improvement loop."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.continuous_improvement import build_cycle_plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--targets",
        type=Path,
        default=Path("data/reports/improvement_targets.json"),
    )
    parser.add_argument("--history", type=Path)
    args = parser.parse_args()
    targets = json.loads(args.targets.read_text())
    history = json.loads(args.history.read_text()) if args.history else []
    plan = build_cycle_plan(targets.get("targets", []), history)
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
