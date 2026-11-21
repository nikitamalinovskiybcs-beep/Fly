"""Build a research-only AI review packet for Phoenix formulas and risk code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _snippet(path: str, start: int, end: int) -> dict[str, object]:
    file_path = ROOT / path
    lines = file_path.read_text(encoding="utf-8").splitlines()
    return {
        "file": path,
        "lines": f"{start}-{end}",
        "code": "\n".join(lines[start - 1:end]),
    }


def build_packet() -> dict[str, object]:
    return {
        "review_type": "phoenix_formula_and_risk_code_review",
        "objective": (
            "Independently decide what to KEEP, REMOVE, or REPLACE in the "
            "Phoenix score, payoff, barrier, calibration, and risk metrics."
        ),
        "product_contract": {
            "tenor_months": 24,
            "historical_anchors_months_ago": [6, 12, 18, 24],
            "production_mutation_allowed": False,
            "trades_allowed": False,
        },
        "evidence": {
            "fixed_24m_gate": (
                "Every tested candidate failed the empirical baseline at all "
                "four fixed-24-month anchors."
            ),
            "known_risk": (
                "The earlier horizon-specific 12-month signal did not transfer "
                "to the fixed-24-month product."
            ),
        },
        "review_questions": [
            "Is p_loss a calibrated probability or only a ranking score?",
            "Are barrier and tenor effects derived from evidence or arbitrary proxies?",
            "Does the payoff engine model observation timing and coupon eligibility correctly?",
            "Are correlation, dividends, rates, and path-dependent barriers handled?",
            "Which components should be removed because they are double-counted or unvalidated?",
            "What replacement formula is simplest and testable on chronological OOS data?",
            "What exact Brier, log-loss, ECE, calibration-gap, and monotonicity gates are required?",
        ],
        "formula_components": [
            _snippet("src/structured_product.py", 105, 161),
            _snippet("src/quant_benchmarks.py", 10, 112),
            _snippet("src/quant_benchmarks.py", 115, 172),
            _snippet("src/phoenix/pricing.py", 21, 139),
            _snippet("src/phoenix/barrier_risk.py", 212, 314),
            _snippet("src/risk_metrics.py", 365, 425),
            _snippet("src/real_data.py", 170, 245),
        ],
        "required_output": {
            "verdict": "approve|revise|reject",
            "summary": "short technical conclusion",
            "findings": [
                {
                    "action": "KEEP|REMOVE|REPLACE",
                    "component": "exact component",
                    "reason": "evidence-based reason",
                    "replacement": "specific alternative or empty string",
                    "metric_gate": "objective acceptance rule",
                },
            ],
            "next_experiments": [
                {
                    "hypothesis": "testable hypothesis",
                    "change": "one narrow code/formula change",
                    "metric_gate": "fixed-24m OOS gate",
                },
            ],
            "production_weights_changed": False,
            "verdict_mutated": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.write_text(
        json.dumps(build_packet(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
