"""Commercial-readiness classification based on evidence, not marketing claims."""

from typing import Dict


def assess_commercial_readiness(
    evidence_gate: Dict,
    quality_report: Dict,
) -> Dict:
    """Classify what the product may honestly be sold as today."""
    gate_passed = bool(evidence_gate.get("passed"))
    realized_notes = int(quality_report.get("realized_notes", 0))
    historical_windows = int(quality_report.get("historical_windows", 0))

    if not gate_passed:
        status = "not_ready"
        label = "NOT READY FOR LIVE PRODUCT USE"
        allowed_claim = "Diagnostic software only; market evidence is incomplete."
    elif realized_notes < 30:
        status = "pilot_ready"
        label = "PILOT MVP READY"
        allowed_claim = "Decision-support platform for supervised pilot use."
    else:
        status = "production_review"
        label = "PRODUCTION REVIEW"
        allowed_claim = "Pilot evidence exists; independent validation is still required."

    return {
        "status": status,
        "label": label,
        "pilot_ready": gate_passed,
        "production_ready": realized_notes >= 30 and historical_windows >= 30,
        "human_review_required": True,
        "legal_or_regulatory_approval": False,
        "compliance_approval": False,
        "realized_notes": realized_notes,
        "historical_windows": historical_windows,
        "allowed_claim": allowed_claim,
        "blocked_claim": "Do not claim guaranteed returns or proven live win rate.",
        "blocked_claims": [
            "guaranteed returns",
            "proven live win rate",
            "AI-approved investment",
            "compliance-approved product",
            "replacement for licensed advice or suitability review",
        ],
        "conditions_precedent": [
            "independent fixed-24m OOS or paper evidence",
            "sufficient realized-note sample and outcome quality",
            "provenance-verified dealer quote and quote-fit",
            "independent model-risk validation",
            "human compliance and suitability review",
        ],
    }
