"""Reproduce three 2025 Neocloud research quarters from original SEC statements.

SEC +14 calendar days, original 2025 source only, and no lookahead.
The Q1 Nebius original consolidated issuer cash-flow perimeter differs from
the later continuing-operations basis; that caveat is retained in every event.
Retrospective original web inspection is not a signed historical PIT feed.
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

RECEIPT = Path("aics_data/research/neoclouds_2025_q1_q3_sec_cashflow_research_2026-11-21.json")
BASE = "https://www.sec.gov/Archives/edgar/data/"
EXPECTED_SOURCE_KEYS = {"crwv_q1","crwv_h1","crwv_9m","nbis_q1","nbis_q2","nbis_9m"}
EXPECTED_Q = {"2025-Q1":"2025-06-03","2025-Q2":"2025-08-27","2025-Q3":"2025-11-27"}


def dec(x):
    if isinstance(x,bool):
        raise ValueError("Non-numeric cashflow")
    try:
        val=Decimal(str(x))
    except (InvalidOperation,TypeError,ValueError) as exc:
        raise ValueError("Invalid source numeric") from exc
    if not val.is_finite():
        raise ValueError("Nonfinite source input")
    return val


def score(cfo,purchases):
    if purchases<=0:
        raise ValueError("Non-positive source capital purchases")
    value=100*(1-cfo/purchases)
    return min(Decimal(100),max(Decimal(0),value)).quantize(Decimal(".01"),rounding=ROUND_HALF_UP)


def calculate(data=None):
    data = data if data is not None else json.loads(RECEIPT.read_text(encoding="utf-8"))
    if (data.get("schema")!="aics-neocloud-2025-q1-q3-original-sec-research-v1"
            or data.get("model_node")!="Neoclouds"
            or data.get("weight")!=100
            or data.get("certified_aics") is not None
            or data.get("original_11_node_index_untouched") is not True
            or data.get("legacy_multiplier_applied") is not False
            or data.get("raw_complete_submission_independently_rehashed") is not False
            or data.get("historical_pit_original_provider_capture_attested") is not False
            or data.get("independent_24_month_oos") is not False
            or data.get("trades_created") is not False):
        raise ValueError("Source scenario wrongly approved as an AICS index")
    sources=data["sources"]
    if set(sources)!=EXPECTED_SOURCE_KEYS:
        raise ValueError("Six complete original SEC filing references required")
    for name,row in sources.items():
        filed=dt.date.fromisoformat(row["filed_at"])
        available=dt.date.fromisoformat(row["available_at"])
        if available != filed+dt.timedelta(days=14):
            raise ValueError("SEC 14-day embargo violated")
        if row.get("source_raw_sha256") is not None:
            raise ValueError("Unverified original bytes claim")
        if (not row["source_page"].startswith(BASE)
                or not row["sec_index"].startswith(BASE)
                or row["accession"].replace("-","") not in row["source_page"]
                or row["accession"].replace("-","") not in row["sec_index"]
                or row["issuer"] != ("CoreWeave" if name.startswith("crwv_") else "Nebius")):
            raise ValueError("Invalid original accession or issuer")
    crwv={
        "2025-Q1":(dec(sources["crwv_q1"]["cfo_ytd"]),dec(sources["crwv_q1"]["cash_purchases_ytd"])),
        "2025-Q2":(dec(sources["crwv_h1"]["cfo_ytd"])-dec(sources["crwv_q1"]["cfo_ytd"]),
                   dec(sources["crwv_h1"]["cash_purchases_ytd"])-dec(sources["crwv_q1"]["cash_purchases_ytd"])),
        "2025-Q3":(dec(sources["crwv_9m"]["cfo_ytd"])-dec(sources["crwv_h1"]["cfo_ytd"]),
                   dec(sources["crwv_9m"]["cash_purchases_ytd"])-dec(sources["crwv_h1"]["cash_purchases_ytd"]))
    }
    nbis={
        "2025-Q1":(dec(sources["nbis_q1"]["cfo_quarter"]),dec(sources["nbis_q1"]["cash_purchases_quarter"])),
        "2025-Q2":(dec(sources["nbis_q2"]["cfo_quarter"]),dec(sources["nbis_q2"]["cash_purchases_quarter"])),
        "2025-Q3":(dec(sources["nbis_9m"]["cfo_9m"])-dec(sources["nbis_q2"]["cfo_h1"]),
                   dec(sources["nbis_9m"]["cash_purchases_9m"])-dec(sources["nbis_q2"]["cash_purchases_h1"]))
    }
    observations=data["observations"]
    if len(observations)!=3 or [x["period"] for x in observations]!=list(EXPECTED_Q):
        raise ValueError("Wrong quarter roster")
    results=[]
    for original in observations:
        quarter=original["period"]
        cfo_c,capex_c=crwv[quarter]
        cfo_n,capex_n=nbis[quarter]
        avail=max(sources[key]["available_at"] for key in
                  (("crwv_q1","nbis_q1") if quarter=="2025-Q1" else
                   ("crwv_h1","nbis_q2") if quarter=="2025-Q2" else
                   ("crwv_9m","nbis_9m")))
        actual={"coreweave_operating_cash_m":cfo_c,
                "coreweave_cash_purchases_m":capex_c,
                "nebius_operating_cash_m":cfo_n,
                "nebius_cash_purchases_m":capex_n,
                "total_operating_cash_m":cfo_c+cfo_n,
                "total_cash_purchases_m":capex_c+capex_n}
        if (avail!=EXPECTED_Q[quarter] or original["available_at"]!=avail or
                any(dec(original[key])!=v for key,v in actual.items()) or
                dec(original["score"])!=score(actual["total_operating_cash_m"],
                                               actual["total_cash_purchases_m"])):
            raise ValueError("Original 2025 SEC statements / cashflow arithmetic mismatched")
        results.append({
            "period":quarter,
            "available_at":avail,
            "score":original["score"],
            "weighted_node_contribution":original["score"],
            "total_cfo_usd_m":str(actual["total_operating_cash_m"]),
            "total_cash_purchases_usd_m":str(actual["total_cash_purchases_m"]),
            "scope_warning":data["comparability_warning"],
            "historical_pit_certified":False,
            "full_aics":None,
        })
    return results


if __name__=="__main__":
    print(json.dumps(calculate(),indent=2,ensure_ascii=False))
