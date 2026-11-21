"""Single research-only readiness contract for Phoenix."""

from __future__ import annotations

from collections.abc import Mapping


SAFETY_FLAGS = {
    "production_weights_changed": False,
    "verdict_mutated": False,
    "trades_created": False,
}


def evaluate_readiness(
    evidence: Mapping[str, object],
    committee: Mapping[str, object],
) -> dict[str, object]:
    blockers: list[str] = []
    if evidence.get("term_months") != 24:
        blockers.append("fixed-24m-required")
    if tuple(evidence.get("anchors", ())) != (6, 12, 18, 24):
        blockers.append("anchors-required:6,12,18,24")
    if evidence.get("provenance_complete") is not True:
        blockers.append("provenance-incomplete")
    if evidence.get("baseline_beaten") is not True:
        blockers.append("baseline-not-beaten")
    if committee.get("quorum") is not True:
        blockers.append("committee-quorum-missing")

    unavailable = list(committee.get("unavailable", ()))
    dissent = list(committee.get("dissent", ()))
    conditions = [
        "human-model-risk-review",
        "human-compliance-review",
        "chronological-fixed-24m-paper-evidence",
    ]
    return {
        "status": "blocked" if blockers else "research_ready",
        "production_approval": False,
        "blockers": blockers,
        "conditions_precedent": conditions,
        "evidence_lineage": sorted(str(key) for key in evidence),
        "committee_lineage": {
            "completed_votes": committee.get("completed_votes", 0),
            "approval_votes": committee.get("approval_votes", 0),
            "unavailable": unavailable,
            "dissent": dissent,
        },
        "safety_flags": dict(SAFETY_FLAGS),
    }
