"""Summarize 24 observed research-score availability states, not market risk.

Counts & weights are visibly dated source-eligible research candidates,
not independent historical PIT, a normalized model index, skill or trade.
"""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from collections import Counter

from scripts.aics_score_reproducibility_gate import WEIGHTS

SOURCE=Path("aics_data/research/aics_24_month_no_multiplier_coverage_2026-11-21.json")
OUTPUT=Path("aics_data/research/aics_24m_weighted_observability_2026-11-21.json")
CENT=Decimal("0.01")

def pct(w):
    return str((Decimal(w)*100/Decimal(1050)).quantize(CENT,rounding=ROUND_HALF_UP))

def build(data=None):
    data=data if data is not None else json.loads(SOURCE.read_text(encoding="utf-8"))
    rows=data.get("monthly",[])
    if (data.get("schema")!="aics-24-month-source-gated-no-multiplier-coverage-v1"
        or data.get("node_weights_total")!=1050 or len(rows)!=24
        or data.get("new_11_node_full_aics_months")!=0
        or data.get("new_11_node_sp500_spread_months")!=0
        or data.get("certified_aics") is not None
        or sum(WEIGHTS.values())!=1050):
        raise ValueError("Invalid incomplete historical source ledger")
    out=[]
    for r in rows:
        known=r["latest_eligible_research_scores"]
        missing=r["missing_nodes"]
        if (set(known)|set(missing)!=set(WEIGHTS)
            or set(known)&set(missing)
            or len(known)!=r["known_node_count_research_only"]
            or r.get("full_11_node_aics_no_multiplier") is not None
            or r.get("aics_sp500_normalized_spread") is not None
            or r.get("independent_historical_pit_confirmed") is not False):
            raise ValueError("Full 11-node index falsely promoted or source set invalid")
        if any(v.get("source_available_at","")>r["as_of"] or
               not 0<=Decimal(v["score"])<=100 for v in known.values()):
            raise ValueError("Future source or invalid node input")
        w=sum(WEIGHTS[node] for node in known)
        if w<=0 or w>=1050:
            raise ValueError("Unexpected full or missing source-observability weight")
        out.append({
            "month":r["month"],
            "known_research_nodes":len(known),
            "known_research_node_weight":w,
            "total_possible_node_weight":1050,
            "source_eligible_weight_pct_not_pit":pct(w),
            "unobserved_node_weight":1050-w,
            "missing_nodes":missing,
            "full_actual_aics":None,
            "aics_sp500_historical_spread":None,
            "independently_historical_pit_certified":False
        })
    counts=Counter(r["known_research_nodes"] for r in out)
    if out[0]["month"]!="2024-11" or out[-1]["month"]!="2026-10":
        raise ValueError("Month coverage is not the original 24-month period")
    cumulative=sum(r["known_research_node_weight"] for r in out)
    avg_pct=(Decimal(cumulative)*100/(24*1050)).quantize(CENT,rounding=ROUND_HALF_UP)
    return {
        "schema":"aics-24m-dated-research-weight-observability-v1",
        "source":str(SOURCE),
        "asof_review":"2026-11-21",
        "months":24,
        "months_with_at_least_one_research_node":sum(r["known_research_nodes"]>0 for r in out),
        "months_with_full_eleven_node_aics":0,
        "months_with_historical_aics_sp500_spread":0,
        "sum_known_weight_months":cumulative,
        "sum_total_possible_weight_months":25200,
        "average_known_weight_pct_not_pit":str(avg_pct),
        "first_month_known_weight_pct_not_pit":out[0]["source_eligible_weight_pct_not_pit"],
        "last_month_known_weight_pct_not_pit":out[-1]["source_eligible_weight_pct_not_pit"],
        "months_by_known_research_node_count":{str(k):counts[k] for k in sorted(counts)},
        "rows":out,
        "independent_historical_pit_verified":False,
        "production_index":None,
        "trades_created":False,
        "explanation":"Weight availability is data-completeness only. It does not attest timestamped source delivery, prediction, calibration, market timing, or a real AICS index."
    }

if __name__=="__main__":
    print(json.dumps(build(),indent=2,ensure_ascii=False))
