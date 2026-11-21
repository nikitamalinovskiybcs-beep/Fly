"""Reproduce the 20-Nov-2026 AICS research close; no synthetic backfill or certification.

Only seven regular-session equities are refreshed. The ten other research
proxies are explicitly carried from the signed 19-Nov research release.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from scripts.aics_research_20261119 import composite
from scripts.aics_score_reproducibility_gate import WEIGHTS

RECEIPT = Path("aics_data/research/aics_2026_11_20_close_research_rollover.json")
BASE_RELEASE = Path("aics_data/progress/research_release_2026-11-19.json")
SYMBOLS = ("NVDA", "MSFT", "GOOGL", "AMZN", "META", "MU", "ORCL")


def _decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid numeric source observation") from exc
    if not result.is_finite():
        raise ValueError("Non-finite numeric observation")
    return result


def calculate(record=None, base_release=None):
    record = record if record is not None else json.loads(RECEIPT.read_text(encoding="utf-8"))
    base_release = (base_release if base_release is not None else
                    json.loads(BASE_RELEASE.read_text(encoding="utf-8")))
    if (record.get("schema") != "aics-friday-close-research-v1"
            or record.get("session") != "2026-11-20"
            or record.get("session_close") != "2026-11-20T16:00:00-05:00"
            or record.get("rollover", {}).get("frozen_release") != str(BASE_RELEASE)
            or record["rollover"].get("non_equity_inputs_from") != "2026-11-18"
            or base_release["first_publication"]["session"] != "2026-11-19"):
        raise ValueError("Mismatched close or unapproved input vintage")
    if (record.get("certified_aics") is not None
            or record.get("promotion") != "RESEARCH_ONLY_UNCERTIFIED"
            or record.get("trades_created") is not False
            or any(record["source_caveats"].get(k) is not False for k in
                   ("raw_webpage_bytes_archived", "primary_exchange_feed_pit_attested",
                    "independent_24_month_oos"))):
        raise ValueError("Uncertified research may not be promoted to production")
    rows = record["observations"]
    if (len(rows) != len(SYMBOLS)
            or tuple(row.get("symbol") for row in rows) != SYMBOLS):
        raise ValueError("Seven-security close roster incomplete or reordered")
    daily_returns = {}
    for row in rows:
        symbol = row["symbol"]
        if row.get("source_url") != f"https://stockanalysis.com/stocks/{symbol.lower()}/history/":
            raise ValueError("Unapproved/untraceable historical OHLC source")
        opening, closing = _decimal(row["open"]), _decimal(row["close"])
        if opening <= 0 or closing <= 0:
            raise ValueError("Non-positive or missing regular-session price")
        daily_returns[symbol] = (closing / opening - 1) * 100
    decliners = sum(v < 0 for v in daily_returns.values())
    basket_return = sum(daily_returns.values(), Decimal(0)) / len(SYMBOLS)
    scores = dict(base_release["first_publication"]["scores"])
    if (scores.keys() != WEIGHTS.keys() or sum(WEIGHTS.values()) != 1050
            or scores["AI Equities"] != 100):
        raise ValueError("Fixed weights or known original 11-node release mutated")
    scores["AI Equities"] = float(Decimal(100) * decliners / len(SYMBOLS))
    research = composite(scores)
    raw = sum((_decimal(scores[n]) * WEIGHTS[n] / 100 for n in WEIGHTS), Decimal(0))
    h = sum(score > 60 for score in scores.values())
    multiplier = min(Decimal("1.35"), Decimal(1) + Decimal("0.20") *
                     min(Decimal(1), max(Decimal(0), Decimal(h - 2))) +
                     Decimal("0.05") * max(Decimal(0), Decimal(h - 3)))
    total = (raw * multiplier).quantize(Decimal("0.01"))
    expected = record["expected"]
    checks = {
        "observed_symbols": len(SYMBOLS),
        "declining_from_open_to_close": decliners,
        "equal_weight_open_to_close_pct": str(basket_return.quantize(Decimal("0.000001"))),
        "ai_equities_score": f"{scores['AI Equities']:.2f}",
        "raw_weighted_sum": str(raw),
        "hot_nodes": h,
        "multiplier": f"{multiplier:.2f}",
        "research_aics": str(total),
        "previous_research_aics": f"{_decimal(base_release['first_publication']['research_aics']):.2f}",
        "change_vs_previous": f"{total - _decimal(base_release['first_publication']['research_aics']):.2f}",
    }
    if checks != expected or Decimal(str(research["research_aics"])) != total:
        raise ValueError("20-Nov research close does not reconcile to sealed receipt")
    return {
        "session": record["session"],
        "research_aics": str(total),
        "certified_aics": None,
        "change_vs_2026_11_19": checks["change_vs_previous"],
        "source_freshness": "7 EQUITY CURRENT, 10 OTHER NODES CARRIED FROM 2026-11-18",
        "basket_return_open_to_close_pct": checks["equal_weight_open_to_close_pct"],
        "declining_securities": decliners,
        "raw_weighted_sum": str(raw),
        "hot_nodes": h,
        "multiplier": str(multiplier),
        "nodes": [
            {"node": node, "weight": WEIGHTS[node], "score": scores[node],
             "weighted_points_after_multiplier": str(
                 _decimal(scores[node]) * WEIGHTS[node] * multiplier / 100),
             "input_status": "2026-11-20 OBSERVED EQUITY" if node == "AI Equities" else
                             "CARRIED FROM 2026-11-18"}
            for node in WEIGHTS
        ],
        "promotion": "RESEARCH_ONLY_UNCERTIFIED",
        "trades_created": False,
    }


if __name__ == "__main__":
    print(json.dumps(calculate(), indent=2, ensure_ascii=False))
