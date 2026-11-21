"""Unmultiplied AICS mathematical bounds for missing scored nodes.

Not predictive intervals, not a full AICS series and not AICS-SP500 spread.
The lower bound assumes all *missing* node scores could be zero, while upper
assumes they could be 100. Neither assumption is an observed imputed score.
Existing observed score research is not independently certified PIT.
"""
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import json

from scripts.aics_score_reproducibility_gate import WEIGHTS

INPUT=Path("aics_data/research/aics_24_month_no_multiplier_coverage_2026-11-21.json")
OUTPUT=Path("aics_data/research/aics_24m_unmultiplied_node_bounds_2026-11-21.json")
CENT=Decimal("0.01")

def rnd(x):
    return str(x.quantize(CENT,rounding=ROUND_HALF_UP))

def build(data=None):
    data=data if data is not None else json.loads(INPUT.read_text(encoding="utf-8"))
    if (data.get("schema")!="aics-24-month-source-gated-no-multiplier-coverage-v1"
            or data.get("node_weights_total")!=1050
            or len(data.get("monthly",[]))!=24
            or data.get("new_11_node_full_aics_months")!=0
            or data.get("new_11_node_sp500_spread_months")!=0
            or data.get("certified_aics") is not None):
        raise ValueError("Source must be complete 24 month panel, not certified AICS")
    rows=[]
    for row in data["monthly"]:
        known=row["latest_eligible_research_scores"]
        missing=row["missing_nodes"]
        if (set(known)&set(missing)
                or set(known)|set(missing)!=set(WEIGHTS)
                or len(known)!=row["known_node_count_research_only"]
                or row["aics_sp500_normalized_spread"] is not None
                or row["full_11_node_aics_no_multiplier"] is not None):
            raise ValueError("Missing or duplicated AICS nodes")
        lower=sum((Decimal(WEIGHTS[k])*Decimal(v["score"])/100
                   for k,v in known.items()),Decimal(0))
        if any(not 0<=Decimal(v["score"])<=100 for v in known.values()):
            raise ValueError("Out-of-range observed candidate")
        stored=row["partial_known_weighted_points_not_aics"]
        if (rnd(lower) if known else None)!=stored:
            raise ValueError("Underlying partial arithmetic or rounding drift")
        unknown_weight=sum(WEIGHTS[k] for k in missing)
        upper=lower+Decimal(unknown_weight)
        rows.append({
            "month":row["month"],
            "known_nodes":len(known),
            "missing_nodes":missing,
            "unknown_total_node_weight":unknown_weight,
            "known_contribution_lower_bound":rnd(lower),
            "arithmetic_upper_bound_if_all_missing_scores_were_100":rnd(upper),
            "arithmetic_band_width":str(unknown_weight),
            "actual_complete_aics":None,
            "actual_aics_minus_sp500_spread":None,
            "qualification":"Bounds only; missing values were NOT set to zero or 100 in the original AICS source data",
            "independently_historically_pit_attested":False,
        })
    if (rows[-1]["month"]!="2026-10" or rows[-1]["known_nodes"]!=10
            or rows[-1]["missing_nodes"]!=["AI Equities"]
            or rows[-1]["known_contribution_lower_bound"]!="453.17"
            or rows[-1]["arithmetic_upper_bound_if_all_missing_scores_were_100"]!="553.17"):
        raise ValueError("October 2026 bounds changed unexpectedly")
    return {
        "schema":"aics-24-month-unmultiplied-arithmetic-bounds-v1",
        "asof_research":"2026-11-21",
        "weights_total":1050,
        "multiplier_applied":False,
        "meaning":"Pure mathematical min/max range conditional on the known historical research-only scores. NOT a probability forecast, index observation, price spread or any missing-data imputation.",
        "observed_market_months":24,
        "actual_complete_aics_months":0,
        "actual_aics_sp500_spread_months":0,
        "rows":rows,
        "certified_aics":None,
        "trades_created":False,
    }

if __name__=="__main__":
    print(json.dumps(build(),ensure_ascii=False,indent=2))
