"""Build 100 additional, research-only Phoenix improvement proposals."""

from __future__ import annotations

import json
from pathlib import Path


CATEGORIES = {
    "data_contracts": [
        "Add source reliability scores per field",
        "Validate timezone normalization at ingestion",
        "Detect duplicate observations across providers",
        "Store corporate-action adjustment provenance",
        "Add stale-field quarantine instead of row-level masking",
        "Version ticker aliases and corporate identifiers",
        "Track market-close calendar mismatches",
        "Add missingness pattern diagnostics by provider",
        "Require immutable raw payload hashes",
        "Add human review queue for disputed facts",
    ],
    "payoff_autocall": [
        "Model observation-date timezone and holiday conventions",
        "Separate autocall trigger from coupon trigger semantics",
        "Add coupon memory state transition tests",
        "Test partial-period accrual at early redemption",
        "Support issuer-specific call schedules",
        "Add payoff monotonicity tests for every term",
        "Report first-call hazard by observation date",
        "Decompose expected return by coupon and redemption state",
        "Add barrier touch versus barrier close distinction",
        "Validate participation cap and floor semantics",
    ],
    "risk": [
        "Add jump-to-default stress for single names",
        "Model overnight gap risk separately from diffusion",
        "Add liquidity liquidation haircut scenarios",
        "Stress correlation to crisis-floor and crisis-spike states",
        "Add dividend-cut and special-dividend scenarios",
        "Estimate wrong-way risk between volatility and correlation",
        "Add issuer credit spread sensitivity",
        "Report risk contribution by payoff state",
        "Add scenario ranking by expected loss contribution",
        "Track model-risk reserve for unsupported assumptions",
    ],
    "calibration_oos": [
        "Add nested walk-forward calibration",
        "Use blocked bootstrap confidence intervals",
        "Add calibration transfer test across basket sizes",
        "Track calibration sample effective size",
        "Add probability clipping audit",
        "Compare isotonic and Platt calibration out of sample",
        "Add anchor-specific calibration stability bands",
        "Require calibration degradation alerts",
        "Separate label delay from model error",
        "Add reproducible benchmark manifest per run",
    ],
    "basket_selection": [
        "Penalize common earnings-week concentration",
        "Add event-calendar overlap score",
        "Limit single-factor exposure in candidate baskets",
        "Add pairwise crash co-occurrence score",
        "Prefer basket substitutions with matched volatility",
        "Add liquidity-weighted basket feasibility",
        "Score index constituents separately from single names",
        "Add country and revenue exposure caps",
        "Rank baskets by autocall hazard per unit coupon",
        "Add dealer inventory concentration as a research feature",
    ],
    "agents_learning": [
        "Add per-agent ablation registry",
        "Measure agent correlation and signal overlap",
        "Require agent output lineage and timestamp",
        "Add stale-agent output rejection",
        "Add champion-challenger agent reports",
        "Cap online-learning update magnitude",
        "Add rollback snapshots for learned parameters",
        "Separate research agent votes from scoring features",
        "Detect agent disagreement clusters",
        "Require human approval for agent promotion",
    ],
    "committee_governance": [
        "Add proposal schema validation before panel calls",
        "Require independent provider diversity for quorum",
        "Record provider timeout and rate-limit causes",
        "Add explicit abstain and conflict outcomes",
        "Require dissent text for every approval",
        "Add evidence citation validation",
        "Score proposals by falsifiability",
        "Detect copied or correlated provider reasoning",
        "Add second-pass adversarial review",
        "Add committee decision expiration dates",
    ],
    "storage_production": [
        "Add Supabase schema migration checksum",
        "Add cloud/local write reconciliation report",
        "Add idempotency keys for cloud writes",
        "Add dead-letter queue for failed syncs",
        "Add storage latency and error budgets",
        "Add startup readiness endpoint",
        "Add secrets-source precedence diagnostics",
        "Add deployment configuration drift checks",
        "Add release rollback verification",
        "Add production-readiness evidence bundle export",
    ],
    "ui_decision_support": [
        "Show evidence versus assumption badges per input",
        "Show worst-of driver history",
        "Show autocall probability by observation date",
        "Show coupon fair-value interval beside quote",
        "Show confidence and sample-size warnings",
        "Add side-by-side payoff state comparison",
        "Add stale-data banner with exact timestamps",
        "Show why a candidate is blocked",
        "Add downloadable audit summary",
        "Separate research score from investment verdict",
    ],
    "validation_research": [
        "Add negative-control baskets to every replay",
        "Run synthetic-data calibration sanity checks",
        "Add leakage sentinel features",
        "Track selection bias from survivor universes",
        "Add repeated-seed Monte Carlo stability reports",
        "Compare model against naive autocall hazard",
        "Add stress-period holdout evaluation",
        "Add reproducible environment fingerprint",
        "Add test-data contamination scan",
        "Require human sign-off artifact before promotion",
    ],
}


def build_catalog() -> dict[str, object]:
    proposals: list[dict[str, object]] = []
    index = 201
    for category, titles in CATEGORIES.items():
        for title in titles:
            proposals.append(
                {
                    "id": f"phoenix-{index}",
                    "category": category,
                    "title": title,
                    "change": title,
                    "value": 8 if category in {"data_contracts", "calibration_oos", "validation_research"} else 7,
                    "risk": 2 if category in {"committee_governance", "ui_decision_support"} else 3,
                    "cost": 2 if category in {"committee_governance", "ui_decision_support"} else 4,
                    "status": "research_only",
                    "metric_gate": (
                        "No production promotion unless fixed-24m OOS Brier and "
                        "log-loss beat the empirical baseline at 6/12/18/24 anchors."
                    ),
                    "safety": {
                        "production_weights_changed": False,
                        "verdict_mutated": False,
                        "trades_created": False,
                    },
                },
            )
            index += 1
    return {
        "review_type": "phoenix_improvement_brainstorm",
        "catalog_version": "v3",
        "objective": "Generate 100 additional improvements beyond prior catalogs, then shortlist ten.",
        "count": len(proposals),
        "categories": {category: len(items) for category, items in CATEGORIES.items()},
        "constraints": [
            "AI recommendations are research input, not market evidence",
            "do not fabricate notes, quotes, outcomes, votes or consensus",
            "do not change production weights, live verdicts or trades",
            "fixed-24m OOS remains the promotion safety gate",
        ],
        "proposals": proposals,
    }


def main() -> None:
    output = Path("data/reports/phoenix-improvement-catalog-v3.json")
    output.write_text(json.dumps(build_catalog(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output} with {len(build_catalog()['proposals'])} proposals")


if __name__ == "__main__":
    main()
