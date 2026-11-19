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


def insurer_credit_share():
    data = read("insurers_pru_met_mixed_original_sec_external_rehash_2026-11-19")
    filing, = [r for r in data["originals"] if r["issuer"] == "PRU"]
    available(filing["sec_available_at"])
    if date.fromisoformat(filing["filed_at"]) + timedelta(days=14) != date.fromisoformat(filing["sec_available_at"]):
        raise ValueError("Invalid SEC availability")
    period = filing["balance_date"]
    replay = data["joint_replay"]
    subset = replay["pru_nonaccrual_without_related_acl_millions"][period]
    loans = replay["pru_commercial_mortgage_and_other_loans_net_millions"][period]
    if not 0 <= subset <= loans or loans <= 0:
        raise ValueError("Invalid loan balances")
    return round(100 * subset / loans, 2)


def capacity_scores():
    observed = read("observed_source_review_2026-11-19")["observations"]
    fed = observed["fed_naics_3344_utilization"]
    available(fed["release_date"])
    utilization = float(fed["october_preliminary_pct"])
    # Applied Digital's dated October 2 IR release reports 400 MW contracted.
    # https://ir.applieddigital.com/news-events/press-releases/detail/161
    available("2026-10-02")
    site = observed["applied_digital_polaris_forge_1"]
    available(site["status_date"])
    operating = site["two_operating_buildings_capacity_mw"]
    if not 0 <= operating <= 400 or not 0 <= utilization <= 100:
        raise ValueError("Invalid capacity inputs")
    return {"Semiconductors Supply": utilization,
            "Power/Data Centers": round(100 * (400 - operating) / 400, 2)}


if __name__ == "__main__":
    scores = snapshot()
    scores.update({"Private Credit": credit_breadth(), "Repo": repo_pressure(),
                   "AI Demand": demand_shortfall()})
    scores["Insurers"] = insurer_credit_share()
    scores.update(capacity_scores())
    print(json.dumps({"as_of": CUTOFF.isoformat(), "research_scores": scores,
                      "certified": False, "index_aics": None}, indent=2))
