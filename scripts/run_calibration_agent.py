"""Run the evidence-gated calibration agent on persisted realized notes."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.calibration_agent import run_calibration_cycle
from src.outcome_engine import PaperOutcomeTracker


def main() -> None:
    result = run_calibration_cycle(PaperOutcomeTracker().notes)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
