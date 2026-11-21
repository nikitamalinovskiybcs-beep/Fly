"""Replay issuer-hosted PRU quarterly original filing credit proxy without SEC lookahead.

The 2025-Q1 through 2026-Q3 Prudential filings (including the 2025Q4 10-K) contain a consistent
nonaccrual-WITHOUT-related-ACL numerator and a balance-sheet gross scope-
matched net commercial mortgage/other loans denominator. This ratio is
a narrowly scoped research candidate, not total delinquency or a certified
Insurers node. Original bytes and contemporaneous delivery remain unaudited.
"""
import datetime as dt
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

LEDGER=Path("aics_data/research/pru_insurers_nonaccrual_original_quarters_2025_2026.json")
EXPECTED={
    "2025-Q1":("2025-03-31","2025-05-01","0001137774-25-000060",274,54169),
    "2025-Q2":("2025-06-30","2025-07-31","0001137774-25-000108",423,54612),
    "2025-Q3":("2025-09-30","2025-10-30","0001137774-25-000178",415,55829),
    "2025-Q4":("2025-12-31","2026-02-12","0001137774-26-000048",442,56195),
    "2026-Q1":("2026-03-31","2026-05-06","0001137774-26-000095",250,56436),
    "2026-Q2":("2026-06-30","2026-08-05","0001137774-26-000176",757,57458),
    "2026-Q3":("2026-09-30","2026-11-04","0001137774-26-000221",610,58685),
}
BASE="https://investor.prudential.com/financials/sec-filings/content/"


def ratio(numerator,denominator):
    if type(numerator) is not int or type(denominator) is not int or not 0<=numerator<=denominator:
        raise ValueError("Invalid issuer credit-source operands")
    return str((Decimal(100)*Decimal(numerator)/Decimal(denominator)).quantize(
        Decimal("0.01"),rounding=ROUND_HALF_UP))


def calculate(data=None):
    data=data if data is not None else json.loads(LEDGER.read_text(encoding="utf-8"))
    if (data.get("schema")!="aics-pru-insurers-noacl-nonaccrual-quarterly-original-filing-v1"
            or data.get("node")!="Insurers" or data.get("node_weight")!=125
            or data.get("issuer_count")!=1 or data.get("periods")!=7
            or data.get("raw_original_bytes_independently_rehashed") is not False
            or data.get("independently_historically_contemporaneous_pit_certified") is not False
            or data.get("independently_verified_24_month_oos") is not False
            or data.get("model_production_formula_modified") is not False
            or data.get("hot_node_multiplier_applied") is not False
            or data.get("complete_11_node_aics") is not None
            or data.get("trades_created") is not False
            or data.get("research_only") is not True):
        raise ValueError("Invalid Insurers original research provenance")
    events=data["events"]
    if len(events)!=7 or [x["quarter"] for x in events]!=list(EXPECTED):
        raise ValueError("Required six observed Prudential quarters missing")
    output=[]
    for row in events:
        quarter=row["quarter"]
        period,filed,acc,numerator,denominator=EXPECTED[quarter]
        available=(dt.date.fromisoformat(filed)+dt.timedelta(days=14)).isoformat()
        if quarter=="2025-Q4":
            sec_path="https://www.sec.gov/Archives/edgar/data/1137774/"+acc.replace("-","")+"/"
            expected_url=sec_path+"pru-"+period.replace("-","")+".htm"
            expected_index=sec_path+acc+"-index.htm"
            if row.get("source_index")!=expected_index:
                raise ValueError("Original 10-K SEC index invalid")
        else:
            expected_url=BASE+acc+"/pru-"+period.replace("-","")+".htm"
        if (row.get("period_end")!=period or row.get("filed_at")!=filed
                or row.get("accession")!=acc or row.get("source_url")!=expected_url
                or row.get("available_at")!=available
                or row.get("issuer")!="Prudential Financial, Inc."
                or row.get("cik")!="1137774" or row.get("form")!=("10-K" if quarter=="2025-Q4" else "10-Q")
                or row.get("source_raw_sha256") is not None
                or row.get("original_provider_delivery_pit_attested") is not False):
            raise ValueError("PRU issuer, SEC accession or +14 day source chronology invalid")
        if quarter=="2026-Q3":
            correction=data.get("september_2026_correction_notice",{})
            if (correction.get("previous_denominator_usd_m")!=67004
                or correction.get("correct_portfolio_denominator_usd_m")!=58685
                or correction.get("previous_score_pct")!="0.91"
                or correction.get("corrected_score_pct")!="1.04"):
                raise ValueError("Q3 denominator correction lost")
        if (row.get("nonaccrual_no_related_acl_usd_m")!=numerator
                or row.get("commercial_mortgage_and_other_loans_net_usd_m")!=denominator
                or row.get("score_pct")!=ratio(numerator,denominator)):
            raise ValueError("Issuer original loan quantities or ratio mismatched")
        output.append({
            "node":"Insurers",
            "quarter":quarter,
            "available_at":available,
            "score":row["score_pct"],
            "source_url":row["source_url"],
            "source_receipt":str(LEDGER),
            "metric":"PRU nonaccrual without related allowance / net commercial mortgage and other loans",
            "historical_provider_pit_certified":False,
            "independent_24m_oos":False
        })
    return output


if __name__=="__main__":
    print(json.dumps(calculate(),ensure_ascii=False,indent=2))
