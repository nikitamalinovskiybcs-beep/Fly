"""AICS pre-crisis cash-funding imbalance layer, distinct from stress index.

Source-grounded original SEC quarterly 4-hyperscaler data across 2025Q1-Q4
and 2026Q1-Q3. Do not backdate recovered 2026Q1, infer bank debt from a
negative CFO-minus-cash-PPE gap, backfill availability, or claim AI-specific
spending. Primary filing dated source amounts are research originals, not
independently archived historical SEC bytes or PIT-certified trading signals.

Outcomes are an *imbalance shadow*, not an extra weighted AICS node.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS

ROOT=Path("aics_data/research")
Y2025=ROOT/"hyperscalers_2025_q1_q3_original_sec_cashflow_2026-11-21.json"
Q42025=ROOT/"hyperscalers_2025_q4_original_sec_cashflow_2026-11-21.json"
Q12026=ROOT/"hyperscalers_2026_q1_original_sec_cashflow_2026-11-22.json"
Q22026=ROOT/"hyperscalers_cash_coverage_june_to_september_2026.json"
Q32026=ROOT/"hyperscalers_operating_cash_flow_coverage_2026_q3.json"
OUTPUT=ROOT/"aics_precrisis_imbalance_4hyperscalers_2025_2026_research_2026-11-22.json"
ISSUERS={"Microsoft","Amazon","Alphabet","Meta"}
WANTED=("2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q1","2026-Q2","2026-Q3")
QUARTER_END={
    "2025-Q1":"2025-03-31","2025-Q2":"2025-06-30",
    "2025-Q3":"2025-09-30","2025-Q4":"2025-12-31",
    "2026-Q1":"2026-03-31","2026-Q2":"2026-06-30","2026-Q3":"2026-09-30",
}
TWO=Decimal("0.01")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def number(value):
    if isinstance(value,bool):
        raise ValueError("Boolean is not a financial number")
    x=Decimal(str(value))
    if not x.is_finite():
        raise ValueError("Nonfinite original SEC value")
    return x


def money(value):
    return str(number(value).quantize(TWO,rounding=ROUND_HALF_UP))


def _day(value):
    return dt.date.fromisoformat(value)


def _sec_gate(url,filed,available,*,cutoff):
    if not isinstance(url,str) or not url.startswith("https://www.sec.gov/Archives/edgar/data/"):
        raise ValueError("Official original SEC document URL required")
    if _day(available) != _day(filed)+dt.timedelta(days=14):
        raise ValueError("Original SEC legacy +14-day source date mismatch")
    if _day(filed)>cutoff or _day(available)>cutoff:
        return False
    return True


def _record(period,issuer,cfo,ppe,source_records,*,cutoff):
    if period not in QUARTER_END or issuer not in ISSUERS:
        raise ValueError("Unrecognized quarter or issuer")
    cfo,ppe=number(cfo),number(ppe)
    if cfo < 0 or ppe < 0:
        raise ValueError("Negative original 4-hyperscaler operating cash or cash PPE")
    if not source_records or not all(isinstance(x,dict) for x in source_records):
        raise ValueError("Missing direct SEC filing provenance")
    for src in source_records:
        if not _sec_gate(src["url"],src["filed"],src["available"],cutoff=cutoff):
            raise ValueError("Source not yet eligible by research cutoff")
    eligible=max(src["available"] for src in source_records)
    return {
        "period":period,"quarter_end":QUARTER_END[period],
        "issuer":issuer,"ocf_usd_m":str(cfo),
        "gross_cash_ppe_usd_m":str(ppe),"cash_gap_usd_m":str(cfo-ppe),
        "cash_ppe_gt_cfo":ppe>cfo,
        "cash_ppe_over_ocf_pct":money(100*ppe/cfo) if cfo>0 else None,
        "first_complete_source_eligible_at_sec_plus14":eligible,
        "original_sec_sources":source_records,
        "independent_historical_provider_receipt_attested":False,
        "gpu_or_ai_specific_spend_identified":False,
    }


def build(y2025,q4,q2,q3,*,q1=None,as_of=None):
    as_of=as_of or dt.datetime.now(dt.timezone.utc).date()
    if isinstance(as_of,str):as_of=_day(as_of)
    if not isinstance(as_of,dt.date) or isinstance(as_of,dt.datetime):
        raise ValueError("Research as-of should be calendar date")
    if (
        y2025.get("schema")!="aics-hyperscalers-2025-q1-q3-original-sec-quarterly-cash-gap-v1"
        or y2025.get("flags",{}).get("independently_historically_pit_attested") is not False
        or y2025.get("flags",{}).get("original_sec_html_bytes_independently_rehashed") is not False
        or q4.get("schema")!="aics-hyperscalers-2025q4-original-sec-first-release-cashgap-v1"
        or q4.get("integrity",{}).get("historical_first_delivery_provider_pit_attested") is not False
        or q4.get("observation_quarter")!="2025-Q4"
        or q2.get("quarter_end")!="2026-06-30"
        or q3.get("quarter_ends")!=["2025-09-30","2026-09-30"]
        or q3.get("available_at")!="2026-11-13"
        or sum(WEIGHTS.values())!=1050
    ):
        raise ValueError("Unverified, rewritten or mismatched original SEC source ledger")
    rows=[]
    lookups={}
    for r in y2025["issuer_quarters"]:
        p,issuer=r["period"],r["issuer"]
        if p not in ("2025-Q1","2025-Q2","2025-Q3"):
            raise ValueError("Unexpected extra original 2025 quarter")
        if (p,issuer) in lookups:
            raise ValueError("Repeated issuer-quarter")
        source_objects=[y2025["sources"][s] for s in r["source_ids"]]
        refs=[{"url":x["source_url"],"filed":x["filed_at"],"available":x["available_at"],"accession":x["accession"]}
              for x in source_objects]
        eligible=max(x["available"] for x in refs)
        if eligible!=r["eligible_at"]:
            raise ValueError("Issuer direct quarter source eligibility mismatch")
        if any(_day(x["filed"])>as_of or _day(x["available"])>as_of for x in refs):
            continue
        row=_record(p,issuer,r["operating_cash_usd_m"],r["cash_ppe_usd_m"],refs,cutoff=as_of)
        if number(row["cash_gap_usd_m"])!=number(r["ocf_minus_cash_ppe_usd_m"]):
            raise ValueError("Original 2025 quarter cash flow arithmetic mismatch")
        rows.append(row);lookups[(p,issuer)]=row
    if len(y2025["issuer_quarters"])!=12:
        raise ValueError("Original 2025 Q1-Q3 roster must have 12 issuer-quarter rows")
    if len(q4["issuer_rows"])!=4 or {r["issuer"] for r in q4["issuer_rows"]}!=ISSUERS:
        raise ValueError("Original Q4 2025 four issuer panel missing")
    for r in q4["issuer_rows"]:
        if _day(r["available_at"])>as_of:continue
        refs=[{"url":r["original_sec_url"],"filed":r["filed_at"],
               "available":r["available_at"],"accession":r["accession"]}]
        row=_record("2025-Q4",r["issuer"],r["cfo"],r["ppe"],refs,cutoff=as_of)
        if number(row["cash_gap_usd_m"])!=number(r["cash_gap_usd_m"]):
            raise ValueError("Original Q4 gap mismatch")
        rows.append(row);lookups[(row["period"],row["issuer"])]=row
    if q1 is not None:
        if (
            q1.get("schema")!="aics-hyperscalers-2026q1-original-sec-first-release-cashgap-v1"
            or q1.get("observation_quarter")!="2026-Q1"
            or q1.get("period_end")!=QUARTER_END["2026-Q1"]
            or q1.get("unit")!="USD million"
            or q1.get("integrity",{}).get("direct_3month_cash_flow_columns") is not True
            or q1.get("integrity",{}).get("raw_source_bytes_independently_rehashed") is not False
            or q1.get("integrity",{}).get("historical_first_delivery_provider_pit_attested") is not False
            or q1.get("integrity",{}).get("production_score_approved") is not False
            or q1.get("integrity",{}).get("trades_created") is not False
            or len(q1.get("issuer_rows",[]))!=4
            or {r["issuer"] for r in q1["issuer_rows"]}!=ISSUERS
            or len(q1["issuer_rows"])!=len({r["issuer"] for r in q1["issuer_rows"]})
            or set(q1.get("issuers",[]))!=ISSUERS
        ):
            raise ValueError("Unverified or incomplete first-filed 2026 Q1 SEC source ledger")
        expected_cik={"Microsoft":"789019","Amazon":"1018724","Alphabet":"1652044","Meta":"1326801"}
        q1_cfo,q1_ppe=Decimal(0),Decimal(0)
        q1_gaps=[]
        for r in q1["issuer_rows"]:
            issuer=r["issuer"]
            cik=str(int(r["cik"])) if str(r["cik"]).isdigit() else None
            accession=r["accession"]
            prefix=("https://www.sec.gov/Archives/edgar/data/"
                    +expected_cik[issuer]+"/"+accession.replace("-","")+"/")
            if (
                cik!=expected_cik[issuer]
                or r.get("period")!="2026-Q1"
                or r.get("period_end")!="2026-03-31"
                or r.get("filed_at")!="2026-04-29"
                or r.get("available_at")!="2026-05-13"
                or r.get("form") not in ("10-Q","8-K EX-99.1")
                or not isinstance(r.get("source_file"),str)
                or r.get("source_url")!=prefix+r["source_file"]
                or r.get("index_url")!=prefix+accession+"-index.htm"
                or r.get("original_document_bytes_sha256") is not None
                or r.get("retrospective_source_retrieval_not_historical_provider_receipt") is not True
            ):
                raise ValueError("Incorrect 2026 Q1 SEC identity, date or first-filing lineage")
            refs=[{"url":r["source_url"],"filed":r["filed_at"],
                   "available":r["available_at"],"accession":accession}]
            cfo,ppe=number(r["ocf"]),number(r["ppe"])
            if cfo<0 or ppe<0 or cfo-ppe!=number(r["cash_gap_usd_m"]):
                raise ValueError("2026 Q1 direct statement values do not reconcile")
            q1_cfo+=cfo;q1_ppe+=ppe
            if ppe>cfo:q1_gaps.append(issuer)
            if _day(r["available_at"])<=as_of:
                row=_record("2026-Q1",issuer,cfo,ppe,refs,cutoff=as_of)
                rows.append(row);lookups[(row["period"],row["issuer"])]=row
        totals=q1.get("totals",{})
        if (
            number(totals.get("ocf_usd_m"))!=q1_cfo
            or number(totals.get("cash_ppe_usd_m"))!=q1_ppe
            or number(totals.get("cash_gap_usd_m"))!=q1_cfo-q1_ppe
            or number(totals.get("cash_ppe_over_ocf_pct"))!=number(money(100*q1_ppe/q1_cfo))
            or totals.get("first_all_four_research_eligible_at")!="2026-05-13"
            or sorted(totals.get("negative_issuer_gap",[]))!=sorted(q1_gaps)
        ):
            raise ValueError("2026 Q1 original four-issuer cohort amounts do not reconcile")
    if len(q2["rows"])!=4 or {r["issuer"] for r in q2["rows"]}!=ISSUERS:
        raise ValueError("Original 2026 Q2 roster missing")
    for r in q2["rows"]:
        if _day(r["available_at"])>as_of:continue
        refs=[{"url":r["source"],"filed":r["filed_at"],"available":r["available_at"]}]
        row=_record("2026-Q2",r["issuer"],r["ocf"],r["ppe"],refs,cutoff=as_of)
        if number(row["cash_gap_usd_m"])!=number(r["gap"]):
            raise ValueError("Original Q2 gap mismatch")
        rows.append(row);lookups[(row["period"],row["issuer"])]=row
    if len(q3["rows"])!=4 or {r["issuer"] for r in q3["rows"]}!=ISSUERS:
        raise ValueError("Original 2026 Q3 roster missing")
    for r in q3["rows"]:
        if _day(r["available_at"])>as_of:continue
        refs=[{"url":r["source"],"filed":(_day(r["available_at"])-dt.timedelta(days=14)).isoformat(),
               "available":r["available_at"]}]
        row=_record("2026-Q3",r["issuer"],
                    r["current"]["operating_cash_flow"],r["current"]["cash_ppe"],refs,cutoff=as_of)
        if number(row["cash_gap_usd_m"])!=number(r["current"]["ocf_less_cash_ppe"]):
            raise ValueError("Original Q3 gap mismatch")
        prior=lookups.get(("2025-Q3",r["issuer"]))
        if prior is not None and (
            number(prior["ocf_usd_m"])!=number(r["prior"]["operating_cash_flow"])
            or number(prior["gross_cash_ppe_usd_m"])!=number(r["prior"]["cash_ppe"])):
            raise ValueError("2025-2026 original same-issuer YoY source mismatch")
        rows.append(row);lookups[(row["period"],row["issuer"])]=row
    if len({(r["period"],r["issuer"]) for r in rows})!=len(rows):
        raise ValueError("Duplicate issuer-quarter after source combination")
    periods=[]
    for period in WANTED:
        eligible=[r for r in rows if r["period"]==period]
        if not eligible:continue
        group={"period":period,"source_eligible_at":max(x["first_complete_source_eligible_at_sec_plus14"] for x in eligible),
               "issuer_count":len(eligible),"four_issuer_complete":len(eligible)==4,
               "missing_issuers":sorted(ISSUERS-set(x["issuer"] for x in eligible)),
               "observed_negative_cash_gap_issuers":sorted(x["issuer"] for x in eligible if x["cash_ppe_gt_cfo"]),
               "cash_outflow_measure":"consolidated_gross_cash_ppe_not_AI_specific"}
        if len(eligible)==4:
            cfo=sum((number(x["ocf_usd_m"]) for x in eligible),Decimal(0))
            ppe=sum((number(x["gross_cash_ppe_usd_m"]) for x in eligible),Decimal(0))
            group.update({"four_issuer_ocf_usd_m":str(cfo),
                          "four_issuer_cash_ppe_usd_m":str(ppe),
                          "four_issuer_cash_gap_usd_m":str(cfo-ppe),
                          "cash_ppe_over_ocf_pct":money(100*ppe/cfo) if cfo>0 else None,
                          "cash_gap_negative":ppe>cfo,
                          "cash_gap_negative_is_proof_of_bank_borrowing":False})
        else:
            group.update({"four_issuer_ocf_usd_m":None,
                          "four_issuer_cash_ppe_usd_m":None,
                          "four_issuer_cash_gap_usd_m":None,
                          "cash_ppe_over_ocf_pct":None,
                          "cash_gap_negative":None,
                          "cash_gap_negative_is_proof_of_bank_borrowing":False})
        periods.append(group)
    lookup={x["period"]:x for x in periods}
    y2025q3=lookup.get("2025-Q3")
    y2026q3=lookup.get("2026-Q3")
    yoy=None
    if y2025q3 and y2026q3 and y2025q3["four_issuer_complete"] and y2026q3["four_issuer_complete"]:
        prior_ocf=number(y2025q3["four_issuer_ocf_usd_m"])
        prior_ppe=number(y2025q3["four_issuer_cash_ppe_usd_m"])
        cur_ocf=number(y2026q3["four_issuer_ocf_usd_m"])
        cur_ppe=number(y2026q3["four_issuer_cash_ppe_usd_m"])
        yoy={
            "comparison":"2026-Q3_versus_2025-Q3_same_four_issuers",
            "asof_after_all_four_2026_original_sec_plus14":y2026q3["source_eligible_at"],
            "cash_ppe_growth_pct":money((cur_ppe/prior_ppe-1)*100),
            "operating_cash_growth_pct":money((cur_ocf/prior_ocf-1)*100),
            "cash_ppe_over_ocf_change_percentage_points":
                money(number(y2026q3["cash_ppe_over_ocf_pct"])-number(y2025q3["cash_ppe_over_ocf_pct"])),
            "cash_gap_deterioration_usd_m":str((cur_ocf-cur_ppe)-(prior_ocf-prior_ppe)),
            "negative_gap_issuer_count_change":len(y2026q3["observed_negative_cash_gap_issuers"])-len(y2025q3["observed_negative_cash_gap_issuers"]),
            "issuer_list_identical":True,
            "measure_is_not_total_ai_capex":True,
            "cash_gap_is_not_proof_of_excess_debt":True,
        }
    return {
        "schema":"aics-precrisis-four-hyperscaler-source-gated-cash-imbalance-research-v1",
        "as_of":as_of.isoformat(),"objective":"early_imbalance_before_observed_funding_distress",
        "economic_issuer_count":4,"fixed_original_aics_node_weights_total":1050,
        "extra_index_node_created":False,
        "source_ledger_files":[str(x) for x in ((Y2025,Q42025,Q12026,Q22026,Q32026) if q1 is not None else (Y2025,Q42025,Q22026,Q32026))],
        "quarterly_original_issuer_records":rows,
        "complete_or_partial_quarters":periods,
        "missing_quarters_not_imputed":["2026-Q1"] if q1 is None else [],
        "same_issuer_yoy_q3":yoy,
        "primary_source_document_bytes_independently_historical_pit_attested":False,
        "precrisis_crisis_prediction_probability":None,
        "similarity_to_2000_pct":None,"similarity_to_2008_pct":None,
        "contagion_2008_recourse_or_repo_ever_proven":False,
        "separate_imbalance_layer_not_aics_score":True,
        "2026_10_30_marketclose_q3_2026_available":False,
        "full_11_node_aics":None,"historical_oos_predictive_skill":None,
        "production_weight_change":False,"trading":False,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=OUTPUT)
    parser.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    args=parser.parse_args()
    result=build(read(Y2025),read(Q42025),read(Q22026),read(Q32026),q1=read(Q12026),as_of=args.as_of)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "asof":result["as_of"],"eligible_quarters":[x["period"] for x in result["complete_or_partial_quarters"]],
        "original_issuer_quarters":len(result["quarterly_original_issuer_records"]),
        "yoy":result["same_issuer_yoy_q3"],"precrisis_risk_probability":None,
        "new_production_score":None,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
