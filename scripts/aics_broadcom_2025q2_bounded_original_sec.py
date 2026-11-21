"""One observable AI Demand zero inferred from a STRICT reported lower bound.

Original SEC 2025-Q1 guidance = 4.4B; original 2025-Q2 actual >4.4B.
Therefore score=0 for all actual values compatible with the actual release.
Do not assert an exact unreported value or PIT-certified historical source.
"""
from __future__ import annotations
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

SOURCE=Path("aics_data/research/broadcom_ai_demand_2025q2_strict_lower_bound_sec_2026-11-21.json")
BASE="https://www.sec.gov/Archives/edgar/data/1730168/"
EXPECTED={
 "prior_guidance_filing":{
    "period":"2025-Q1","filed_at":"2025-03-06",
    "accession":"0001730168-25-000009",
    "file":"avgo-02022025x8kxex99.htm"},
 "actual_filing":{
    "period":"2025-Q2","filed_at":"2025-06-05",
    "accession":"0001730168-25-000061",
    "file":"avgo-05042025x8kxex99.htm"},
}

def calculate(data=None):
    data=data if data is not None else json.loads(SOURCE.read_text(encoding="utf-8"))
    cert=data.get("certification",{})
    if (data.get("schema")!="aics-broadcom-2025q2-bounded-actual-above-guidance-original-sec-v1"
        or data.get("node")!="AI Demand"
        or data.get("node_weight")!=50
        or data.get("issuer")!="Broadcom Inc."
        or data.get("cik")!="1730168"
        or data.get("period")!="2025-Q2"
        or data.get("period_end")!="2025-05-04"
        or any(cert.get(k) is not False for k in (
          "original_full_submission_bytes_rehashed",
          "independent_2025_provider_delivery_attested",
          "historical_pit_certified",
          "independent_out_of_sample_model_verified",
          "trades_created"))
        or cert.get("full_11_node_aics") is not None
        or cert.get("historical_aics_sp500_spread") is not None):
        raise ValueError("Unverified source or illicit historical AICS promotion")
    for key,exp in EXPECTED.items():
        f=data.get(key,{})
        acc=exp["accession"]
        filepath=BASE+acc.replace("-","")+"/"
        filed=dt.date.fromisoformat(exp["filed_at"])
        if (f.get("period")!=exp["period"] or f.get("filed_at")!=exp["filed_at"]
            or f.get("available_at")!=(filed+dt.timedelta(days=14)).isoformat()
            or f.get("form")!="8-K" or f.get("exhibit")!="EX-99.1"
            or f.get("accession")!=acc
            or f.get("source_url")!=filepath+exp["file"]
            or f.get("source_index")!=filepath+acc+"-index.htm"
            or f.get("raw_original_sha256") is not None):
            raise ValueError("Invalid original SEC filing identity or +14 day embargo")
    prior=data["prior_guidance_filing"]
    actual=data["actual_filing"]
    deduction=data.get("deduction",{})
    guidance=prior.get("next_quarter_guidance_ai_revenue_usd_m")
    lower=actual.get("reported_actual_lower_bound_strict_usd_m")
    if (type(guidance) is not int or type(lower) is not int
        or guidance!=4400 or lower!=4400
        or prior.get("quantifier")!="expected AI semiconductor revenue of $4.4 billion in Q2"
        or actual.get("reported_actual_relation")!=">"
        or actual.get("reported_actual_exact_usd_m") is not None
        or actual.get("original_text_summary")!="Q2 AI revenue grew 46% year-over-year to over $4.4 billion"
        or actual["available_at"]<=prior["available_at"]
        or deduction.get("joint_source_first_available_at")!=actual["available_at"]
        or deduction.get("does_not_imply_exact_revenue_known") is not True
        or deduction.get("contemporaneous_original_reports_from_2025_but_retrieved_2026") is not True):
        raise ValueError("Broadcom strict lower-bound proof or chronology invalid")
    # A > G > 0 mathematically guarantees max(0, 1-A/G)==0.
    if lower!=guidance or not Decimal(guidance)>0 or deduction.get("score")!="0.00":
        raise ValueError("No logically bounded stress score from original sources")
    return {
        "period":"2025-Q2","node":"AI Demand",
        "available_at":actual["available_at"],"score":"0.00",
        "actual_exact_usd_m":None,"actual_strictly_greater_than_usd_m":lower,
        "guidance_usd_m":guidance,
        "original_forecast_source":prior["source_url"],
        "original_actual_source":actual["source_url"],
        "independently_historical_pit_certified":False,
        "certified_full_aics":None,
        "trades_created":False,
    }

if __name__=="__main__":
    print(json.dumps(calculate(),indent=2,ensure_ascii=False))
