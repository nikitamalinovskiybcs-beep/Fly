"""AICS evidence-gated index. No inferred observations, backfill or look-ahead."""
from datetime import date, timedelta
from math import isfinite

WEIGHTS = {
    "private_credit": 150, "insurers": 125, "ust_30y": 125,
    "neoclouds": 100, "ai_equities": 100, "hyperscalers": 100,
    "spv": 100, "repo": 100, "power_data_centers": 50,
    "semiconductors_supply": 50, "ai_demand": 50,
}
assert sum(WEIGHTS.values()) == 1050

def sec_available_at(filed_at):
    """SEC eligibility starts 14 calendar days after filing."""
    return date.fromisoformat(filed_at) + timedelta(days=14)

def alfred_value_at(observations, observation_date, as_of):
    """Select an observation only from its actual vintage interval."""
    target = date.fromisoformat(observation_date)
    cutoff = date.fromisoformat(as_of)
    if target > cutoff:
        return None
    eligible = [r for r in observations
                if r["date"] == observation_date
                and date.fromisoformat(r["realtime_start"]) <= cutoff
                <= date.fromisoformat(r["realtime_end"])
                and r.get("value") not in (None, "", ".")]
    if len(eligible) != 1:
        return None
    try:
        value = float(eligible[0]["value"])
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None

def calculate(node_scores, *, verified_nodes=None):
    """Publish only when all 11 scores have verified PIT provenance.

    node_scores: canonical node name -> observed, verified 0..100 stress score.
    verified_nodes: iterable of nodes whose upstream evidence passed PIT checks.
    """
    verified = set(verified_nodes or ())
    missing = sorted(set(WEIGHTS) - set(node_scores))
    unverified = sorted(set(WEIGHTS) - verified)
    invalid = sorted(name for name, score in node_scores.items()
                     if name not in WEIGHTS or isinstance(score, bool)
                     or not isinstance(score, (int, float))
                     or not isfinite(score) or not 0 <= score <= 100)
    if missing or unverified or invalid:
        return {"publishable": False, "aics": None, "verdict": None,
                "missing_nodes": missing, "unverified_nodes": unverified,
                "invalid_nodes": invalid}
    hot = sum(node_scores[n] > 60 for n in WEIGHTS)
    multiplier = min(1.35, max(1.0,
        1 + 0.20 * min(1, max(0, hot - 2)) + 0.05 * max(0, hot - 3)))
    weighted = sum(WEIGHTS[n] * node_scores[n] / 100 for n in WEIGHTS)
    index = weighted * multiplier
    verdict = "entry" if index < 450 else "watch" if index <= 500 else "cash"
    return {"publishable": True, "aics": index, "base": weighted,
            "hot_nodes": hot, "multiplier": multiplier, "verdict": verdict}
