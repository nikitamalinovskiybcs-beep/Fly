"""Audit source-event recency across a strictly incomplete 24-month AICS panel.

This is only source-observability recency, NOT an index, historical PIT
attestation, predictive signal, decay assumption or recommendation. Carrying
a source-eligible quarterly observation forward is allowed and separately
identified; this script NEVER imputes missing node values.
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS

SOURCE=Path("aics_data/research/aics_24_month_no_multiplier_coverage_2026-11-21.json")
OUTPUT=Path("aics_data/research/aics_24m_source_freshness_audit_2026-11-21.json")
CENT=Decimal("0.01")

def pct(weight):
    return str((Decimal(weight)*100/Decimal(1050)).quantize(CENT,rounding=ROUND_HALF_UP))

def audit(data=None):
    data=data if data is not None else json.loads(SOURCE.read_text(encoding="utf-8"))
    if (data.get("schema")!="aics-24-month-source-gated-no-multiplier-coverage-v1"
        or data.get("node_weights_total")!=1050
        or sum(WEIGHTS.values())!=1050
        or len(data.get("monthly",[]))!=24
        or data.get("new_11_node_full_aics_months")!=0
        or data.get("new_11_node_sp500_spread_months")!=0
        or data.get("certified_aics") is not None):
        raise ValueError("Wrong historical source-availability panel or fabricated AICS")
    event_map={}
    for e in data["score_source_events"]:
        key=(e["node"],e["available_at"],e["score"])
        if (e["node"] not in WEIGHTS
            or e.get("independently_attested_historical_pit") is not False
            or e.get("independently_24month_oos_verified") is not False
            or key in event_map):
            raise ValueError("Invalid, duplicated or wrongly certified source event")
        event_map[key]=True
    rows=[]
    totals={"fresh":0,"carried":0,"missing":0,"over90":0}
    for idx,row in enumerate(data["monthly"]):
        month=row["month"]
        year,mm=map(int,month.split("-"))
        month_end=dt.date(year,mm,calendar.monthrange(year,mm)[1])
        expected_month=(2024+(10+idx)//12,(10+idx)%12+1)
        if ((year,mm)!=expected_month or row["as_of"]!=month_end.isoformat()
            or row.get("full_11_node_aics_no_multiplier") is not None
            or row.get("aics_sp500_normalized_spread") is not None
            or row.get("independent_historical_pit_confirmed") is not False):
            raise ValueError("Month alignment or illegitimate full-AICS promotion")
        known=row["latest_eligible_research_scores"]
        missing=row["missing_nodes"]
        if (set(known)|set(missing)!=set(WEIGHTS)
            or set(known)&set(missing)
            or len(known)!=row["known_node_count_research_only"]):
            raise ValueError("Unknown/fabricated node roster")
        fresh=[]; carried=[]; age90=[]; ages={}
        for node,datum in known.items():
            date=dt.date.fromisoformat(datum["source_available_at"])
            score=datum["score"]
            if (date>month_end or
                (node,date.isoformat(),score) not in event_map or
                datum["carried_from_prior_month"]!=(date.strftime("%Y-%m")!=month)):
                raise ValueError("Undated, stale-flag mismatched or lookahead source")
            age=(month_end-date).days
            ages[node]=age
            (fresh if date.strftime("%Y-%m")==month else carried).append(node)
            if age>90:
                age90.append(node)
        weights={
            "fresh":sum(WEIGHTS[n] for n in fresh),
            "carried":sum(WEIGHTS[n] for n in carried),
            "missing":sum(WEIGHTS[n] for n in missing),
            "over90":sum(WEIGHTS[n] for n in age90),
        }
        if sum(weights[x] for x in ("fresh","carried","missing"))!=1050:
            raise ValueError("Freshness weights do not reconcile")
        for name,value in weights.items():
            totals[name]+=value
        rows.append({
            "month":month,
            "known_node_count":len(known),
            "fresh_source_nodes":sorted(fresh),
            "carried_source_nodes":sorted(carried),
            "missing_nodes":missing,
            "fresh_source_weight":weights["fresh"],
            "carried_source_weight":weights["carried"],
            "missing_node_weight":weights["missing"],
            "over_90_day_old_source_weight":weights["over90"],
            "fresh_pct_of_full_1050_not_pit":pct(weights["fresh"]),
            "carried_pct_of_full_1050_not_pit":pct(weights["carried"]),
            "missing_pct_of_full_1050":pct(weights["missing"]),
            "known_source_age_days_by_node":dict(sorted(ages.items())),
            "full_historical_aics":None,
            "historical_aics_sp500_spread":None,
            "historical_pit_certified":False,
        })
    if (rows[0]["month"]!="2024-11" or rows[-1]["month"]!="2026-10"
        or rows[-1]["fresh_source_weight"]!=325
        or rows[-1]["carried_source_weight"]!=625
        or rows[-1]["missing_node_weight"]!=100):
        raise ValueError("Oct 2026 should have 325 fresh/625 carried/100 missing")
    return {
        "schema":"aics-24m-source-age-weight-partition-research-v1",
        "source":str(SOURCE),
        "asof_review":"2026-11-21",
        "months":24,
        "total_weight":1050,
        "full_historical_aics_months":0,
        "full_aics_sp500_spread_months":0,
        "total_fresh_weight_months":totals["fresh"],
        "total_carried_weight_months":totals["carried"],
        "total_missing_weight_months":totals["missing"],
        "fresh_month_weight_avg_pct":pct(Decimal(totals["fresh"])/24),
        "carried_month_weight_avg_pct":pct(Decimal(totals["carried"])/24),
        "missing_month_weight_avg_pct":pct(Decimal(totals["missing"])/24),
        "months_with_over90_day_old_eligible_source":sum(x["over_90_day_old_source_weight"]>0 for x in rows),
        "over90_weight_months":totals["over90"],
        "last_month":rows[-1],
        "rows":rows,
        "historically_attested_pit":False,
        "certified_aics":None,
        "trades_created":False,
        "explanation":"Freshness measures when a declared source first became research-eligible in the month. Carry-forward may be appropriate for quarterly reports and is NOT missing data. These are not proven historical provider tape captures; none of the source-age figures are trading signals."
    }

if __name__=="__main__":
    print(json.dumps(audit(),ensure_ascii=False,indent=2))
