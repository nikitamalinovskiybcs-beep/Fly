"""AICS V18: original 2024Q2-2026Q1 3-BDC nonaccrual-cost research overlay.

Replays first-original 8 issuer quarters, 7 source-eligible quarterly breadth
events, and separately merges ONLY absent Private Credit research node
observability into the immutable V17 incomplete 24-month panels.

The 2026 scoring rule is RETROSPECTIVELY APPLIED to earlier filings, so
this is not pre-registered model history or an investment-grade AICS.
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS

ROOT=Path("aics_data/research")
SRC=ROOT/"private_credit_2024q2_2026q1_first_sec_cost_breadth_2026-11-22.json"
V17=ROOT/"aics_24m_multi_node_publication_overlay_2026-11-21.json"
OUT=ROOT/"aics_v18_private_credit_24m_pit_proxy_overlay_2026-11-22.json"
CENT=Decimal("0.01")
ISSUERS={"ARCC","BXSL","OBDC"}
Q=("2024-Q2","2024-Q3","2024-Q4","2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q1")


def _date(value):
    return dt.date.fromisoformat(value)


def _round(x):
    return str(Decimal(str(x)).quantize(CENT,rounding=ROUND_HALF_UP))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def source_events(ledger):
    if (ledger.get("schema")!="aics-private-credit-2024q2-2026q1-8quarter-original-sec-cost-breadth-expost-v1"
            or ledger.get("node")!="Private Credit" or ledger.get("weight")!=150
            or ledger.get("weight_total")!=1050
            or ledger.get("quarter_roster")!=list(Q)
            or ledger.get("provenance",{}).get("pre_registered_2024_formula") is not False
            or ledger.get("not_computed",{}).get("production_private_credit_score") is not None):
        raise ValueError("Wrong or falsely certified Private Credit original receipt")
    originals=ledger["original_issuer_quarter_observations"]
    if len(originals)!=24:
        raise ValueError("Exactly 3 issuers by 8 quarters required")
    quarters={}
    for q in Q:
        rs=[r for r in originals if r["quarter"]==q]
        if len(rs)!=3 or {r["issuer"] for r in rs}!=ISSUERS:
            raise ValueError("Missing or duplicated issuer-quarter: "+q)
        for r in rs:
            filed=_date(r["filed_at"])
            if (_date(r["research_available_date_only_proxy"])!=filed+dt.timedelta(days=1)
                or _date(r["legacy_sec_plus14_available_at"])!=filed+dt.timedelta(days=14)
                or not r["original_numeric_source_url"].startswith(
                    "https://www.sec.gov/Archives/edgar/data/")
                or not r["original_sec_filing_index_url"].startswith(
                    "https://www.sec.gov/Archives/edgar/data/")
                or r["cik"]!={"ARCC":"1287750","BXSL":"1736035","OBDC":"1655888"}[r["issuer"]]):
                raise ValueError("Missing original issuer or source timing")
            val=Decimal(r["nonaccrual_amortized_cost_pct"])
            if not 0<=val<=100 or not val.is_finite():
                raise ValueError("Invalid issuer nonaccrual cost percentage")
            debt_table=r.get("original_debt_cost_table_usd_thousands")
            if debt_table is not None:
                if r["issuer"]!="OBDC" or q not in ("2025-Q1","2025-Q2","2025-Q3"):
                    raise ValueError("Unexpected statement number source")
                if (debt_table["performing"]+debt_table["non_accrual"]!=debt_table["total"]
                    or debt_table["non_accrual"]<0
                    or debt_table["performing"]<0
                    or debt_table["total"]<=0):
                    raise ValueError("Invalid original nonaccrual debt totals")
                rounded_one=Decimal(100*debt_table["non_accrual"]/debt_table["total"]).quantize(
                    Decimal("0.1"),rounding=ROUND_HALF_UP)
                if rounded_one!=val:
                    raise ValueError("Original 2025 OBDC amount versus 1-decimal table mismatch")
        quarters[q]={r["issuer"]:r for r in rs}
    out=[]
    for p,c in zip(Q[:-1],Q[1:]):
        prior,now=quarters[p],quarters[c]
        worsening=sorted(k for k in ISSUERS if Decimal(now[k]["nonaccrual_amortized_cost_pct"])>
                         Decimal(prior[k]["nonaccrual_amortized_cost_pct"]))
        improving=sorted(k for k in ISSUERS if Decimal(now[k]["nonaccrual_amortized_cost_pct"])<
                         Decimal(prior[k]["nonaccrual_amortized_cost_pct"]))
        unchanged=sorted(ISSUERS-set(worsening)-set(improving))
        available=max(r["research_available_date_only_proxy"] for r in now.values())
        legacy=max(r["legacy_sec_plus14_available_at"] for r in now.values())
        score=_round(Decimal(100)*len(worsening)/3)
        declared=ledger["source_event_breadth_series"][len(out)]
        if (declared["quarter"]!=c or declared["previous_quarter"]!=p
            or declared["available_at_source_date_plus1_proxy"]!=available
            or declared["legacy_sec_plus14_eligible_at"]!=legacy
            or declared["worsening_issuers"]!=worsening
            or declared["improving_issuers"]!=improving
            or declared["unchanged_issuers"]!=unchanged
            or declared["score_0_100_descriptive_2026_formula_applied_ex_post"]!=score):
            raise ValueError("Source-to-score drift: "+c)
        out.append({"node":"Private Credit","quarter":c,"previous_quarter":p,
                    "research_available_at_proxy":available,
                    "legacy_sec_plus14_available_at":legacy,
                    "score":score,"worsening_issuers":worsening,
                    "improving_issuers":improving,"unchanged_issuers":unchanged,
                    "issuer_source_provenance":{k:now[k]["original_numeric_source_url"]
                                                for k in sorted(ISSUERS)},
                    "historically_contemporaneous_pit_attested":False,
                    "pre_registered_historical_formula":False})
    if len(out)!=7 or len(ledger["source_event_breadth_series"])!=7:
        raise ValueError("Seven contiguous quarters required")
    return out


def _run_overlay(v17,events,key):
    old=v17[key]
    if len(old)!=24:
        raise ValueError("No complete 24-month source calendar")
    result=[]
    new_weight_months=0
    for row in old:
        y,m=(int(x) for x in row["month"].split("-"))
        cutoff=_date(row["cutoff_date"])
        end=dt.date(y,m,calendar.monthrange(y,m)[1])
        if cutoff>end or cutoff<dt.date(y,m,1) or row.get("full_aics") is not None:
            raise ValueError("Bad chronology or full AICS promotion")
        prev=sorted((e for e in events if e["research_available_at_proxy"]<=cutoff.isoformat()),
                    key=lambda e:e["research_available_at_proxy"])
        latest=prev[-1] if prev else None
        newrow=dict(row)
        node_scores={k:dict(v) for k,v in row["node_scores"].items()}
        if "Private Credit" not in node_scores and latest is not None:
            age=(cutoff-_date(latest["research_available_at_proxy"])).days
            if age>90:
                # Do not give stale quarterly source a fresh monthly observation.
                newrow["private_credit_unavailable_age_gt90_days"]=True
            else:
                node_scores["Private Credit"]={
                    "score":latest["score"],
                    "research_eligible_date":latest["research_available_at_proxy"],
                    "source_policy":"original_3bdc_cost_direction_expost_2026_formula_dateonly_plus1",
                    "quarter_source":latest["quarter"],
                    "source_age_days":age,
                    "pre_registered_historical_formula":False,
                }
                new_weight_months+=150
        newrow["node_scores"]=dict(sorted(node_scores.items()))
        newrow["known_node_count"]=len(node_scores)
        newrow["known_weight"]=sum(WEIGHTS[n] for n in node_scores)
        newrow["missing_nodes"]=sorted(set(WEIGHTS)-set(node_scores))
        partial=sum((Decimal(WEIGHTS[n])*Decimal(x["score"])/100
                     for n,x in node_scores.items()),Decimal(0))
        newrow["partial_weighted_points_not_full_aics"]=_round(partial) if node_scores else None
        newrow["full_aics"]=None
        newrow["aics_sp500_spread"]=None
        newrow["historical_pit_certified"]=False
        result.append(newrow)
    if result[0]["month"]!="2024-11" or result[-1]["month"]!="2026-10":
        raise ValueError("Invalid 24-month window")
    return result,new_weight_months


def build(ledger=None,v17=None):
    ledger=ledger if ledger is not None else read(SRC)
    v17=v17 if v17 is not None else read(V17)
    if (v17.get("schema")!="aics-24m-multi-node-first-public-date-research-overlay-v1"
        or v17.get("baseline_source_weight_months")!=8075
        or v17.get("new_calendar_end_research_weight_months")!=9675
        or v17.get("new_last_weekday_proxy_weight_months")!=9450
        or v17.get("complete_11_node_aics_months")!=0
        or v17.get("independently_historical_pit_attested") is not False
        or sum(WEIGHTS.values())!=1050):
        raise ValueError("Invalid V17 baseline / weights")
    events=source_events(ledger)
    calendar,extra_calendar=_run_overlay(v17,events,"monthly_calendar_end_research")
    market,extra_market=_run_overlay(v17,events,"monthly_last_weekday_market_proxy")
    n=24*1050
    wc=sum(r["known_weight"] for r in calendar)
    wm=sum(r["known_weight"] for r in market)
    if extra_calendar!=3150 or extra_market!=3150:
        raise ValueError("Unexpected Private Credit source-month coverage; check source ages")
    return {"schema":"aics-v18-24m-private-credit-original-sec-expost-research-overlay-v1",
            "asof":"2026-11-22",
            "underlying":"aics_data/research/aics_24m_multi_node_publication_overlay_2026-11-21.json",
            "new_original_sec_issuer_quarter_records":24,
            "new_research_breadth_events":7,
            "source_events":events,
            "original_v17_calendar_coverage_pct":v17["new_calendar_end_research_coverage_pct"],
            "original_v17_market_weekday_proxy_coverage_pct":v17["new_last_weekday_proxy_coverage_pct"],
            "additional_calendar_source_weight_months":extra_calendar,
            "additional_market_source_weight_months":extra_market,
            "calendar_source_weight_months":wc,
            "market_weekday_proxy_source_weight_months":wm,
            "calendar_research_source_coverage_pct":_round(100*Decimal(wc)/Decimal(n)),
            "market_weekday_proxy_source_coverage_pct":_round(100*Decimal(wm)/Decimal(n)),
            "monthly_calendar_end_research":calendar,
            "monthly_last_weekday_market_proxy":market,
            "no_synthetic_backfill":True,
            "source_events_forward_carry_only_if_within_90_days":True,
            "scores_are_expost_not_preregistered":True,
            "historical_pit_source_bytes_independently_attested":False,
            "full_11node_index_months":0,"aics_sp500_spread_months":0,
            "legacy_source_data_changed":False,"production_index_changed":False,
            "trades_created":False}


if __name__=="__main__":
    print(json.dumps(build(),indent=2,ensure_ascii=False))
