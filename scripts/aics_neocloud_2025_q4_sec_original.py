"""Reproduce 2025 Q4 Neocloud cash funding stress from two original SEC exhibits.

CoreWeave EX-99.1 original reported Q4 2025 cash-flow figures are in
whole USD millions; the older 9M 10-Q ledger has USD thousand precision.
Never use FY-minus-9M as a claim of exact Q4 original numbers.
Nebius original EX-99.1 2025-Q4 is continuing operations.
Historical SEC provider PIT rehash/independent 24-month OOS NOT certified.
"""
import datetime as dt
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

SOURCE=Path("aics_data/research/neoclouds_2025_q4_sec_original_cashflow_2026-11-21.json")
SEC="https://www.sec.gov/Archives/edgar/data/"
EXPECTED={
 "CoreWeave":{
    "cik":"1769628","accession":"0001769628-26-000094","form":"8-K",
    "filed_at":"2026-02-26","available_at":"2026-03-12",
    "doc":"coreweave4q25earningspress.htm","q4_cfo":"1559","q4_purchases":"4060",
    "fy_cfo":"3058","fy_purchases":"10309"},
 "Nebius":{
    "cik":"1513845","accession":"0001104659-26-013946","form":"6-K",
    "filed_at":"2026-02-12","available_at":"2026-02-26",
    "doc":"tm266173d1_ex99-1.htm","q4_cfo":"834.3","q4_purchases":"2056.0",
    "fy_cfo":"401.9","fy_purchases":"4066.0"}
}
Q=Decimal("0.01")

def amt(s):
    if not isinstance(s,str):
        raise ValueError("Unpinned cashflow numerical type")
    x=Decimal(s)
    if not x.is_finite():
        raise ValueError("Invalid source cashflow")
    return x

def calculate(data=None):
    data=data if data is not None else json.loads(SOURCE.read_text(encoding="utf-8"))
    if (data.get("schema")!="aics-neocloud-2025-q4-original-sec-research-v1"
        or data.get("period")!="2025-Q4"
        or data.get("model_node")!="Neoclouds"
        or data.get("weight")!=100
        or data.get("original_provider_historical_delivery_independently_attested") is not False
        or data.get("original_full_submission_bytes_independently_rehashed") is not False
        or data.get("historical_24_month_oos_verified") is not False
        or data.get("legacy_multiplier_applied") is not False
        or data.get("production_formula_changed") is not False
        or data.get("certified_full_aics") is not None
        or data.get("trades_created") is not False):
        raise ValueError("Unsupported certification or research event identity")
    sources=data.get("sources",{})
    if set(sources)!=set(EXPECTED):
        raise ValueError("Requires exactly two original reporting issuers")
    sums={"cfo":Decimal(0),"purchases":Decimal(0)}
    for issuer,expected in EXPECTED.items():
        source=sources[issuer]
        filing=dt.date.fromisoformat(source["filed_at"])
        if (source.get("issuer")!=issuer
            or source.get("cik")!=expected["cik"]
            or source.get("accession")!=expected["accession"]
            or source.get("form")!=expected["form"]
            or source.get("exhibit")!="EX-99.1"
            or source.get("filed_at")!=expected["filed_at"]
            or source.get("available_at")!=expected["available_at"]
            or source.get("available_at")!=(filing+dt.timedelta(days=14)).isoformat()
            or source.get("original_quarter_ended")!="2025-12-31"
            or source.get("source_raw_sha256") is not None):
            raise ValueError("Issuer original SEC date, accession or embargo mismatched")
        sec_path=SEC+expected["cik"]+"/"+expected["accession"].replace("-","")+"/"
        if (source.get("source_page")!=sec_path+expected["doc"]
            or source.get("sec_index")!=sec_path+expected["accession"]+"-index.htm"):
            raise ValueError("Original issuer SEC URL mismatch")
        cfo=amt(source["cfo_quarter_usd_m"])
        purchases=amt(source["cash_purchases_quarter_usd_m"])
        fy_cfo_key="published_fy_cfo_usd_m" if issuer=="CoreWeave" else "published_fy_continuing_cfo_usd_m"
        if (cfo!=amt(expected["q4_cfo"])
            or purchases!=amt(expected["q4_purchases"])
            or amt(source[fy_cfo_key])!=amt(expected["fy_cfo"])
            or amt(source["published_fy_cash_purchases_usd_m"])!=amt(expected["fy_purchases"])
            or purchases<=0):
            raise ValueError("SEC quarterly original cash flow mismatch")
        if issuer=="Nebius" and "continuing operations" not in source.get("cfo_scope",""):
            raise ValueError("Nebius continuing scope was lost")
        sums["cfo"]+=cfo
        sums["purchases"]+=purchases
    gap=sums["purchases"]-sums["cfo"]
    score=max(Decimal(0),min(Decimal(100),100*(1-sums["cfo"]/sums["purchases"])))
    score=score.quantize(Q,rounding=ROUND_HALF_UP)
    point=data["measurement"]
    if (amt(point["total_quarter_cfo_usd_m"])!=sums["cfo"]
        or amt(point["total_quarter_cash_purchases_usd_m"])!=sums["purchases"]
        or amt(point["funding_gap_usd_m"])!=gap
        or amt(point["score_0_100"])!=score
        or point["joint_first_sec_eligible_at"]!=max(s["available_at"] for s in sources.values())
        or point["research_weighted_points"]!=str(score)):
        raise ValueError("Combined SEC cashflow and score arithmetic mismatch")
    return {
        "period":"2025-Q4","node":"Neoclouds",
        "available_at":point["joint_first_sec_eligible_at"],"score":str(score),
        "total_cfo_usd_m":str(sums["cfo"]),
        "total_cash_purchases_usd_m":str(sums["purchases"]),
        "cash_funding_gap_usd_m":str(gap),
        "scope_warning":data["comparability_warning"],
        "original_source_receipt":str(SOURCE),
        "historical_pit_certified":False,"full_aics":None
    }

if __name__=="__main__":
    print(json.dumps(calculate(),ensure_ascii=False,indent=2))
