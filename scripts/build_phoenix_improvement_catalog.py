"""Build 100 distinct, evidence-gated Phoenix improvement proposals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CATEGORIES = {
    "formula": [
        "Replace arbitrary objective coefficients with fitted utility units.",
        "Separate expected return from probability-of-loss scoring.",
        "Add monotonic barrier response tests to the score.",
        "Add monotonic tenor response tests to the score.",
        "Use coupon-after-loss expected value instead of additive proxies.",
        "Expose every score component and its unit.",
        "Fit score weights only on chronological OOS data.",
        "Add uncertainty bands around every score component.",
        "Compare raw, calibrated and empirical p_loss side by side.",
        "Block score promotion when inputs are out of contract bounds.",
    ],
    "probability": [
        "Add walk-forward isotonic calibration.",
        "Add walk-forward logistic calibration.",
        "Compare beta calibration against histogram calibration.",
        "Measure calibration drift by issuance month.",
        "Report reliability diagrams with confidence intervals.",
        "Use Brier decomposition into reliability, resolution and uncertainty.",
        "Add log-loss and ECE gates beside Brier.",
        "Calibrate separately by barrier bucket.",
        "Calibrate separately by basket size.",
        "Add probability clipping diagnostics rather than silent clipping.",
    ],
    "payoff_barrier": [
        "Formalize observation-date semantics in one contract.",
        "Test coupon memory after missed observations.",
        "Test coupon eligibility on autocall dates.",
        "Test first-autocall termination and no later coupons.",
        "Test discrete barrier versus contractual barrier monitoring.",
        "Add Brownian-bridge barrier research candidate.",
        "Test barrier crossing between observations.",
        "Test maturity redemption with and without knock-in.",
        "Test worst-of identity at each payoff branch.",
        "Add payoff conservation and bounds checks.",
    ],
    "monte_carlo": [
        "Add convergence curves over path counts.",
        "Add confidence intervals for fair value and p_loss.",
        "Add common random numbers for candidate comparisons.",
        "Add seed-sensitivity reports.",
        "Add antithetic variates as a research candidate.",
        "Add quasi-random Sobol paths as a research candidate.",
        "Parameterize risk-free rate and dividends.",
        "Validate positive-definite correlation inputs.",
        "Report correlation condition numbers.",
        "Add deterministic scenario replay fixtures.",
    ],
    "worst_of_dependence": [
        "Compare Gaussian and Student-t copulas OOS.",
        "Measure tail dependence by regime.",
        "Add shrinkage correlation estimates.",
        "Add correlation uncertainty intervals.",
        "Stress joint downside correlation explicitly.",
        "Compare terminal worst-of with path worst-of.",
        "Add basket-size sensitivity analysis.",
        "Add sector concentration penalty only if OOS-supported.",
        "Detect stale or partial correlation histories.",
        "Report which asset drives worst-of risk.",
    ],
    "risk": [
        "Unify VaR/CVaR sign conventions.",
        "Add sample-size gates for EVT.",
        "Add EVT threshold stability diagnostics.",
        "Add bootstrap confidence intervals for CVaR.",
        "Separate simulated stress from realized evidence.",
        "Add gap-risk sensitivity to overnight volatility.",
        "Add jump-risk scenario analysis.",
        "Add liquidity and quote-width stress.",
        "Add dealer quote-fit as an explicit gate.",
        "Add risk-limit explanations to the verdict.",
    ],
    "data": [
        "Require source and as_of on every market observation.",
        "Reject future-dated observations.",
        "Reject stale prices before scoring.",
        "Compare two independent price sources.",
        "Track corporate-action adjustments.",
        "Track dividends and borrow assumptions.",
        "Add missing-symbol and partial-basket gates.",
        "Persist feature lineage for every prediction.",
        "Separate realized, replay, simulated and stress rows.",
        "Add immutable data-snapshot hashes.",
    ],
    "agents": [
        "Measure marginal contribution of every agent.",
        "Remove agents with non-positive OOS contribution.",
        "Detect correlated agent outputs.",
        "Replace additive adjustments with bounded transforms.",
        "Require agent confidence and evidence references.",
        "Add agent timeout and retry budgets.",
        "Add provider status to every consensus report.",
        "Prevent AI outputs from creating trades.",
        "Prevent AI outputs from changing production weights.",
        "Add a single typed agent interface.",
    ],
    "engineering": [
        "Create one canonical Phoenix pipeline entrypoint.",
        "Centralize product configuration.",
        "Replace broad silent fallbacks with typed statuses.",
        "Add static structure audit to CI.",
        "Add unit checks for magic-number configuration.",
        "Add contract tests for storage-disabled mode.",
        "Add dependency and import hygiene reports.",
        "Add structured error codes and latency fields.",
        "Add model registry records for every candidate.",
        "Add rollback snapshots for promoted configuration.",
    ],
    "operations_ui": [
        "Show one GOOD/CAUTION/BAD verdict with reasons.",
        "Show WHY BLOCKED and WHAT TO CHECK.",
        "Show committee progress from 0 to 100.",
        "Show data freshness on the main screen.",
        "Show quote-fit and dealer evidence separately.",
        "Show realized versus simulated evidence labels.",
        "Show current model version and data snapshot.",
        "Add a slow map of expected return and tail risk.",
        "Add paper-note lifecycle from open to realized.",
        "Add daily drift and calibration monitoring.",
    ],
}


def build_catalog() -> dict[str, object]:
    proposals = []
    index = 1
    for category, items in CATEGORIES.items():
        for proposal in items:
            priority = "P0" if index <= 30 else "P1" if index <= 70 else "P2"
            proposals.append(
                {
                    "id": f"phoenix-{index:03d}",
                    "category": category,
                    "priority": priority,
                    "proposal": proposal,
                    "status": "research_only",
                    "acceptance": (
                        "must pass focused tests and fixed-24m evidence; "
                        "no production mutation"
                    ),
                },
            )
            index += 1
    return {
        "status": "catalog",
        "review_type": "phoenix_improvement_brainstorm",
        "objective": (
            "Generate independent, technically specific proposals to improve "
            "the Phoenix calculator; do not merely approve or reject."
        ),
        "count": len(proposals),
        "categories": {name: len(items) for name, items in CATEGORIES.items()},
        "proposals": proposals,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(build_catalog(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
