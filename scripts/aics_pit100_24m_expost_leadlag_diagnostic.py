"""AICS 24m lead/lag falsification: fixed first-month source cohort vs S&P500.

Use only the observed original PIT100 source-candidate nodes present in the
FIRST 2024-11 market month. Do not pick survivors using future dates.
Compute only descriptive fixed-cohort scores when all fixed sources exist.
Compare with S&P500 (1) prior->current return and (2) subsequent return,
with 0/11 independently certified nodes. This is retrospective EX-POST
diagnostics, NOT trained forecasts, independent OOS, 2000/2008 crisis
warning, production AICS, trade or entry/exit threshold inference.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_pit100_rebuild_24_month_public_filing_panel import read_bytes

ROOT=Path("aics_data/agent_runs/ten_real_collection_rounds")
RECONCILED=ROOT/"aics_pit100_reconciled_24m_sp500_monthly.json"
RICH=ROOT/"aics_24m_publication_date_rebuilt_research_panel.json"
OUT=ROOT/"aics_pit100_24m_expost_leadlag_falsification.json"
CSV=ROOT/"aics_pit100_24m_expost_leadlag_falsification.csv"


def dec(x):
    if isinstance(x,bool):
        raise ValueError("Invalid market numeric boolean")
    n=Decimal(str(x))
    if not n.is_finite():
        raise ValueError("Non finite research data")
    return n


def pearson(a,b):
    if len(a)!=len(b) or len(a)<6:
        return None
    aa=[float(x) for x in a];bb=[float(x) for x in b]
    av=sum(aa)/len(aa);bv=sum(bb)/len(bb)
    ax=[x-av for x in aa];bx=[x-bv for x in bb]
    den=math.sqrt(sum(x*x for x in ax)*sum(y*y for y in bx))
    if den<=0:return None
    v=sum(x*y for x,y in zip(ax,bx))/den
    if not -1.00001<=v<=1.00001:
        raise ValueError("Invalid correlation")
    return round(max(-1,min(1,v)),4)


def rank(xs):
    ordered=sorted((float(x),i) for i,x in enumerate(xs))
    result=[0.0]*len(xs);idx=0
    while idx<len(xs):
        j=idx+1
        while j<len(xs) and ordered[j][0]==ordered[idx][0]:
            j+=1
        avg=(idx+1+j)/2
        for k in range(idx,j):
            result[ordered[k][1]]=avg
        idx=j
    return result


def compare(reconciled,rich):
    if (reconciled.get("schema")!="aics-pit100-two-independent-24month-replays-reconciled-v1"
        or reconciled.get("research_months_reconciled")!=24
        or reconciled.get("month_node_disagreements_remaining")!=0
        or reconciled.get("full_11node_AICS") is not None
        or reconciled.get("AICS_SP500_spread") is not None
        or reconciled.get("independently_certified_historical_PIT_nodes")!=0
        or rich.get("schema")!="aics-24month-public-filing-date-PIT100-rebuilt-candidate-panel-v1"
        or rich.get("full_11node_AICS") is not None
        or rich.get("independently_historical_PIT_first_delivery_certified") is not False
        or sum(WEIGHTS.values())!=1050):
        raise ValueError("No historically authorized AICS feature/score inference")
    aligned=reconciled["monthly_aligned_research_panel"]
    series=rich["monthly_rebuilt_panels"]["market"]
    if len(aligned)!=24 or len(series)!=24:
        raise ValueError("No 24 observed months")
    if [a["month"] for a in aligned]!=[s["month"] for s in series]:
        raise ValueError("Month alignment wrong")
    initial=series[0]["event_source_scores"]
    cohort=sorted(initial)
    if not cohort or sum(WEIGHTS[x] for x in cohort)<=0:
        raise ValueError("Fixed source cohort missing on initial observed month")
    initial_cohort_weight=sum(WEIGHTS[x] for x in cohort)
    records=[]
    for i,(a,s) in enumerate(zip(aligned,series)):
        if (a["market_cutoff_date"]!=s["cutoff_date"]
            or a["sp500_same_month_return_pct_retrieved_expost"] !=
                s["SP500_monthly_context_not_AICS_spread"]["same_month_return_from_previous_observed_close_pct"]
            or s["source_pit_independently_certified"] is not False):
            raise ValueError("Retrospective return or source date mismatch")
        nodes=s["event_source_scores"]
        cohort_complete=all(n in nodes for n in cohort)
        risk=(sum((dec(nodes[n]["score_0_100_research_only"])*WEIGHTS[n] for n in cohort),
                  Decimal(0))/initial_cohort_weight if cohort_complete else None)
        if risk is not None and not 0<=risk<=100:
            raise ValueError("Invalid candidate fixed cohort source risk")
        now=a["sp500_same_month_return_pct_retrieved_expost"]
        forward=aligned[i+1]["sp500_same_month_return_pct_retrieved_expost"] if i<23 else None
        records.append({
            "month":a["month"],
            "market_cutoff_date":s["cutoff_date"],
            "fixed_first_month_research_node_cohort":cohort,
            "fixed_first_month_source_weight":initial_cohort_weight,
            "fixed_cohort_original_source_available_all":cohort_complete,
            "fixed_cohort_normalized_research_score_0_100_NOT_AICS":
                f"{risk:.4f}" if risk is not None else None,
            "market_coverage_weight_not_full_index":a["market_known_weight_research_only"],
            "SP500_current_month_return_pct_expost":now,
            "SP500_following_month_return_pct_expost_NOT_AN_INPUT":forward,
            "registered_historical_early_warning_prediction":None,
            "independent_first_provider_PIT":False,
            "production_score":None,
        })
    good_forward=[r for r in records if
                  r["fixed_cohort_original_source_available_all"] and
                  r["SP500_following_month_return_pct_expost_NOT_AN_INPUT"] is not None]
    good_current=[r for r in records if
                  r["fixed_cohort_original_source_available_all"] and
                  r["SP500_current_month_return_pct_expost"] is not None]
    def corr(rows,key,ranked=False):
        xs=[dec(r["fixed_cohort_normalized_research_score_0_100_NOT_AICS"]) for r in rows]
        ys=[dec(r[key]) for r in rows]
        return pearson(rank(xs),rank(ys)) if ranked else pearson(xs,ys)
    forward="SP500_following_month_return_pct_expost_NOT_AN_INPUT"
    current="SP500_current_month_return_pct_expost"
    return {
        "schema":"aics-PIT100-24m-EXPOST-fixed-first-month-cohort-leadlag-v1",
        "as_of":rich["as_of"],
        "historical_source_cohort_fixed_from_first_month_only":cohort,
        "cohort_weight_out_of_1050":initial_cohort_weight,
        "monthly_research_observations":24,
        "potential_next_month_outcome_months":23,
        "matched_complete_first_cohort_forward_returns":len(good_forward),
        "matched_complete_first_cohort_contemporaneous_returns":len(good_current),
        "descriptive_correlation_risk_vs_following_month_SP500_return_pearson":
            corr(good_forward,forward),
        "descriptive_correlation_risk_vs_following_month_SP500_return_spearman":
            corr(good_forward,forward,ranked=True),
        "negative_control_same_month_SP500_return_pearson":
            corr(good_current,current),
        "negative_control_same_month_SP500_return_spearman":
            corr(good_current,current,ranked=True),
        "correlations_are_EXPOST_not_independent_forecast_skill":True,
        "cohort_selected_in_2024_11_then_preserved_without_future_selection":True,
        "SP500_following_month_returns_used_only_as_targets":True,
        "revised_corporate_actions_and_historical_first_delivery_not_certified":True,
        "independent_24m_out_of_sample_forecast_labels":0,
        "2000_2008_crisis_onset_lead_time_certified":False,
        "full_11node_AICS":None,
        "full_AICS_SP500_spread":None,
        "production_trades_created":False,
        "monthly_diagnostics":records,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reconciled",type=Path,default=RECONCILED)
    p.add_argument("--rich",type=Path,default=RICH)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--csv",type=Path,default=CSV)
    args=p.parse_args()
    out=compare(read_bytes(args.reconciled),read_bytes(args.rich))
    out["input_sha256"]={
        str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in (args.reconciled,args.rich)}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with args.csv.open("w",newline="",encoding="utf-8") as f:
        fields=[
            "month","market_cutoff_date","fixed_cohort_original_source_available_all",
            "fixed_cohort_normalized_research_score_0_100_NOT_AICS",
            "market_coverage_weight_not_full_index",
            "SP500_current_month_return_pct_expost",
            "SP500_following_month_return_pct_expost_NOT_AN_INPUT",
            "registered_historical_early_warning_prediction",
        ]
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        for row in out["monthly_diagnostics"]:
            w.writerow({k:row[k] for k in fields})
    print(json.dumps({
        "research_rows":24,
        "fixed_first_month_cohort":out["historical_source_cohort_fixed_from_first_month_only"],
        "observed_subsequent_return_pairs":out["matched_complete_first_cohort_forward_returns"],
        "EXPOST_risk_vs_next_SP500_corr":out["descriptive_correlation_risk_vs_following_month_SP500_return_pearson"],
        "EXPOST_risk_vs_current_SP500_corr":out["negative_control_same_month_SP500_return_pearson"],
        "historical_oos_forecast_skill":None,"production_index":None,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
