"""Create a prioritized 20-item structural cleanup plan from repository evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ITEMS = [
    ("P0", "Unify Phoenix decision entrypoint", "src/structured_product.py, src/full_pipeline.py", "one typed pipeline contract"),
    ("P0", "Remove silent broad exception fallbacks", "src/data_module.py, src/scheduler.py", "typed errors plus visible degraded status"),
    ("P0", "Centralize product constants", "src/structured_product.py, src/phoenix_engine.py", "one ProductConfig for tenor/barrier/rates"),
    ("P0", "Enforce provenance on every learning row", "src/data_quality.py, src/outcome_engine.py", "source/as_of/status/eligibility schema"),
    ("P0", "Make train/OOS splits chronological", "src/replay_calibration.py, src/calibration_agent.py", "walk-forward-only calibration"),
    ("P0", "Audit payoff timing invariants", "src/outcome_engine.py, src/phoenix/pricing.py", "coupon/autocall/barrier contract tests"),
    ("P0", "Replace arbitrary score coefficients", "src/structured_product.py", "research candidates with metric gates"),
    ("P0", "Add market-data freshness gate", "src/data_quality.py, src/data_module.py", "stale or missing data blocks decisions"),
    ("P1", "Add one model-lineage record per candidate", "src/model_lineage.py", "hash code/data/features/parameters"),
    ("P1", "Measure agent marginal contribution", "src/model_lineage.py, src/self_learning_agents.py", "ablation report before retention"),
    ("P1", "Split research and production namespaces", "src/continuous_improvement.py, src/autopilot", "promotion only through PR/evidence"),
    ("P1", "Add correlation-matrix diagnostics", "src/phoenix/pricing.py, src/quant_benchmarks.py", "condition number/shrinkage/reporting"),
    ("P1", "Parameterize rates, dividends and monitoring", "src/phoenix/pricing.py, src/phoenix/barrier_risk.py", "no hidden hard-coded market inputs"),
    ("P1", "Consolidate duplicated risk metrics", "src/risk_metrics.py, src/phoenix/barrier_risk.py", "shared sign/confidence conventions"),
    ("P1", "Add convergence and sensitivity reports", "src/outcome_engine.py, src/phoenix/pricing.py", "seeded n-path stability checks"),
    ("P1", "Make provider failures observable", "src/ai_judge_panel.py, src/gemini_judge.py", "status/reason/latency artifact"),
    ("P2", "Remove unused dependencies and modules", "requirements.txt, src/", "AST/import usage audit before deletion"),
    ("P2", "Replace magic numbers with named settings", "src/agents.py, src/data_module.py", "typed configuration with defaults"),
    ("P2", "Add contract tests for storage fallbacks", "src/storage/", "disabled-by-default behavior isolated from env"),
    ("P2", "Document one canonical runbook", "README.md, .github/workflows/", "setup, benchmark, evidence and rollback steps"),
]


def build_plan() -> dict[str, object]:
    return {
        "status": "research_plan",
        "objective": "Reduce duplication, hidden fallbacks and untestable heuristics.",
        "items": [
            {
                "id": f"cleanup-{index:02d}",
                "priority": priority,
                "proposal": proposal,
                "evidence": evidence,
                "acceptance": acceptance,
                "production_change_allowed": False,
            }
            for index, (priority, proposal, evidence, acceptance) in enumerate(ITEMS, 1)
        ],
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(
        json.dumps(build_plan(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
