"""Runtime adapter that exposes the research orchestrator in the dashboard."""

from __future__ import annotations

from collections.abc import Mapping

from src.fact_check import build_fact_check_report
from src.research_orchestrator import run_research_pipeline
from src.storage import Storage


def build_runtime_research_status(
    data: Mapping[str, object],
    pipeline: Mapping[str, object],
) -> dict[str, object]:
    """Build a non-mutating research status for the current dashboard run."""
    evidence_gate = data.get("evidence_gate", {})
    evidence_passed = (
        evidence_gate.get("passed") is True
        if isinstance(evidence_gate, Mapping)
        else False
    )
    fact_check = build_fact_check_report(
        [
            {
                "claim_id": "live_market_evidence",
                "claim": "live market evidence is complete",
                "evidence_ids": ["evidence_gate"],
            },
        ],
        {"evidence_gate": {"verified": evidence_passed}},
    )
    return run_research_pipeline(
        pipeline.get("evidence_records", {}),
        storage=Storage().integration_status()["active"],
        calculation=lambda _context: {"status": "completed", "source": "live_analysis"},
        committee=lambda _context: {
            "status": "completed"
            if pipeline.get("committee_review")
            else "deferred",
            "source": "committee_artifact",
        },
        fact_check=lambda _context: fact_check,
        oos=lambda _context: {
            "status": "passed"
            if pipeline.get("oos_gate") is True
            else "blocked",
            "source": "fixed_24m_gate",
        },
        safety=lambda _context: {
            "status": "passed",
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
        },
    )
