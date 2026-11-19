"""Research snapshot for 18 November. Run python -m scripts.aics_research_snapshot."""
import json
from datetime import date, timedelta
from decimal import Decimal

from .aics_four_node_snapshot import CUTOFF, available, read, snapshot


def credit_breadth():
    quarters = read("private_credit_3bdc_3quarter_22values_2026-11-19")["three_issuer_quarter_comparison"]
    panels = []
    for end in ("2026-06-30", "2026-09-30"):
        quarter, = [q for q in quarters if q["period_end"] == end]
        amounts = {}
        for row in quarter["issuer_rows"]:
            available(row["available_at"])
            amounts[row["issuer"]] = Decimal(row["nonaccrual_amortized_cost_pct"])
        if len(quarter["issuer_rows"]) != 3 or set(amounts) != {"ARCC", "BXSL", "OBDC"}:
            raise ValueError("Incomplete BDC panel")
        panels.append(amounts)
    earlier, later = panels
    return round(100 * sum(later[name] > earlier[name] for name in later) / len(later), 2)


def repo_pressure():
    rows = read("repo_24_month_observed_research_2026-11-18")["monthly_observations"]
    dates = [row["as_of"] for row in rows]
    if len(dates) != 24 or dates != sorted(set(dates)) or dates[-1] != "2026-10-31":
        raise ValueError("Incomplete repo reference window")
    spreads = []
    for row in rows:
        available(row["as_of"])
        if not row["market_effective_date"] <= row["publication_proxy_date"] <= row["as_of"]:
            raise ValueError("Invalid publication date")
        spread = 100 * (Decimal(row["sofr_pct"]) - Decimal(row["iorb_pct"]))
        if spread != row["sofr_minus_iorb_bps"]:
            raise ValueError("Rate spread mismatch")
        spreads.append(spread)
    rank = sum((v < spreads[-1]) + 0.5 * (v == spreads[-1]) for v in spreads[:-1])
    return round(100 * rank / (len(spreads) - 1), 2)


def demand_shortfall():
    prior, current = read("broadcom_ai_semiconductor_revenue_2026_q2_q3")["records"]
    for row in (prior, current):
        available(row["available_at"])
        if date.fromisoformat(row["filed_at"]) + timedelta(days=14) != date.fromisoformat(row["available_at"]):
            raise ValueError("SEC availability mismatch")
    if prior["available_at"] >= current["period_end"] or prior["next_quarter_guidance"] <= 0:
        raise ValueError("Invalid prior-quarter guidance")
    return round(max(0, min(100, 100 * (1 - current["actual"] / prior["next_quarter_guidance"]))), 2)


if __name__ == "__main__":
    scores = snapshot()
    scores.update({"Private Credit": credit_breadth(), "Repo": repo_pressure(),
                   "AI Demand": demand_shortfall()})
    print(json.dumps({"as_of": CUTOFF.isoformat(), "research_scores": scores,
                      "certified": False, "index_aics": None}, indent=2))
