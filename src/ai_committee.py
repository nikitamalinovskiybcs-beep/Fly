"""Research-only AI committee: debate, vote, quorum and safety vetoes."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
import re


def _proposal_key(proposal: Mapping[str, object]) -> str:
    text = " ".join(
        str(proposal.get(field, ""))
        for field in ("component", "title", "change")
    ).lower()
    return re.sub(r"\W+", " ", text).strip()[:180]


def _safety_veto(proposal: Mapping[str, object]) -> str | None:
    text = " ".join(str(value) for value in proposal.values()).lower()
    for marker in ("create trades", "change production", "bypass gate", "ignore oos"):
        if marker in text:
            return marker
    return None


def deliberate(
    panel: Mapping[str, object],
    *,
    quorum: int = 2,
    majority: float = 0.5,
) -> dict[str, object]:
    """Aggregate independent completed reviews into a research decision."""
    votes: dict[str, list[dict[str, object]]] = defaultdict(list)
    completed = []
    for review_item in panel.get("reviews", []):
        if not isinstance(review_item, Mapping):
            continue
        if review_item.get("status") != "completed":
            continue
        review = review_item.get("review")
        if not isinstance(review, Mapping):
            continue
        provider = str(review_item.get("provider", review.get("provider", "unknown")))
        completed.append(provider)
        proposals = review.get("proposals", [])
        if not isinstance(proposals, Sequence) or isinstance(proposals, (str, bytes)):
            continue
        for proposal in proposals:
            if not isinstance(proposal, Mapping):
                continue
            key = _proposal_key(proposal)
            if key:
                votes[key].append({"provider": provider, "proposal": dict(proposal)})

    decisions = []
    for key, ballots in votes.items():
        representative = dict(ballots[0]["proposal"])
        vetoes = [
            _safety_veto(ballot["proposal"])
            for ballot in ballots
            if _safety_veto(ballot["proposal"])
        ]
        vote_count = len(ballots)
        passed = vote_count >= quorum and vote_count / max(len(completed), 1) >= majority
        decisions.append(
            {
                "proposal_id": f"committee-{len(decisions) + 1:03d}",
                "proposal_key": key,
                "proposal": representative,
                "votes_for": vote_count,
                "voters": [str(ballot["provider"]) for ballot in ballots],
                "quorum": quorum,
                "majority_required": majority,
                "safety_veto": vetoes[0] if vetoes else None,
                "decision": (
                    "blocked_safety"
                    if vetoes
                    else "research_approved" if passed else "deferred_insufficient_vote"
                ),
            },
        )
    return {
        "status": (
            "consensus_available"
            if completed and decisions
            else "unavailable"
        ),
        "completed_reviewers": completed,
        "reviewer_count": len(completed),
        "proposal_count": len(decisions),
        "decisions": decisions,
        "quorum": quorum,
        "majority": majority,
        "moderation": {
            "independent_reviews_required": True,
            "dissent_preserved": True,
            "safety_veto_enabled": True,
        },
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
