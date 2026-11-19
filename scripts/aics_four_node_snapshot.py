"""Research-only four-node snapshot. Run from the repository root."""
import json
from datetime import date
from pathlib import Path

DATA = Path("aics_data/research")
CUTOFF = date(2026, 11, 18)


def read(name):
    return json.loads((DATA / (name + ".json")).read_text())


def available(day):
    if date.fromisoformat(day) > CUTOFF:
        raise ValueError("Source was unavailable at the snapshot date")


def funding_gap(cash, purchases):
    if purchases <= 0:
        raise ValueError("Positive capital purchases required")
    return round(max(0, min(100, 100 * (1 - cash / purchases))), 2)


def snapshot():
    neo = read("neocloud_cash_coverage_2026_h1")
    quarter = [r for r in neo["observations"] if r["period"] == "2026-Q2"]
    hyper = read("hyperscalers_operating_cash_flow_coverage_2026_q3")["rows"]
    for rows, names in [(quarter, {"CoreWeave", "Nebius"}),
                        (hyper, {"Microsoft", "Amazon", "Alphabet", "Meta"})]:
        if len(rows) != len(names) or {r["issuer"] for r in rows} != names:
            raise ValueError("Incomplete issuer coverage")
    for row in quarter:
        available(row["all_cited_checks_available"])
    for row in hyper:
        available(row["available_at"])
    facilities = neo["coreweave_facilities"]
    available(facilities["available_at"])
    loans = facilities["facilities"]
    if sorted(r["facility"] for r in loans) != ["DDTL 4.0", "DDTL 5.0"]:
        raise ValueError("Unexpected facility coverage")
    debt = sum(r["reported_debt_usd_m"] for r in loans)
    limit = sum(r["facility_ceiling_usd_m"] for r in loans)
    if not 0 <= debt <= limit or limit <= 0:
        raise ValueError("Invalid facility balances")
    releases = read("ust_month_end_release_dates_2026-11-19")["records"]
    months = read("ust30_yield_change_volatility_2024_2026")["months"]
    timeline = {r["cutoff"]: r for r in releases}
    dates = [r["as_of"] for r in months]
    if len(dates) != 24 or dates != sorted(set(dates)) or dates[-1] != "2026-10-31":
        raise ValueError("Incomplete volatility reference period")
    vol = []
    for row in months:
        cutoff = row["as_of"]
        available(cutoff)
        release = timeline[cutoff]
        if not (row["last_yield_date"] == release["observation"]
                <= release["first_nonmissing_vintage"] <= cutoff):
            raise ValueError("Inconsistent vintage")
        vol.append(float(row["sample_sd_daily_change_bp"]))
    # Rank October against the preceding 23 monthly observations only.
    rank = sum((v < vol[-1]) + 0.5 * (v == vol[-1]) for v in vol[:-1])
    return {
        "UST 30Y": round(100 * rank / len(vol[:-1]), 2),
        "Neoclouds": funding_gap(sum(float(r["operating_cash_flow"]) for r in quarter),
                                 sum(float(r["cash_purchases"]) for r in quarter)),
        "Hyperscalers": funding_gap(sum(r["current"]["operating_cash_flow"] for r in hyper),
                                    sum(r["current"]["cash_ppe"] for r in hyper)),
        "SPV": round(100 * debt / limit, 2),
    }


if __name__ == "__main__":
    print(json.dumps({"as_of": CUTOFF.isoformat(), "research_scores": snapshot(),
                      "certified": False, "index_aics": None}, indent=2))
