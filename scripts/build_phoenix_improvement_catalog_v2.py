"""Build the second 100-item AI committee improvement catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CATEGORIES = {
    "debate": [
        "Require every model to identify the strongest opposing argument.",
        "Run a second-pass rebuttal after proposals are anonymized.",
        "Ask each model to rank rival proposals by falsifiability.",
        "Separate factual disagreement from preference disagreement.",
        "Record unsupported assumptions in a shared objection ledger.",
        "Require citations to supplied files for implementation claims.",
        "Add a devil's-advocate seat to every committee round.",
        "Limit repeated arguments from the same provider.",
        "Ask models to state what evidence would change their vote.",
        "Preserve minority opinions in the final committee artifact.",
    ],
    "moderation": [
        "Add a typed moderator decision schema.",
        "Detect contradictions between a model's verdict and proposals.",
        "Reject malformed proposal fields before voting.",
        "Normalize synonymous component names before deduplication.",
        "Cluster proposals by semantic component and test target.",
        "Require the moderator to explain every tie.",
        "Add a confidence interval to vote share.",
        "Distinguish consensus from correlated provider outputs.",
        "Cap the influence of any single provider.",
        "Require a minimum independent-provider count for promotion.",
    ],
    "evidence": [
        "Attach one measurable acceptance test to every proposal.",
        "Attach a baseline metric to every proposed model change.",
        "Require a data snapshot hash in every experiment.",
        "Require a code version in every experiment.",
        "Store train and OOS row counts with each result.",
        "Reject proposals that only cite simulated evidence.",
        "Track evidence age for every recommendation.",
        "Add confidence intervals to committee KPI claims.",
        "Record failed experiments, not only winners.",
        "Add an evidence completeness score per proposal.",
    ],
    "experiments": [
        "Generate an isolated branch for each approved research target.",
        "Run candidate tests in a reproducible container.",
        "Compare candidates with common random numbers.",
        "Run multi-seed validation before committee re-vote.",
        "Run basket-universe perturbation tests.",
        "Run time-window perturbation tests.",
        "Run barrier perturbation tests.",
        "Run coupon perturbation tests.",
        "Run correlation perturbation tests.",
        "Run missing-data sensitivity tests.",
    ],
    "oos_paper": [
        "Create a paper-note record for every promoted candidate.",
        "Require paper maturity before realized-evidence claims.",
        "Track daily MTM and model prediction together.",
        "Separate model selection from paper outcome evaluation.",
        "Add a paper-note stop rule for stale market data.",
        "Measure realized calibration by issuance cohort.",
        "Measure realized drawdown by candidate lineage.",
        "Compare paper outcomes with the empirical baseline.",
        "Add an explicit paper-to-realized transition audit.",
        "Block learning from notes without complete lifecycle data.",
    ],
    "drift": [
        "Monitor feature distribution drift weekly.",
        "Monitor p_loss distribution drift weekly.",
        "Monitor barrier-breach rate drift.",
        "Monitor dealer coupon drift.",
        "Monitor quote-width drift.",
        "Monitor basket-sector mix drift.",
        "Monitor model residual drift.",
        "Trigger re-calibration on measured drift.",
        "Trigger committee review on repeated drift.",
        "Show drift status in the main verdict UI.",
    ],
    "data_contracts": [
        "Version the market-data schema.",
        "Version the dealer-quote schema.",
        "Validate timezone consistency at ingestion.",
        "Validate trading-calendar alignment.",
        "Validate adjusted-close policy.",
        "Validate duplicate observation handling.",
        "Validate out-of-order observations.",
        "Validate source failover provenance.",
        "Validate snapshot completeness before replay.",
        "Publish machine-readable data-quality reasons.",
    ],
    "risk_extensions": [
        "Add wrong-way risk between coupon and barrier events.",
        "Add liquidity haircut scenarios.",
        "Add funding-spread scenarios.",
        "Add dividend-miss scenarios.",
        "Add early-close scenarios.",
        "Add market-halt scenarios.",
        "Add corporate-action scenarios.",
        "Add discontinuous jump scenarios.",
        "Add correlation-break scenarios.",
        "Add model-risk capital buffer scenarios.",
    ],
    "automation": [
        "Create a scheduled proposal-generation artifact.",
        "Create a scheduled committee-vote artifact.",
        "Create a scheduled evidence-gap artifact.",
        "Create a scheduled progress-score history.",
        "Open a draft PR only after tests pass.",
        "Attach benchmark reports to research PRs.",
        "Attach committee dissent to research PRs.",
        "Require CI before any research PR update.",
        "Add automatic rollback of failed research branches.",
        "Add a manual approval gate before merge.",
    ],
    "observability_security": [
        "Add provider latency to every panel result.",
        "Add provider cost/quota status without exposing keys.",
        "Redact secrets from AI prompts and artifacts.",
        "Hash prompts for reproducibility without storing secrets.",
        "Log committee version and prompt version.",
        "Log model version and provider endpoint.",
        "Alert on unexpected provider response schema.",
        "Alert on safety-flag changes.",
        "Add immutable artifact retention policy.",
        "Run a periodic access review for automation tokens.",
    ],
}


def build_catalog() -> dict[str, object]:
    proposals = []
    index = 101
    for category, items in CATEGORIES.items():
        for proposal in items:
            priority = "P0" if index <= 130 else "P1" if index <= 170 else "P2"
            proposals.append(
                {
                    "id": f"phoenix-{index:03d}",
                    "category": category,
                    "priority": priority,
                    "proposal": proposal,
                    "status": "research_only",
                    "acceptance": (
                        "requires independent AI review, tests and evidence; "
                        "no production mutation"
                    ),
                },
            )
            index += 1
    return {
        "status": "catalog",
        "catalog_version": "v2",
        "review_type": "phoenix_improvement_brainstorm",
        "objective": (
            "Generate independent debate, evidence and automation improvements "
            "without duplicating catalog v1."
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
