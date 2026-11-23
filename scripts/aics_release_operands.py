"""Reconcile the November 19 scores using explicit ratios from dated research records."""
from bisect import bisect_left, bisect_right
from decimal import Decimal

from scripts.aics_research_snapshot import read


def rank_inputs(values):
    last = values[-1]
    reference = sorted(values[:-1])
    if len(reference) != 23:
        raise ValueError("The dated percentile needs 23 prior months")
    midpoint = Decimal(bisect_left(reference, last) + bisect_right(reference, last)) / 2
    return midpoint, len(reference)


def ratios(decliners, basket_size):
    credit = read("private_credit_3bdc_3quarter_22values_2026-11-19")["three_issuer_quarter_comparison"]
    by_period = {q["period_end"]: {r["issuer"]: Decimal(r["nonaccrual_amortized_cost_pct"])
                                  for r in q["issuer_rows"]} for q in credit}
    june, september = by_period["2026-06-30"], by_period["2026-09-30"]
    pru = read("insurers_pru_met_mixed_original_sec_external_rehash_2026-11-19")["joint_replay"]
    observations = read("observed_source_review_2026-11-19")["observations"]
    pru_loans_m = observations["pru_commercial_mortgage_and_other_loans"]["net_loans_usd"] // 1_000_000
    volatility = read("ust30_yield_change_volatility_2024_2026")["months"]
    repo = read("repo_24_month_observed_research_2026-11-18")["monthly_observations"]
    funding = read("neocloud_q2_funding_2026")["cash_bridges"]
    cloud_cash = read("neocloud_cash_coverage_2026_h1")["observations"]
    purchases = sum(Decimal(r["cash_purchases"]) for r in cloud_cash if r["period"] == "2026-Q2")
    triples = read("hyperscalers_leave_one_out_2026_q2_q3")["rows"]
    # Each issuer occurs in three of the four leave-one-out portfolios.
    gap = -sum(Decimal(r["september"]) for r in triples) / 3
    capex = read("hyperscalers_operating_cash_flow_coverage_2026_q3")["totals"]["current"]["cash_ppe"]
    loans = read("coreweave_two_spv_debt_original_independent_rehash_2026-11-19")
    site = read("applied_digital_polaris_capacity_2026-10-02")
    capacity = site["contracted_full_buildout_mw"]
    fed = observations["fed_naics_3344_utilization"]
    demand = read("broadcom_ai_semiconductor_revenue_2026_q2_q3")
    return {
        "Private Credit": (sum(v > june[issuer] for issuer, v in september.items()), len(june)),
        "Insurers": (pru["pru_nonaccrual_without_related_acl_millions"]["2026-09-30"], pru_loans_m),
        "UST 30Y": rank_inputs([Decimal(r["sample_sd_daily_change_bp"]) for r in volatility]),
        "Neoclouds": (sum(Decimal(r["cash_purchases_less_operating_cash"]) for r in funding), purchases),
        "AI Equities": (decliners, basket_size),
        "Hyperscalers": (gap, capex),
        "SPV": (loans["separate_same_date_facility_reported_debt_total_usd_m"],
                loans["separate_same_date_facility_ceiling_total_usd_m"]),
        "Repo": rank_inputs([r["sofr_minus_iorb_bps"] for r in repo]),
        "Power/Data Centers": (capacity - site["operating_mw"], capacity),
        "Semiconductors Supply": (Decimal(fed["september_revised_pct"]) + Decimal(fed["change_within_release_pp"]), 100),
        "AI Demand": (-demand["q3_actual_less_prior_guidance"], demand["records"][0]["next_quarter_guidance"]),
    }


def score_from_ratio(numerator, denominator):
    if denominator <= 0:
        raise ValueError("Non-positive release denominator")
    percentage = 100 * Decimal(numerator) / Decimal(denominator)
    return round(max(Decimal(0), min(Decimal(100), percentage)), 2)
