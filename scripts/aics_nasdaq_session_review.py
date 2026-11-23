"""Replay two regular sessions for the November 19 research basket and attribute its full AICS."""
import argparse
import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from scripts.aics_collect_ai_equities_prices import (
    RESEARCH_SYMBOLS,
    _date,
    _number,
    quote_url,
    retrieve,
    validate_price_response,
)
from scripts.aics_research_20261119 import calculate, composite
from scripts.aics_research_snapshot import read
from scripts.aics_score_reproducibility_gate import WEIGHTS

PRIOR, SESSION = date(2026, 11, 18), date(2026, 11, 19)
RECEIPT = Path("aics_data/research/ai_equities_2026_11_19_nasdaq_session_review.json")


def session_prices(raw, symbol):
    validate_price_response(raw, PRIOR, SESSION)
    data = json.loads(raw)["data"]
    if data["symbol"] != symbol:
        raise ValueError(f"Nasdaq symbol mismatch for {symbol}")
    values = {}
    for row in data["tradesTable"]["rows"]:
        values[_date(row["date"])] = tuple(_number(row[k], strictly_positive=True) for k in ("open", "close"))
    if values.keys() != {PRIOR, SESSION}:
        raise ValueError(f"Expected both session dates for {symbol}")
    return values


def analyze(sources, raw_directory=None):
    if len(sources) != len(RESEARCH_SYMBOLS) or {s["symbol"] for s in sources} != set(RESEARCH_SYMBOLS):
        raise ValueError("Incomplete or duplicated seven-security roster")
    initial = calculate()
    vendor = {r["symbol"]: r for r in read("ai_equities_2026_11_19_session")["rows"]}
    returns = {PRIOR: {}, SESSION: {}}
    differences = {"open": [], "close": []}
    for source in sources:
        symbol, digest = source["symbol"], source["sha256"]
        url = quote_url(symbol, PRIOR, SESSION)
        if source["url"] != url:
            raise ValueError(f"Unexpected quote source for {symbol}")
        raw = (retrieve(url) if raw_directory is None else
               (raw_directory / f"{symbol}_{digest}.json").read_bytes())
        if len(raw) != source["bytes"] or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f"Quote file differs from the recorded capture for {symbol}")
        prices = session_prices(raw, symbol)
        for day, (opening, closing) in prices.items():
            returns[day][symbol] = 100 * (closing / opening - 1)
        for i, (field, original) in enumerate((("open", "reported_open"), ("close", "vendor_regular_close"))):
            if prices[SESSION][i] != Decimal(str(vendor[symbol][original])):
                differences[field].append(symbol)

    sessions = []
    for day, daily in returns.items():
        sessions.append({"session": day.isoformat(), "decliners": sorted(n for n, v in daily.items() if v < 0),
                         "constituents": len(daily),
                         "equal_weight_open_to_close_pct": format(sum(daily.values()) / len(daily), ".6f")})
    scores = dict(initial["scores"])
    scores["AI Equities"] = 100 * len(sessions[-1]["decliners"]) / len(RESEARCH_SYMBOLS)
    current = composite(scores)
    multiplier = Decimal(str(current["multiplier"]))
    raw = {n: Decimal(str(score)) * WEIGHTS[n] / 100 for n, score in scores.items()}
    base = sum(raw.values())
    level = base * multiplier
    if base != Decimal(str(current["raw"])) or round(level, 2) != Decimal(str(current["research_aics"])):
        raise ValueError("Node contributions do not reconcile to the research composite")
    return {
        "equity_basket_sessions": sessions, "price_fields_differing_from_first_capture_on_nov_19": differences,
        "initial_basket_open_to_close_pct": round(initial["basket_return_pct"], 6),
        "raw_point_total": str(base), "hot_nodes": current["hot_nodes"], "multiplier": str(multiplier),
        "points_added_by_multiplier": str(level - base), "research_aics": current["research_aics"],
        "contributions_at_observed_multiplier": [
            {"node": n, "weight": WEIGHTS[n], "score": scores[n], "points": str(amount * multiplier)}
            for n, amount in sorted(raw.items(), key=lambda item: -item[1])],
        "full_index_ytd_change": None, "certified_aics": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-directory", type=Path, help="Pinned Nasdaq JSON files. Omit to fetch from Nasdaq.")
    args = parser.parse_args()
    receipt = json.loads(RECEIPT.read_text())
    result = analyze(receipt["sources"], args.raw_directory)
    if result != receipt["result"]:
        raise SystemExit("The replay differs from the recorded result.")
    print(json.dumps(result, indent=2))
