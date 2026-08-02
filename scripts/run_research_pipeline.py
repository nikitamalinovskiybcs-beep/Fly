"""Run the unified Phoenix research pipeline from JSON stage artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.research_orchestrator import run_research_pipeline  # noqa: E402


def _load(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(payload)


def _stage(path: Path):
    return lambda _context: _load(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--calculation", type=Path, required=True)
    parser.add_argument("--committee", type=Path, required=True)
    parser.add_argument("--fact-check", type=Path, required=True)
    parser.add_argument("--oos", type=Path, required=True)
    parser.add_argument("--safety", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    records = _load(args.records)
    result = run_research_pipeline(
        records,
        calculation=_stage(args.calculation),
        committee=_stage(args.committee),
        fact_check=_stage(args.fact_check),
        oos=_stage(args.oos),
        safety=_stage(args.safety),
    )
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
