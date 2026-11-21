"""Create the next evidence-gated quant improvement proposal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.quant_improvement import build_quant_improvement_proposal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    proposal = build_quant_improvement_proposal(report)
    payload = json.dumps(proposal, indent=2)
    if args.output:
        args.output.write_text(payload)
    print(payload)


if __name__ == "__main__":
    main()
