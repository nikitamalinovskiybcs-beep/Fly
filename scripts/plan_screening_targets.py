"""Create bounded KPI screening targets from AI judge reviews."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ai_screening import build_screening_target_plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("panel", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_screening_target_plan(json.loads(args.panel.read_text()))
    args.output.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
