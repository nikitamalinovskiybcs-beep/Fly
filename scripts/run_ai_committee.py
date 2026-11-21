"""Run the research-only AI committee over a multi-model panel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ai_committee import deliberate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("panel", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quorum", type=int, default=2)
    args = parser.parse_args()
    result = deliberate(
        json.loads(args.panel.read_text()),
        quorum=args.quorum,
    )
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
