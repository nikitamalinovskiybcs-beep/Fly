"""Run an independent Gemini model-risk review for a benchmark report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import os
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gemini_judge import judge_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("proposal", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gemini-2.0-flash")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        payload = {
            "status": "skipped",
            "reason": "GEMINI_API_KEY is not configured",
            "production_weights_changed": False,
            "verdict_mutated": False,
        }
    else:
        report = json.loads(args.report.read_text())
        proposal = json.loads(args.proposal.read_text())
        try:
            payload = {
                "status": "completed",
                "review": judge_report(
                    report,
                    proposal,
                    api_key,
                    model=args.model,
                ),
            }
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else 0
            if status not in {429, 500, 502, 503, 504}:
                raise
            payload = {
                "status": "deferred",
                "reason": f"Gemini API returned HTTP {status}",
                "production_weights_changed": False,
                "verdict_mutated": False,
            }

    args.output.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
