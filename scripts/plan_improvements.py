"""Print ranked Phoenix improvement targets from local evidence reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.improvement_targets import build_improvement_targets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--replay",
        type=Path,
        default=Path("data/reports/replay_80_baskets.json"),
    )
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--ece", type=float, default=0.126122)
    args = parser.parse_args()
    replay = json.loads(args.replay.read_text())
    benchmark = (
        json.loads(args.benchmark.read_text())
        if args.benchmark
        else {"ece": args.ece}
    )
    print(json.dumps(build_improvement_targets(replay, benchmark), indent=2))


if __name__ == "__main__":
    main()
