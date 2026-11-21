"""AICS core mission: distinguish 2000-style buildout bust from 2008 funding contagion.

A historical *mechanism* map and falsifiable, date-based outcome benchmark.
Not a numeric 2000-vs-2008 similarity classifier: we do not have a comparable,
PIT-attested 1998-2002 / 2005-2009 11-node AICS history. Never assign
invented historical scores or training labels, and never interpret a
pre-WorldCom / pre-Lehman observation as necessarily pre-crisis onset.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS

V18=Path("aics_data/research/aics_v18_private_credit_24m_pit_proxy_overlay_2026-11-22.json")
OUT=Path("aics_data/agent_runs/aics_2000_2008_2026_analog_research.json")

# Descriptive historical categories are grounded in public Federal Reserve,
# FRBSF/Richmond and NYFed work. They are NOT historic 0-100 AICS scores.
ANCHORS={
    "telecom2000":{
        "market_bubble_peak":"2000-03-10",  # Nasdaq; Fed 2000-03-21 greenbook
        "first_crisis_event":"2000-03-10",
        "first_crisis_event_definition":"Nasdaq composite peak; subsequent dotcom unwind",
        "later_high_profile_failure":"2002-07-21",
        "later_high_profile_event":"WorldCom Chapter 11",
        "claimed_old_aics_crossing_window":["2000-10-01","2000-12-31"],
        "source_urls":[
            "https://www.federalreserve.gov/monetarypolicy/files/fomc20000321gbpt220000315.pdf",
            "https://fraser.stlouisfed.org/title/economic-quarterly-federal-reserve-bank-richmond-960/fall-2003-477419/fulltext",
            "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-18451",
        ],
        "signature":"Overbuilt telecom networks/fiber, customer demand below investment expectations, falling equipment values, exposed corporate debt and defaults",
    },
    "subprime2008":{
        "market_bubble_peak":"2006-12-31",  # proxy YEAR only, NOT exact house-price peak
        "first_crisis_event":"2007-08-09",
        "first_crisis_event_definition":"Documented money-market liquidity squeeze, after earlier 2007 subprime distress",
        "later_high_profile_failure":"2008-09-15",
        "later_high_profile_event":"Lehman bankruptcy",
        "claimed_old_aics_crossing_window":["2007-10-01","2007-12-31"],
        "source_urls":[
            "https://www.federalreserve.gov/monetarypolicy/mpr_20090224_part2.htm",
            "https://www.federalreserve.gov/newsevents/speech/bernanke20120413a.htm",
            "https://www.federalreserve.gov/newsevents/speech/yellen20170825a.htm",
        ],
        "signature":"Collateral leverage and opaque structured exposures propagated through repo, bank/nonbank wholesale funding and liquidity runs",
    },
}
AXES=(
    ("capacity_overinvestment",("Hyperscalers","Neoclouds","Power/Data Centers"),
      "Core in telecom 2000", "Different asset (housing), not primary telecom capex", "AI capex versus independently paid utilization"),
    ("realized_demand_vs_promised",("AI Demand","Hyperscalers"),
      "Core: expected network demand vs realized cash receipts", "Core: debt-service cash flows below mortgage expectations", "Collectible external AI demand / revenue and contract cancellations"),
    ("collateral_residual_value",("Semiconductors Supply","Neoclouds","SPV"),
      "Overbuilt fiber/network residual values", "House/MBS collateral revaluations and haircuts", "Original GPU resale auction prices, liquidation values and age vintages"),
    ("debt_refinancing_maturity",("Private Credit","Neoclouds","UST 30Y"),
      "Corporate telecom leverage and refinancing", "Mortgage/structured-credit rollover", "Signed debt maturity ladders and source-specific refinancing spreads"),
    ("hidden_leverage_structured_vehicles",("SPV","Private Credit","Hyperscalers"),
      "Corporate balance-sheet/lease debt, not central repo run", "SIV/ABCP/off-balance funding amplification", "Issuer-level SPV recourse, guarantees, direct owner and holders"),
    ("cross_institution_contagion",("Private Credit","Insurers","SPV"),
      "Creditor defaults, corporate-credit losses", "Bank/nonbank/insurer credit exposure and counterparty transmission", "Verified borrower-lender-insurer exposure matrix and insurer look-through"),
    ("wholesale_liquidity_run",("Repo","UST 30Y","Private Credit"),
      "Not the defining market-wide short-term funding mechanism", "Central: repo/collateral haircuts/money-market run", "Contemporaneous SOFR-IORB, repo haircuts, fund outflows and bid fails"),
    ("equity_concentration_crowding",("AI Equities","AI Demand"),
      "Tech/equity overvaluation and reversal", "Financial-sector stock losses and forced deleveraging", "Pre-fixed AI equity basket, valuations, market leverage and changes"),
)
ORIGINAL_REPORTS=[
    {"title":"БКС Ультима · Системный риск цепочки ИИ-финансирования",
     "pages":[2,3,4,5,6,9,10,11,12,13],
     "role":"2026 research thesis, NOT raw 2000/2008 backtest evidence",
     "claim":"Old 9-node candidate 463/1000; historical >500 crossings 2000Q4 / 2007Q4 not reproducibly PIT certified",
     "old_index_scale":1000},
    {"title":"Brace for Impact · Matthew Scherer & Maya Jenkins (Oct 2026)",
     "pages":[6,9,24,30,33,36,41,42,43,47],
     "role":"Secondary directed contagion hypotheses, NOT attested current exposures",
     "sha256":"466b8a875752c85e23a41d5e33ad985c44f437ddc5cf801e132310c4e28bff60"},
]
KEY_REQUIRED_DATA={
    "2000": ["historical dated telecom capex/sales by issuer","fiber utilization and overcapacity",
             "issuer-corporate debt maturities and defaults","point-in-time market peak and market falls"],
    "2008": ["historical ABCP and repo haircuts by date","dealer/bank/NBFI leverage",
             "original MBS collateral loss and bank holding exposure","first liquidity distress event definitions"],
    "2026": ["verified public company AI-specific revenue versus cash capex",
             "dated contractual SPV recourse and maturity schedules",
             "power-ready MW and GPU vintage resale value",
             "independent lender/insurer exposure graph",
             "PIT-frozen AI equity basket and vintage-correct wholesale funding observations"],
}


def _d(v):
    return dt.date.fromisoformat(v)


def timing(anchor):
    first, last=[_d(v) for v in anchor["claimed_old_aics_crossing_window"]]
    onset=_d(anchor["first_crisis_event"])
    later=_d(anchor["later_high_profile_failure"])
    if not first<=last<later or not onset<later:
        raise ValueError("Historical event chronology invalid")
    if first>onset:
        onset_status="OLD_CROSSING_AFTER_OBSERVED_CRISIS_ONSET"
    elif last<onset:
        onset_status="OLD_CROSSING_BEFORE_OBSERVED_CRISIS_ONSET"
    else:
        onset_status="ONSET_AND_CROSSING_OVERLAP_UNCERTAIN"
    return {
        "first_market_or_funding_crisis_date":onset.isoformat(),
        "later_high_profile_failure_date":later.isoformat(),
        "old_report_crossing_window":[first.isoformat(),last.isoformat()],
        "early_warning_of_crisis_onset_status":onset_status,
        "earliest_possible_lead_to_later_failure_days":(later-last).days,
        "latest_possible_lead_to_later_failure_days":(later-first).days,
        "old_report_historic_crossing_independently_reproduced":False,
        "actual_unlookahead_timing_skill_verified":False,
    }


def build(v18):
    if (v18.get("schema") != "aics-v18-24m-private-credit-original-sec-expost-research-overlay-v1"
        or v18.get("scores_are_expost_not_preregistered") is not True
        or v18.get("historical_pit_source_bytes_independently_attested") is not False
        or v18.get("full_11node_index_months") != 0
        or v18.get("aics_sp500_spread_months") != 0
        or v18.get("production_index_changed") is not False
        or len(v18.get("monthly_last_weekday_market_proxy",[])) != 24
        or sum(WEIGHTS.values()) != 1050):
        raise ValueError("Cannot use certified/fabricated 2026 research index")
    latest=v18["monthly_last_weekday_market_proxy"][-1]
    if (latest["month"]!="2026-10" or latest["cutoff_date"]!="2026-10-30"
        or latest["known_weight"]!=725
        or latest["partial_weighted_points_not_full_aics"]!="268.39"
        or latest["full_aics"] is not None
        or latest["aics_sp500_spread"] is not None
        or latest["historical_pit_certified"] is not False
        or set(latest["node_scores"])|set(latest["missing_nodes"])!=set(WEIGHTS)):
        raise ValueError("Unexpected October 2026 honest market-close cutoff")
    for node,data in latest["node_scores"].items():
        score=float(data["score"])
        if not 0<=score<=100 or _d(data["research_eligible_date"])>_d(latest["cutoff_date"]):
            raise ValueError("Unverified or future source point")
    axes=[]
    for axis,nodes,m2000,m2008,required in AXES:
        candidates={n:{"score_0_100_research_candidate":latest["node_scores"][n]["score"],
                        "research_source_eligible_at":latest["node_scores"][n]["research_eligible_date"],
                        "historical_delivery_pit_attested":False}
                    for n in nodes if n in latest["node_scores"]}
        missing=[n for n in nodes if n not in latest["node_scores"]]
        axes.append({
            "axis":axis,
            "2000_known_failure_mechanism":m2000,
            "2008_known_failure_mechanism":m2008,
            "current_2026_asof_marketclose_node_candidates":candidates,
            "missing_2026_proxy_nodes":missing,
            "required_to_prove_economic_mechanism":required,
            "historically_comparable_unbiased_numeric_2000_2008_metric":None,
            "historical_source_matched_by_definition":False,
            "contemporaneous_2026_economic_mechanism_independently_verified":False,
            "axis_2000_vs_2026_similarity_score":None,
            "axis_2008_vs_2026_similarity_score":None,
        })
    base={key:{"signature":a["signature"],
               "primary_historical_sources":a["source_urls"],
               "source_dates_are_historical_not_data_provider_vintages":True,
               "historical_index_reproduction_status":"NOT_RECONSTRUCTED",
               "timing_audit":timing(a)}
          for key,a in ANCHORS.items()}
    return {
        "schema":"aics-2026-vs-2000-2008-historical-mechanisms-and-timing-v1",
        "research_asof":"2026-11-22",
        "current_2026_source_month":latest["month"],
        "current_price_close_cutoff":latest["cutoff_date"],
        "old_report_index_9node_scale_1000_incommensurate_with_11node_1050":True,
        "new_11node_weights_total":1050,
        "2026_research_observed_candidate_nodes":len(latest["node_scores"]),
        "2026_missing_market_close_nodes":latest["missing_nodes"],
        "2026_partial_known_weighted_points_not_full_index":latest["partial_weighted_points_not_full_aics"],
        "2026_current_crisis_events_proven_by_scores":False,
        "comparison_eras":base,
        "feature_axis_count":len(axes),"feature_axes":axes,
        "historical_reconstruction_plan":KEY_REQUIRED_DATA,
        "original_secondary_reports":ORIGINAL_REPORTS,
        "non_lookahead_narrative_research_hypotheses":[
            "Telecom-2000-type physical buildout and demand monetization overshoot",
            "Subprime-2008-type hidden leverage, structured finance and short-term funding contagion",
            "Mixed regime possible: real asset overbuild can transmit to shadow bank funding without a literal repetition",
        ],
        "main_hypothesis_not_pre_selected":True,
        "quantitative_similarity_percent_2000":None,
        "quantitative_similarity_percent_2008":None,
        "verified_precrisis_index_lead_time":None,
        "prediction_confidence_or_crisis_probability":None,
        "historical_2000_2008_node_scores":None,
        "independent_24month_OOS_backtest":False,
        "AI_equities_proxy_source_eligible_oct30":False,
        "repo_absence_does_not_mean_funding_is_calm":True,
        "full_AICS":None,
        "score_weights_modified":False,
        "trades_created":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=OUT)
    args=p.parse_args()
    model=build(json.loads(V18.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(model,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "axes":model["feature_axis_count"],
        "historical_2000_crossing_onset":model["comparison_eras"]["telecom2000"]["timing_audit"]["early_warning_of_crisis_onset_status"],
        "historical_2008_crossing_onset":model["comparison_eras"]["subprime2008"]["timing_audit"]["early_warning_of_crisis_onset_status"],
        "2026_observed_marketclose_nodes":model["2026_research_observed_candidate_nodes"],
        "2000_similarity":None,"2008_similarity":None,"new_trades":False,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
