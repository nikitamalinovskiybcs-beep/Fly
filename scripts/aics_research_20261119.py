"""November 19 research composite. Ten inputs explicitly carried from November 18."""
import json
from math import isfinite

from .aics_research_snapshot import november_18_scores, read
from .aics_score_reproducibility_gate import WEIGHTS


def composite(scores):
    if scores.keys() != WEIGHTS.keys() or sum(WEIGHTS.values()) != 1050:
        raise ValueError("Invalid or incomplete research composite")
    for node, score in scores.items():
        if type(score) not in (int, float) or not isfinite(score) or not 0 <= score <= 100:
            raise ValueError(f"Invalid research score for {node}")
    raw = sum(WEIGHTS[n] * s / 100 for n, s in scores.items())
    hot = sum(s > 60 for s in scores.values())
    multiplier = min(1.35, 1 + 0.20 * min(1, max(0, hot - 2)) + 0.05 * max(0, hot - 3))
    return {"scores": scores, "raw": raw, "hot_nodes": hot, "multiplier": multiplier,
            "research_aics": round(raw * multiplier, 2), "certified_aics": None}


def calculate():
    data = read("ai_equities_2026_11_19_session")
    directory = read("ai_equities_2026_11_19_nasdaq_current_directory_rehash")
    rows = data["rows"]
    names = {r["symbol"] for r in directory["current_research_securities"]}
    if len(rows) != 7 or {r["symbol"] for r in rows} != names or data["session"] != "2026-11-19":
        raise ValueError("Session or basket mismatch")
    if any(min(r["vendor_regular_close"], r["reported_open"]) <= 0 for r in rows):
        raise ValueError("Invalid price")
    returns = [r["vendor_regular_close"] / r["reported_open"] - 1 for r in rows]
    scores = november_18_scores()
    scores["AI Equities"] = 100 * sum(r < 0 for r in returns) / len(rows)
    return {"session": data["session"], "basket_return_pct": 100 * sum(returns) / len(rows),
            **composite(scores)}


if __name__ == "__main__":
    print(json.dumps(calculate(), indent=2))
