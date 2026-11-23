"""Canonical fact-checking for evidence claims in research reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def build_fact_check_report(
    claims: Sequence[Mapping[str, object]],
    evidence: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Classify claims as proven, unverified, or unsupported."""
    checked: list[dict[str, object]] = []
    for claim in claims:
        claim_id = str(claim.get("claim_id", "unknown"))
        references = claim.get("evidence_ids", [])
        if not isinstance(references, Sequence) or isinstance(references, (str, bytes)):
            references = []
        linked = [evidence.get(str(ref)) for ref in references]
        linked = [item for item in linked if isinstance(item, Mapping)]
        if not linked:
            status = "unsupported"
        elif all(item.get("verified") is True for item in linked):
            status = "proven"
        else:
            status = "unverified"
        checked.append({
            "claim_id": claim_id,
            "claim": claim.get("claim"),
            "status": status,
            "evidence_ids": [str(ref) for ref in references],
        })
    unsupported = [item["claim_id"] for item in checked if item["status"] != "proven"]
    return {
        "status": "passed" if not unsupported else "blocked",
        "claims": checked,
        "unsupported_or_unverified": unsupported,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
