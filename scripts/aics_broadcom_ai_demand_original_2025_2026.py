"""Reproduce three 2025-26 Broadcom AI semiconductor actual-vs-prior-guidance research observations.

Only dated original SEC 8-K EX-99.1 issuer quotes. SEC availability = filing
date +14 calendar days; both forecast and actual must pass gate. Q4 2025
actual excluded because exact original 8-K quarterly AI amount absent.
The 0.00 stress is calculated, not imputed; not independent provider PIT.
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

RECORD=Path("aics_data/research/broadcom_ai_demand_2025q3_2026q2_original_sec_guidance_2026-11-21.json")
EXPECTED={
 "2025-Q2":("2025-05-04","2025-06-05","0001730168-25-000061","avgo-05042025x8kxex99.htm",5100),
 "2025-Q3":("2025-08-03","2025-09-04","0001730168-25-000094","avgo-08032025x8kxex99.htm",6200),
 "2025-Q4":("2025-11-02","2025-12-11","0001730168-25-000116","avgo-11022025x8kxex99.htm",8200),
 "2026-Q1":("2026-02-01","2026-03-04","0001730168-26-000011","avgo-02012026x8kxex99.htm",10700),
 "2026-Q2":("2026-05-03","2026-06-03","0001730168-26-000051","avgo-05032026x8kxex99.htm",16000)
}
OBS={
 "2025-Q3":("2025-Q2",5200,5100,"2025-09-18"),
 "2026-Q1":("2025-Q4",8400,8200,"2026-03-18"),
 "2026-Q2":("2026-Q1",10800,10700,"2026-06-17")
}
BASE="https://www.sec.gov/Archives/edgar/data/1730168/"
CENTS=Decimal("0.01")

def calculate(data=None):
    data=data if data is not None else json.loads(RECORD.read_text(encoding="utf-8"))
    if (data.get("schema")!="aics-broadcom-ai-demand-2025q3-to-2026q2-original-sec-guidance-research-v1"
        or data.get("node")!="AI Demand"
        or data.get("weight")!=50
        or data.get("issuer")!="Broadcom Inc."
        or data.get("cik")!="1730168"
        or data.get("unit")!="USD million"
        or data.get("excluded_quarters")!=["2025-Q4"]
        or data.get("existing_2026q3_source")!="aics_data/research/broadcom_ai_semiconductor_revenue_2026_q2_q3.json"
        or data.get("raw_complete_submissions_independently_sha256_rehashed") is not False
        or data.get("original_provider_delivered_at_historical_date_independently_attested") is not False
        or data.get("historical_provider_market_pit_certified") is not False
        or data.get("independent_24month_out_of_sample") is not False
        or data.get("all_11_node_history_complete") is not False
        or data.get("certified_aics") is not None
        or data.get("model_hot_multiplier_applied") is not False
        or data.get("production_model_formula_changed") is not False
        or data.get("trades_created") is not False):
        raise ValueError("Broadcom original research scope or fraudulent model promotion")
    filings=data.get("filings",[])
    if len(filings)!=5 or [f["period"] for f in filings]!=list(EXPECTED):
        raise ValueError("Missing or out-of-order Broadcom original SEC 8-K releases")
    validated={}
    for f in filings:
        q=f["period"]
        end,filed,acc,doc,forecast=EXPECTED[q]
        sec_path=BASE+acc.replace("-","")+"/"
        seen=dt.date.fromisoformat(filed)
        released=(seen+dt.timedelta(days=14)).isoformat()
        if (f.get("period_end")!=end or f.get("filed_at")!=filed
            or f.get("available_at")!=released
            or f.get("accession")!=acc
            or f.get("original_sec_exhibit_url")!=sec_path+doc
            or f.get("original_sec_filing_index_url")!=sec_path+acc+"-index.htm"
            or f.get("issuer")!="Broadcom Inc." or f.get("cik")!="1730168"
            or f.get("form")!="8-K" or f.get("exhibit")!="EX-99.1"
            or f.get("next_quarter_ai_semiconductor_guidance_usd_m")!=forecast
            or f.get("original_full_submission_sha256") is not None
            or f.get("original_provider_historical_capture_attested") is not False):
            raise ValueError("Original SEC issuer, guidance, URL or 14-day gate mismatch")
        validated[q]=f
    rows=data.get("observations",[])
    if len(rows)!=3 or [r["period"] for r in rows]!=list(OBS):
        raise ValueError("Only three original actual-vs-guidance quarter observations eligible")
    result=[]
    for row in rows:
        period=row["period"]
        previous,actual,forecast,available=OBS[period]
        if (row.get("previous_forecast_from_period")!=previous
            or type(row.get("reported_actual_usd_m")) is not int
            or row.get("reported_actual_usd_m")!=actual
            or row.get("previous_guidance_usd_m")!=forecast
            or validated[previous]["next_quarter_ai_semiconductor_guidance_usd_m"]!=forecast
            or validated[period]["available_at"]!=available
            or row.get("available_at")!=available
            or validated[previous]["available_at"]>=available):
            raise ValueError("AI actual/guidance data mismatch or future forecast leak")
        score=(max(Decimal(0),Decimal(100)*(Decimal(1)-Decimal(actual)/Decimal(forecast)))).quantize(
            CENT,rounding=ROUND_HALF_UP)
        if row.get("score")!=str(score):
            raise ValueError("Broadcom observed stress formula or score mismatch")
        result.append({
            "period":period,"available_at":available,"score":str(score),
            "reported_actual_usd_m":actual,"previous_guidance_usd_m":forecast,
            "original_actual_sec_url":validated[period]["original_sec_exhibit_url"],
            "original_prior_guidance_sec_url":validated[previous]["original_sec_exhibit_url"],
            "historically_pit_certified":False,"full_aics":None
        })
    return result

if __name__=="__main__":
    print(json.dumps(calculate(),ensure_ascii=False,indent=2))
