"""Build the AI committee's measurable implementation progress report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.committee_progress import build_progress_score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--health", type=Path, required=True)
    parser.add_argument("--structure", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_progress_score(
        benchmark=json.loads(args.benchmark.read_text()),
        health=json.loads(args.health.read_text()),
        structure=json.loads(args.structure.read_text()),
        evidence={
            "provenance_gate": True,
            "payoff_tests": True,
            "observation_validation": True,
            "agent_ablation": True,
            "focused_tests": True,
            "ci_passed": False,
        },
    )
    args.output.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
