"""Reconstruct observed AICS monthly source coverage; never invent a history.

24-month research panel from *real* month-end S&P 500, Treasury DGS30
volatility and NY Fed SOFR - IORB spread, plus separately dated 11-node
research-score candidates. Original 24-month complete AICS/spread remains
null. No hot-node multiplier or trading bands.

The event ledger only becomes visible when the recorded all-issuer SEC+14 /
original-publication availability gate has passed. Carry-forward is
chronological use of the latest already eligible observation; the recorded
event origin remains explicit. Retrospective data are NOT certified PIT.
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_neocloud_2025_sec_quarters import calculate as neocloud_2025_original_sec
from scripts.aics_neocloud_2025_q4_sec_original import calculate as neocloud_2025_q4_sec
from scripts.aics_fed_g17_first_release_monthly import read as g17_naics3344_first_releases
from scripts.aics_fed_g17_first_release_monthly import initial_publication as g17_initial_publication
from scripts.aics_pru_insurers_original_quarters import calculate as pru_insurers_quarters

ROOT = Path("aics_data/research")
SP500 = ROOT / "sp500_24_month_closes_2026-11-21.json"
OUTPUT = ROOT / "aics_24_month_no_multiplier_coverage_2026-11-21.json"
Q = Decimal("0.01")
NAMES = frozenset(WEIGHTS)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def d(x):
    if isinstance(x, bool):
        raise ValueError("Boolean may not be a financial observation")
    y = Decimal(str(x))
    if not y.is_finite():
        raise ValueError("Nonfinite financial observation")
    return y


def round2(x):
    return d(x).quantize(Q, rounding=ROUND_HALF_UP)


def gap(cfo, cash_purchases):
    cfo, cash_purchases = d(cfo), d(cash_purchases)
    if cash_purchases <= 0:
        raise ValueError("Non-positive cash investments")
    return round2(max(0, min(100, 100 * (1 - cfo / cash_purchases))))


def breadth(a, b):
    if a.keys() != b.keys() or set(a) != {"ARCC", "BXSL", "OBDC"}:
        raise ValueError("Incorrect BDC panel")
    return round2(d(100) * sum(b[n] > a[n] for n in a) / 3)


def percentile_last_24(values):
    if len(values) != 24:
        raise ValueError("Percentile requires 23 antecedent observed months")
    latest = d(values[-1])
    earlier = [d(v) for v in values[:-1]]
    return round2(100 * (sum(v < latest for v in earlier) +
                         d("0.5") * sum(v == latest for v in earlier)) / 23)


def _month_end(yyyy_mm):
    y, m = map(int, yyyy_mm.split("-"))
    return dt.date(y, m, calendar.monthrange(y, m)[1])


def _check_monotone_rows(rows):
    months = [row["month"] for row in rows]
    if months != [
        f"{year}-{month:02d}"
        for year in (2024, 2025, 2026)
        for month in range(1, 13)
        if (year, month) >= (2024, 11) and (year, month) <= (2026, 10)
    ]:
        raise ValueError("Must contain the exact 24 consecutive elapsed months")


def candidates():
    """Return timestamped, source-defined research events, never a filled row."""
    events = []

    def add(node, available, score, src, measurement, note=""):
        date = dt.date.fromisoformat(available)
        score = round2(score)
        if node not in NAMES or not 0 <= score <= 100:
            raise ValueError("Invalid research event or score")
        events.append({
            "node": node, "available_at": date.isoformat(),
            "score": str(score), "source": str(src), "measurement": measurement,
            "note": note,
            "independently_attested_historical_pit": False,
            "independently_24month_oos_verified": False
        })

    # Six Prudential original SEC 10-Q quarter-end credit facts: the same
    # narrowly scoped no-related-ACL nonaccrual ratio as the November research
    # score. SEC filed_at+14, never retrodict missing 2024 quarters or 2025 Q4.
    for pru in pru_insurers_quarters():
        add("Insurers",pru["available_at"],pru["score"],
            ROOT / "pru_insurers_nonaccrual_original_quarters_2025_2026.json",
            pru["quarter"] + " same-scope PRU no-ACL nonaccrual ratio",
            "Insurer single-issuer proxy; not AI-specific, original bytes not independently rehashed")

    # Original preliminary Oct 2024 observation, first publicly issued on
    # 2024-11-15. This is eligible for the Nov 2024 month-end information
    # set, NOT October 2024 and not a manufactured November observation.
    first = g17_initial_publication()
    add("Semiconductors Supply",first["available_at"],first["score"],
        ROOT / "fed_g17_naics3344_oct2024_first_release_2026-11-21.json",
        "2024-10 initial Fed G.17 NAICS 3344 preliminary (released Nov 15)",
        "First-published Fed date; original bytes not independently archived, research only")

    # Dated original monthly Fed G.17 preliminary observations; first-publication
    # delayed until Dec 2025 for 2025 Sep/Oct/Nov, never use as of the
    # economic observation's month-end. Not a contemporary raw receipt.
    for fed in g17_naics3344_first_releases():
        add("Semiconductors Supply",fed["available_at"],fed["score"],
            ROOT / "fed_g17_naics3344_24_month_original_release_2026-11-21.json",
            fed["observation_month"]+" first-published Fed G.17 NAICS 3344 utilization",
            "Federal Reserve official dated release; source bytes not independently archived, indicator includes other electronic components")

    # Three actual contemporaneous 2025 original-SEC reporting quarters:
    # Q1 group perimeter differs from later continuing operations, and
    # historical provider delivery has not been independently PIT-attested.
    for old in neocloud_2025_original_sec():
        add("Neoclouds", old["available_at"], old["score"],
            ROOT / "neoclouds_2025_q1_q3_sec_cashflow_research_2026-11-21.json",
            old["period"] + " original 2025 SEC two-issuer cash-funding gap",
            old["scope_warning"])

    # Original Q4 2025 SEC EX-99.1 direct quarterly cashflows, never FY
    # annual numbers masquerading as a dated Q4 observation. Joint earliest
    # score as-of 2026-03-12 after both issuer +14 day gates.
    q4 = neocloud_2025_q4_sec()
    add("Neoclouds",q4["available_at"],q4["score"],
        ROOT / "neoclouds_2025_q4_sec_original_cashflow_2026-11-21.json",
        "2025-Q4 original SEC exhibit cashflow shortfall, CoreWeave plus Nebius",
        q4["scope_warning"])

    neo_path = ROOT / "neocloud_cash_coverage_2026_h1.json"
    neo = load(neo_path)
    observations = neo["observations"]
    for q in ("2026-Q1", "2026-Q2"):
        rows = [x for x in observations if x["period"] == q]
        if len(rows) != 2 or {r["issuer"] for r in rows} != {"CoreWeave", "Nebius"}:
            raise ValueError("Missing two neocloud issuers")
        all_available = max(r["all_cited_checks_available"] for r in rows)
        s = gap(sum(d(r["operating_cash_flow"]) for r in rows),
                sum(d(r["cash_purchases"]) for r in rows))
        add("Neoclouds", all_available, s, neo_path, q + " two-issuer cash-funding gap",
            "Quarterly cash-purchase scope differs between issuers; no historical provider PIT certification")

    bdc_path = ROOT / "private_credit_3bdc_3quarter_22values_2026-11-19.json"
    bdc = load(bdc_path)["three_issuer_quarter_comparison"]
    bdc_by = {row["period_end"]: row for row in bdc}
    if set(bdc_by) != {"2026-03-31", "2026-06-30", "2026-09-30"}:
        raise ValueError("Expected actual three-quarter BDC panel")
    for prev, curr in (("2026-03-31", "2026-06-30"),
                       ("2026-06-30", "2026-09-30")):
        old, now = bdc_by[prev], bdc_by[curr]
        def panel(entry):
            return {r["issuer"]: d(r["nonaccrual_amortized_cost_pct"])
                    for r in entry["issuer_rows"]}
        start, end = panel(old), panel(now)
        all_available = max(r["available_at"] for r in now["issuer_rows"])
        if all_available != now["all_three_sec_available_at"]:
            raise ValueError("Issuer gate mismatch")
        add("Private Credit", all_available, breadth(start, end), bdc_path,
            "Breadth of rising nonaccrual across three BDCs, " + curr,
            "No portfolio representativeness claim; never substitute fair-value percentages")

    hyp_q2_path = ROOT / "hyperscalers_cash_coverage_june_to_september_2026.json"
    hyp_q3_path = ROOT / "hyperscalers_operating_cash_flow_coverage_2026_q3.json"
    q2 = load(hyp_q2_path)
    q3 = load(hyp_q3_path)
    if (q2.get("quarter_end") != "2026-06-30"
            or q3.get("quarter_ends")[-1] != "2026-09-30"
            or {r["issuer"] for r in q2["rows"]} !=
            {"Microsoft", "Amazon", "Alphabet", "Meta"}
            or {r["issuer"] for r in q3["rows"]} !=
            {"Microsoft", "Amazon", "Alphabet", "Meta"}):
        raise ValueError("Hyperscaler panel incomplete")
    add("Hyperscalers", max(r["available_at"] for r in q2["rows"]),
        gap(q2["ocf"], q2["ppe"]), hyp_q2_path,
        "2026-Q2 four-issuer total cash funding shortfall")
    current = q3["totals"]["current"]
    add("Hyperscalers", max(r["available_at"] for r in q3["rows"]),
        gap(current["operating_cash_flow"], current["cash_ppe"]),
        hyp_q3_path, "2026-Q3 four-issuer total cash funding shortfall")

    facilities = neo["coreweave_facilities"]
    if (facilities["as_of"] != "2026-06-30"
            or {r["facility"] for r in facilities["facilities"]} !=
            {"DDTL 4.0", "DDTL 5.0"}):
        raise ValueError("Unexpected SPV borrower or facility period")
    loans = facilities["facilities"]
    debt = sum(d(r["reported_debt_usd_m"]) for r in loans)
    ceiling = sum(d(r["facility_ceiling_usd_m"]) for r in loans)
    if not 0 <= debt <= ceiling:
        raise ValueError("SPV debt cannot exceed valid referenced ceilings")
    add("SPV", facilities["available_at"], 100 * debt / ceiling, neo_path,
        "2026-Q2 two reported DDTL facilities, debt divided by ceiling")

    demand_path = ROOT / "broadcom_ai_semiconductor_revenue_2026_q2_q3.json"
    prev, now = load(demand_path)["records"]
    for x in (prev, now):
        if (dt.date.fromisoformat(x["filed_at"]) + dt.timedelta(days=14)).isoformat() != x["available_at"]:
            raise ValueError("Broadcom SEC+14 gate missing")
    add("AI Demand", now["available_at"],
        max(0, 100 * (1 - d(now["actual"]) / d(prev["next_quarter_guidance"]))),
        demand_path, "2026-Q3 Broadcom AI semiconductor revenue versus earlier Q2 guidance")

    power_path = ROOT / "applied_digital_polaris_capacity_2026-10-02.json"
    power = load(power_path)
    if (power["contracted_full_buildout_mw"] <= power["operating_mw"]
            or power["contracted_full_buildout_mw"] != 400):
        raise ValueError("Unexpected site capacity denominators")
    add("Power/Data Centers", power["released_on"],
        100 * (1 - d(power["operating_mw"]) / d(power["contracted_full_buildout_mw"])),
        power_path, "Polaris Forge 1 operational share versus contracted buildout",
        "Site-level proxy, not an industry-wide power stress score")

    ust_path = ROOT / "ust30_yield_change_volatility_2024_2026.json"
    repo_path = ROOT / "repo_24_month_observed_research_2026-11-18.json"
    ust = load(ust_path)["months"]
    repo = load(repo_path)["monthly_observations"]
    if (len(ust) != 24 or len(repo) != 24
            or any(a["as_of"] != b["as_of"] for a, b in zip(ust, repo))
            or ust[-1]["as_of"] != "2026-10-31"):
        raise ValueError("24 authentic matched monthly macro records required")
    add("UST 30Y", ust[-1]["as_of"],
        percentile_last_24([r["sample_sd_daily_change_bp"] for r in ust]),
        ust_path, "October 2026 percentile of 20-change Treasury 30Y yield volatility",
        "Retrospective ALFRED archive: contemporary provider source-release proof not certified")
    last_repo = repo[-1]
    if (last_repo["publication_proxy_date"] > last_repo["as_of"]):
        raise ValueError("Repo current month publication proxy late")
    add("Repo", last_repo["as_of"],
        percentile_last_24([r["sofr_minus_iorb_bps"] for r in repo]),
        repo_path, "October 2026 SOFR-IORB spread against 23 prior months",
        "NY Fed publication date is only a proxy; original 24-month source PIT not attested")
    return sorted(events, key=lambda e: (e["available_at"], e["node"]))


def build():
    sp = load(SP500)
    if (sp.get("schema") != "aics-sp500-24-month-observed-price-source-v1"
            or sp.get("independent_pit_verified") is not False
            or len(sp["points"]) != 24 or sum(WEIGHTS.values()) != 1050):
        raise ValueError("Invalid 24-point benchmark or node weights")
    _check_monotone_rows(sp["points"])
    ust = load(ROOT / "ust30_yield_change_volatility_2024_2026.json")["months"]
    repo = load(ROOT / "repo_24_month_observed_research_2026-11-18.json")["monthly_observations"]
    events = candidates()
    last_known = {}
    event_idx = 0
    monthly = []
    first_close = d(sp["points"][0]["sp500_month_end_close"])
    for idx, row in enumerate(sp["points"]):
        month, cutoff = row["month"], _month_end(row["month"])
        macro_u, macro_r = ust[idx], repo[idx]
        if macro_u["as_of"] != cutoff.isoformat() or macro_r["as_of"] != cutoff.isoformat():
            raise ValueError("Macro and S&P 500 monthly calendar misaligned")
        if (macro_u["last_yield_date"] > cutoff.isoformat()
                or macro_r["publication_proxy_date"] > cutoff.isoformat()):
            raise ValueError("Look-ahead on monthly raw macro observation")
        fresh = []
        while event_idx < len(events) and events[event_idx]["available_at"] <= cutoff.isoformat():
            item = events[event_idx]
            last_known[item["node"]] = item
            fresh.append(item["node"])
            event_idx += 1
        score_nodes = {
            node: {"score": item["score"], "source_available_at": item["available_at"],
                   "carried_from_prior_month": item["available_at"][:7] != month}
            for node, item in sorted(last_known.items())
        }
        count = len(score_nodes)
        partial = sum((d(WEIGHTS[n]) * d(x["score"]) / 100 for n, x in score_nodes.items()), d(0))
        sp500 = d(row["sp500_month_end_close"])
        monthly.append({
            "month": month,
            "as_of": cutoff.isoformat(),
            "sp500_last_session_close": str(sp500),
            "sp500_normalized_nov_2024_100": str((100 * sp500 / first_close).quantize(Decimal("0.0001"))),
            "ust30_20_change_volatility_bp": macro_u["sample_sd_daily_change_bp"],
            "repo_sofr_minus_iorb_bp": macro_r["sofr_minus_iorb_bps"],
            "known_node_count_research_only": count,
            "missing_nodes": sorted(NAMES - set(score_nodes)),
            "new_node_events_in_month": fresh,
            "latest_eligible_research_scores": score_nodes,
            "partial_known_weighted_points_not_aics": str(partial.quantize(Q, rounding=ROUND_HALF_UP)) if count else None,
            "full_11_node_aics_no_multiplier": None,
            "aics_sp500_normalized_spread": None,
            "independent_historical_pit_confirmed": False,
        })
    if len(monthly) != 24 or any(m["full_11_node_aics_no_multiplier"] is not None for m in monthly):
        raise ValueError("Invalid completed-month historical coverage")
    return {
        "schema": "aics-24-month-source-gated-no-multiplier-coverage-v1",
        "window": ["2024-11", "2026-10"],
        "month_count": 24,
        "score_method": "UNMULTIPLIED_SUM_WEIGHT_X_SCORE_OVER_100",
        "node_weights_total": 1050,
        "sp500_source": sp["source_url"],
        "new_11_node_full_aics_months": 0,
        "new_11_node_sp500_spread_months": 0,
        "source_validation": "RETROSPECTIVE_RESEARCH_ONLY_NOT_HISTORICAL_PIT_OR_24M_OOS",
        "scores_at_first_release_only_not_backfilled": True,
        "asof_carry_semantics": "Only move known scores forward after their dated source eligibility; never infer a value for an earlier month. Carried source date remains visible.",
        "original_observation_months": {"sp500":24, "ust30":24, "repo":24},
        "score_source_events": events,
        "monthly": monthly,
        "certified_aics": None,
        "production_formula_changed": False,
        "trades_created": False,
    }


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, ensure_ascii=False))
