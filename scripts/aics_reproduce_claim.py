#!/usr/bin/env python3
"""Reproduce a claimed AICS score from independently sourced, PIT-tagged node scores.

This is a diagnostic calculation, never a promotion or trading decision.
Input JSON: {"as_of":"YYYY-MM-DD","nodes":[{"name":"Private Credit",
"score":63.2,"available_at":"YYYY-MM-DD","source_id":"immutable reference"},...]}
All eleven nodes are required. No missing-value imputation or look-ahead.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

WEIGHTS = {
    "Private Credit": 150, "Insurers": 125, "UST 30Y": 125,
    "Neoclouds": 100, "AI Equities": 100, "Hyperscalers": 100,
    "SPV": 100, "Repo": 100, "Power/Data Centers": 50,
    "Semiconductors Supply": 50, "AI Demand": 50,
}
assert len(WEIGHTS) == 11 and sum(WEIGHTS.values()) == 1050

def reproduce(payload, claimed=None):
    errors = []
    try:
        as_of = dt.date.fromisoformat(payload["as_of"])
    except (KeyError, TypeError, ValueError):
        as_of = None
        errors.append("invalid_as_of")
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        nodes = []
        errors.append("nodes_missing")
    seen = set()
    scores = {}
    for row in nodes:
        if not isinstance(row, dict):
            errors.append("invalid_node")
            continue
        name = row.get("name")
        if name not in WEIGHTS or name in seen:
            errors.append("unknown_or_duplicate_node")
            continue
        seen.add(name)
        score = row.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 100:
            errors.append(f"{name}:invalid_score")
            continue
        if not isinstance(row.get("source_id"), str) or not row["source_id"].strip():
            errors.append(f"{name}:missing_source_id")
        try:
            available_at = dt.date.fromisoformat(row["available_at"])
            if as_of is None or available_at > as_of:
                errors.append(f"{name}:lookahead")
        except (KeyError, TypeError, ValueError):
            errors.append(f"{name}:missing_available_at")
        scores[name] = float(score)
    missing = sorted(set(WEIGHTS) - seen)
    if missing:
        errors.append("missing_nodes:" + ",".join(missing))
    if errors:
        return {"status":"BLOCKED", "errors":errors, "reproduced_aics":None,
                "claimed_aics":claimed, "claim_reproduced":False, "trades_created":False}
    hot = sum(value > 60 for value in scores.values())
    multiplier = min(1.35, max(1.0, 1 + .20 * min(1, max(0, hot-2)) + .05 * max(0, hot-3)))
    base = sum(WEIGHTS[name] * scores[name] / 100 for name in WEIGHTS)
    result = base * multiplier
    return {"status":"DIAGNOSTIC_ONLY_UNVERIFIED", "errors":[], "as_of":str(as_of),
            "hot_nodes":hot, "base_score":round(base, 8), "multiplier":multiplier,
            "reproduced_aics":round(result, 8), "claimed_aics":claimed,
            "claim_reproduced":(abs(result-claimed) <= 0.05 if claimed is not None else None),
            "independently_verified_pit":False, "promotion":"BLOCKED", "trades_created":False}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", help="JSON with 11 real PIT-tagged node scores")
    p.add_argument("--claimed", type=float, help="Historical claimed score, e.g. 646.3")
    p.add_argument("--out", default="aics_score_reproduction.json")
    args = p.parse_args()
    if args.claimed is not None and not math.isfinite(args.claimed):
        p.error("claimed must be finite")
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON root must be object")
    except (OSError, ValueError) as exc:
        payload = {}
        print(f"Input not usable: {exc}")
    result = reproduce(payload, args.claimed)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
