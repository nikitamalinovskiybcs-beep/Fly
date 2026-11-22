"""Reconcile both independent AICS PIT100 24-month replays and align S&P500.

Never equate a source candidate partial weighted score with an approved AICS
index. Month-close S&P values are ex-post market context, not outcomes in
the node scoring function. No claim of independent historical PIT or OOS.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_pit100_rebuild_24m_research import OUT as SIMPLE,read_bytes,num
from scripts.aics_pit100_rebuild_24_month_public_filing_panel import OUT as RICH,SP500

ROOT=Path("aics_data/agent_runs/ten_real_collection_rounds")
OUT=ROOT/"aics_pit100_reconciled_24m_sp500_monthly.json"
CSV=ROOT/"aics_pit100_reconciled_24m_sp500_monthly.csv"
MARKDOWN=ROOT/"aics_pit100_reconciled_24m_sp500_monthly.md"


def quant(x):
    return str(num(x).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))


def reconcile(simple,rich,sp500):
    if (simple.get("schema")!="aics-pit100-24m-public-filing-day-rebuilt-research-v1"
        or rich.get("schema")!="aics-24month-public-filing-date-PIT100-rebuilt-candidate-panel-v1"
        or simple.get("historical_months")!=24
        or simple.get("source_replay_count")!=100
        or rich.get("source_events_recomputed_from_unchanged_original_ledgers")!=64
        or rich.get("original_PIT100_roles_individually_verified_against_rebuild")!=100
        or not simple.get("active_SEC_public_filing_date_no_14day_delay")
        or rich.get("SEC_14day_artificial_delay_active") is not False
        or rich.get("full_11node_AICS") is not None
        or simple.get("fully_rebuilt_production_AICS") is not None
        or rich.get("aics_sp500_spread") is not None
        or simple.get("AICS_SP500_spread") is not None
        or rich.get("independently_historical_PIT_first_delivery_certified") is not False
        or rich.get("24month_independent_OOS_skill") is not None
        or simple.get("24month_independent_OOS") is not False
        or sp500.get("schema")!="aics-sp500-24-month-observed-price-source-v1"
        or sp500.get("independent_pit_verified") is not False
        or len(sp500.get("points",[]))!=24
        or sum(WEIGHTS.values())!=1050):
        raise ValueError("Unverified or falsified PIT100 inputs")
    a_conflicts=simple.get("quarantined_same_day_research_conflicts",[])
    b_conflicts=rich.get("same_day_ambiguous_release_conflicts_quarantined",[])
    if a_conflicts or b_conflicts:
        raise ValueError("Original joint G17 release is two periods, not conflicting dates")
    a_joint=simple.get("same_day_joint_observation_months",{})
    b_joint=rich.get("same_day_joint_different_observation_periods_validated",{})
    expected={"2025-10":Decimal("74.7"),"2025-11":Decimal("74.4")}
    if (a_joint.get("publication_day")!="2025-12-23"
        or b_joint.get("original_release_date")!="2025-12-23"
        or a_joint.get("original_official_Fed_release_url")!=
           b_joint.get("original_official_federal_reserve_release_url")
        or {e["observation_month"]:num(e["value"])
            for e in a_joint.get("observation_period_values",[])}!=expected
        or {e["observation_month"]:num(e["value"])
            for e in b_joint.get("source_observation_values",[])}!=expected
        or a_joint.get("both_values_distinct_periods_no_source_quarantine") is not True
        or b_joint.get("separate_measurement_months_not_duplicate_release_data") is not True
        or a_joint.get("independent_historical_first_feed_receipt") is not False
        or b_joint.get("independent_original_first_delivery_timestamp_attested") is not False):
        raise ValueError("Original 2025-12-23 G17 Oct/Nov joint release not reconciled")
    all_months=[]
    method_differences=[]
    for mode in ("market","calendar"):
        simple_rows=simple[f"{mode}_monthly_rebuilt"]
        rich_rows=rich["monthly_rebuilt_panels"][mode]
        if len(simple_rows)!=24 or len(rich_rows)!=24:
            raise ValueError("Missing 24 monthly research observations")
        for a,b in zip(simple_rows,rich_rows):
            if (a["month"]!=b["month"]
                or a["cutoff_date"]!=b["cutoff_date"]
                or a["historical_PIT_certified"] is not False
                or b["source_pit_independently_certified"] is not False
                or a["full_11node_AICS"] is not None
                or b["full_11_node_AICS"] is not None
                or a["AICS_SP500_spread"] is not None
                or b["S&P500_index_spread"] is not None):
                raise ValueError("Monthly chronology, index status or PIT flag mismatch")
            aa=a["node_scores_rebuilt_from_original_events"]
            bb=b["event_source_scores"]
            if set(aa)!=set(bb) or sorted(a["missing_nodes"])!=sorted(b["missing_nodes"]):
                raise ValueError(f"Different issuer/node coverage between two replays: {mode} {a['month']}")
            for n in aa:
                if (num(aa[n]["research_score_not_PIT_certified"])!=num(bb[n]["score_0_100_research_only"])
                    or aa[n]["source_filing_or_release_date"]!=bb[n]["source_public_day_proxy"]
                    or aa[n]["historical_first_delivery_attested"] is not False
                    or bb[n]["publication_time_and_historical_receipt_not_independently_verified"] is not True):
                    method_differences.append({"mode":mode,"month":a["month"],"node":n})
            if (a["known_weight_research_only"]!=b["date_only_known_weight"]
                or quant(a["research_partial_weighted_points_not_full_AICS"])!=
                   quant(b["date_only_partial_points_not_full_AICS"])):
                raise ValueError(f"Different weight or candidate partial points: {mode} {a['month']}")
            if method_differences:
                raise ValueError(f"Unreconciled original source scores: {method_differences[:5]}")
    old={}
    bymode={}
    for mode in ("market","calendar"):
        bymode[mode]={
            row["month"]:row
            for row in rich["monthly_rebuilt_panels"][mode]
        }
    previous=None
    for i,sp in enumerate(sp500["points"]):
        month=sp["month"]
        market=bymode["market"].get(month)
        calendar=bymode["calendar"].get(month)
        if not market or not calendar:
            raise ValueError("Missing matched observed S&P month in 24-month panel")
        close=num(sp["sp500_month_end_close"])
        if close<=0:raise ValueError("Nonpositive recorded S&P price")
        same=market["SP500_monthly_context_not_AICS_spread"]
        reported=same["same_month_return_from_previous_observed_close_pct"]
        expected=quant((close/previous-1)*100) if previous is not None else None
        if (same["month_end_observed_close_retrieved_expost"]!=sp["sp500_month_end_close"]
            or reported!=expected):
            raise ValueError("S&P closing price/monthly return does not reconcile")
        row={
            "month":month,
            "market_cutoff_date":market["cutoff_date"],
            "calendar_cutoff_date":calendar["cutoff_date"],
            "market_source_nodes_research_only":market["date_only_research_nodes"],
            "calendar_source_nodes_research_only":calendar["date_only_research_nodes"],
            "market_known_weight_research_only":market["date_only_known_weight"],
            "calendar_known_weight_research_only":calendar["date_only_known_weight"],
            "market_weight_coverage_pct_research_only":
                quant(100*num(market["date_only_known_weight"])/1050),
            "calendar_weight_coverage_pct_research_only":
                quant(100*num(calendar["date_only_known_weight"])/1050),
            "market_partial_weighted_points_NOT_AICS":market["date_only_partial_points_not_full_AICS"],
            "calendar_partial_weighted_points_NOT_AICS":calendar["date_only_partial_points_not_full_AICS"],
            "market_fresh_90day_weight":market["fresh_90d_known_weight"],
            "calendar_fresh_90day_weight":calendar["fresh_90d_known_weight"],
            "market_missing_nodes":market["missing_nodes"],
            "calendar_missing_nodes":calendar["missing_nodes"],
            "sp500_close_retrieved_expost":str(close),
            "sp500_same_month_return_pct_retrieved_expost":reported,
            "full_11node_AICS":None,
            "AICS_SP500_spread":None,
            "certified_pit_market_signal":False,
            "independent_walkforward_test":False,
        }
        all_months.append(row)
        previous=close
    if len(all_months)!=24 or len({x["month"] for x in all_months})!=24:
        raise ValueError("Not 24 genuinely aligned monthly rows")
    summary={}
    for mode in ("market","calendar"):
        rows=rich["monthly_rebuilt_panels"][mode]
        summary[mode]={
            "reconciled_months":24,
            "coverage_weight_months":sum(x["date_only_known_weight"] for x in rows),
            "research_coverage_pct":quant(
                100*sum(num(x["date_only_known_weight"]) for x in rows)/(1050*24)),
            "fresh_90d_coverage_pct":rich["baseline_vs_rebuilt_quality_metrics"][mode]["fresh_90d_research_coverage_pct"],
            "months_with_changed_research_partial_points_vs_legacy":
                sum(num(x["difference_in_dateonly_partial_points"])!=0 for x in rows),
            "last_month_known_weight":rows[-1]["date_only_known_weight"],
            "last_month_missing_nodes":rows[-1]["missing_nodes"],
            "last_month_partial_research_points_not_AICS":
                rows[-1]["date_only_partial_points_not_full_AICS"],
        }
    dec_row=next(x for x in all_months if x["month"]=="2025-12")
    if (num(bymode["market"]["2025-12"]["event_source_scores"]["Semiconductors Supply"]["score_0_100_research_only"])!=
        Decimal("74.40")):
        raise ValueError("Latest Nov-2025 measurement in joint G17 release must be visible at Dec month-end")
    return {
        "schema":"aics-pit100-two-independent-24month-replays-reconciled-v1",
        "as_of":rich["as_of"],
        "research_months_reconciled":24,
        "independent_replay_methods_compared":2,
        "month_node_disagreements_remaining":len(method_differences),
        "validated_joint_G17_original_release":{
            "market_month":"2025-12",
            "official_publication_date":"2025-12-23",
            "official_release_url":b_joint["original_official_federal_reserve_release_url"],
            "observation_months":["2025-10","2025-11"],
            "values":["74.70","74.40"],
            "latest_research_monthly_candidate":"74.40",
            "separate_original_measurements_not_conflicting_publications":True,
            "historical_original_first_provider_feed_receipt_attested":False,
        },
        "G17_research_source_period_conflicts_remaining":0,
        "quality_by_panel":summary,
        "market_vs_calendar_same_day_publication_research_difference_not_bug":True,
        "monthly_aligned_research_panel":all_months,
        "SP500_reference_source":sp500["source_url"],
        "SP500_24m_observed_closes_original_feed_PIT_certified":False,
        "monthly_source_score_formula_preregistered":False,
        "full_11node_AICS":None,
        "AICS_SP500_spread":None,
        "forecast_accuracy_or_2000_2008_similarity_pct":None,
        "independently_certified_historical_PIT_nodes":0,
        "production_model_weights_changed":False,
        "trades_created":False,
    }


def csv_export(data,path):
    cols=["month","market_cutoff_date","calendar_cutoff_date",
          "market_source_nodes_research_only","calendar_source_nodes_research_only",
          "market_known_weight_research_only","calendar_known_weight_research_only",
          "market_weight_coverage_pct_research_only","calendar_weight_coverage_pct_research_only",
          "market_partial_weighted_points_NOT_AICS",
          "calendar_partial_weighted_points_NOT_AICS",
          "market_fresh_90day_weight","calendar_fresh_90day_weight",
          "market_missing_nodes","calendar_missing_nodes",
          "sp500_close_retrieved_expost",
          "sp500_same_month_return_pct_retrieved_expost",
          "full_11node_AICS","AICS_SP500_spread"]
    with path.open("w",newline="",encoding="utf-8") as f:
        wr=csv.DictWriter(f,fieldnames=cols)
        wr.writeheader()
        for r in data["monthly_aligned_research_panel"]:
            wr.writerow({k:(",".join(v) if isinstance(v,list) else
                             "" if v is None else v)
                          for k,v in r.items() if k in cols})


def markdown_report(data):
    a=data["quality_by_panel"]
    rows=data["monthly_aligned_research_panel"]
    out=[
        "# AICS PIT100 — 24 months reconciled against S&P 500",
        "",
        f"**Research as-of:** {data['as_of']}. **100 source-event audits**; two independent source reconstructions now agree on all 24 months and all available research node values.",
        "",
        "**Important:** the partial AICS-like weighted research points are NOT a full 11-node AICS, have NOT been PIT-certified, and must not be compared with entry/exit thresholds. S&P 500 is ex-post price context, never a price-return prediction input.",
        "",
        "| Audit | Market close | Calendar close |",
        "|---|---:|---:|",
        f"| Original-source research coverage, share of fixed weight-months | {a['market']['research_coverage_pct']}% | {a['calendar']['research_coverage_pct']}% |",
        f"| Coverage fresh within 90 days | {a['market']['fresh_90d_coverage_pct']}% | {a['calendar']['fresh_90d_coverage_pct']}% |",
        f"| Known weight in October 2026 (max 1050) | {a['market']['last_month_known_weight']} | {a['calendar']['last_month_known_weight']} |",
        f"| Months with source candidate partial score changed versus legacy | {a['market']['months_with_changed_research_partial_points_vs_legacy']} | {a['calendar']['months_with_changed_research_partial_points_vs_legacy']} |",
        "",
        "## 24 observed months — S&P 500 context and incomplete source research",
        "",
        "| Month | Market observed weight / 1050 | Calendar observed weight / 1050 | Market **partial research points (NOT AICS)** | S&P 500 close | S&P 500 change |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        out.append(
            f"| {r['month']} | {r['market_known_weight_research_only']} | {r['calendar_known_weight_research_only']} | "
            f"{r['market_partial_weighted_points_NOT_AICS']} | "
            f"{r['sp500_close_retrieved_expost']} | "
            f"{r['sp500_same_month_return_pct_retrieved_expost'] if r['sp500_same_month_return_pct_retrieved_expost'] is not None else 'n/a'}% |"
        )
    out+= [
        "",
        "## Official Fed G.17 joint release: two valid measurement months, not a conflict",
        "",
        "Official Federal Reserve archival G.17 released **both October 2025 (74.70)** and **November 2025 (74.40)** NAICS 3344 original capacity-utilization research values **together on 2025-12-23** after a government-shutdown delay. These have different measurement months and must not be treated as contradictory same-observation revisions. At December 2025 month-end the latest preliminary observation is November **74.40** (research only). Original first-feed availability remains unverified; the score is not a validated AI-only semiconductor-supply-stress metric.",
        "",
        "## Remaining blockers",
        "",
        "There are **0 independently PIT-certified historical 11-node AICS months** and **0 independently validated 24-month walk-forward OOS results**. Historical first-byte receipt, SEC acceptance timestamps, ALFRED vintage chain, AI Equities original constituent/corporate-action timeline, and preregistered node score formulas remain open. No AICS-vs-S&P return spread or numerical crisis probability has been fabricated.",
        "",
        "Output includes full aligned source data in JSON and CSV. Both research reconstruction implementations were independently executed and cross-checked against the same unchanged original source ledger; neither is an external independent PIT validator.",
        "",
    ]
    return "\n".join(out)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--simple",type=Path,default=SIMPLE)
    p.add_argument("--rich",type=Path,default=RICH)
    p.add_argument("--sp500",type=Path,default=SP500)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--csv",type=Path,default=CSV)
    p.add_argument("--report",type=Path,default=MARKDOWN)
    args=p.parse_args()
    data=reconcile(*(read_bytes(p) for p in (args.simple,args.rich,args.sp500)))
    data["input_sha256"]={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (args.simple,args.rich,args.sp500)}
    for pth in (args.out,args.csv,args.report):
        pth.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    csv_export(data,args.csv)
    args.report.write_text(markdown_report(data),encoding="utf-8")
    print(json.dumps({
        "months":data["research_months_reconciled"],
        "replays_compared":2,
        "unreconciled_node_months":data["month_node_disagreements_remaining"],
        "market_source_weight_coverage_pct":data["quality_by_panel"]["market"]["research_coverage_pct"],
        "calendar_source_weight_coverage_pct":data["quality_by_panel"]["calendar"]["research_coverage_pct"],
        "full_index":None,"historical_oos":None,"trades":False,
    }))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
