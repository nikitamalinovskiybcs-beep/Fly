"""Versioned multi-node research-first publication-date overlay for AICS.

Parallel research-only comparison. Reconstruct from immutable legacy source
events + actual original filing metadata, never by blindly subtracting 13
days. Date-only original SEC filings => next calendar day eligibility proxy.
Provides BOTH calendar-month-end and last-weekday-proxy market close views.
A weekday proxy is NOT an independently verified exchange calendar or public
dissemination timestamp; no historical investable signals are inferred.
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_publication_policy import research_eligibility
from scripts.aics_score_reproducibility_gate import WEIGHTS

ROOT = Path("aics_data/research")
SOURCE = ROOT / "aics_24_month_no_multiplier_coverage_2026-11-21.json"
OUTPUT = ROOT / "aics_24m_multi_node_publication_overlay_2026-11-21.json"
CENT = Decimal("0.01")
SEC_NODES = {"Insurers", "Neoclouds", "Hyperscalers", "AI Demand", "SPV"}
MONTHS = 24


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def quant(x):
    return str(Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP))


def day(value):
    return dt.date.fromisoformat(value)


def filed_source(file_date, old_available, url):
    if (day(file_date) + dt.timedelta(days=14)).isoformat() != old_available:
        raise ValueError("SEC+14 original source date mismatched")
    if not isinstance(url, str) or not url.startswith("https://www.sec.gov/Archives/"):
        raise ValueError("Expected named original SEC archive source")
    return {"filed_at":file_date, "source_url":url}


def shift(original, sources):
    if not sources:
        raise ValueError("Cannot shift an event with no verified SEC origins")
    return max(research_eligibility(
        source_url=x["source_url"], filed_at=x["filed_at"],
        public_date=x["filed_at"]).eligible_date for x in sources)


def register(updates, event, sources):
    key = (event["node"], event["available_at"], event["score"])
    if key in updates:
        raise ValueError("Ambiguous duplicate original SEC event")
    updates[key] = {"research_eligible_date":shift(event, sources),
                    "source_count":len(sources), "source_policy":"verified_original_sec_filed_date_plus_one_calendar_day_proxy",
                    "original_sec_sources":sources}


def _base_event(events, node, date, score):
    found = [x for x in events
             if x["node"] == node and x["available_at"] == date
             and x["score"] == str(score)]
    if len(found) != 1:
        raise ValueError("Original 24M SEC event not uniquely matched: " +
                         str((node,date,score,len(found))))
    return found[0]


def source_updates(events):
    updates = {}
    pru = read("pru_insurers_nonaccrual_original_quarters_2025_2026.json")
    for r in pru["events"]:
        base = _base_event(events,"Insurers",r["available_at"],r["score_pct"])
        # Some original 10-Q numeric documents are SEC accession mirrors on
        # the Prudential investor site; use the independently listed SEC
        # filing accession index to anchor its exact filing date.
        index = r.get("source_index") or (
            "https://www.sec.gov/Archives/edgar/data/" +
            str(r["cik"]) + "/" + r["accession"].replace("-","") +
            "/" + r["accession"] + "-index.htm")
        register(updates,base,[filed_source(
            r["filed_at"],r["available_at"],index)])

    neo = read("neoclouds_2025_q1_q3_sec_cashflow_research_2026-11-21.json")
    roster = {"2025-Q1":("crwv_q1","nbis_q1"),
              "2025-Q2":("crwv_h1","nbis_q2"),
              "2025-Q3":("crwv_9m","nbis_9m")}
    for r in neo["observations"]:
        originals=[neo["sources"][k] for k in roster[r["period"]]]
        base = _base_event(events,"Neoclouds",r["available_at"],r["score"])
        register(updates,base,[filed_source(x["filed_at"],x["available_at"],x["source_page"])
                               for x in originals])
    neo4 = read("neoclouds_2025_q4_sec_original_cashflow_2026-11-21.json")
    base = _base_event(events,"Neoclouds",
                       neo4["measurement"]["joint_first_sec_eligible_at"],
                       neo4["measurement"]["score_0_100"])
    register(updates,base,[filed_source(x["filed_at"],x["available_at"],x["source_page"])
                           for x in neo4["sources"].values()])

    # 2026 neocloud earnings and SPV facilities reference original
    # fixed SEC accession registry. Every required original/cross-check
    # remains mandatory for this original historical scoring formula.
    neo26 = read("neocloud_cash_coverage_2026_h1.json")
    registry = json.loads(Path("aics_data/source_registry/neocloud_cash_h1_sec.json")
                          .read_text(encoding="utf-8"))
    for quarter in ("2026-Q1","2026-Q2"):
        matched = [r for r in neo26["observations"] if r["period"] == quarter]
        if len(matched) != 2 or {r["issuer"] for r in matched} != {"CoreWeave","Nebius"}:
            raise ValueError("Two actual 2026 cloud issuers required")
        original_keys = set()
        for row in matched:
            original_keys.add(row["source"])
            original_keys.update(row["cross_checks"])
        originals=[registry[k] for k in sorted(original_keys)]
        old_date=max(row["all_cited_checks_available"] for row in matched)
        base=[e for e in events if e["node"]=="Neoclouds"
              and e["available_at"]==old_date]
        if len(base)!=1:
            raise ValueError("2026 Neocloud event not uniquely matched")
        register(updates,base[0],[filed_source(x["filed_at"],x["available_at"],
                                               x["source_page"]) for x in originals])
    facility = neo26["coreweave_facilities"]
    original = registry[facility["source"]]
    base = [x for x in events if x["node"]=="SPV" and
            x["available_at"]==facility["available_at"]]
    if len(base)!=1:
        raise ValueError("SPV original not uniquely matched")
    register(updates,base[0],[filed_source(
        original["filed_at"],original["available_at"],original["source_page"])])

    # Broadcom forecast-miss events already have matching original current
    # and prior filings; both must be available to calculate the same score.
    demand0 = read("broadcom_ai_demand_2025q2_strict_lower_bound_sec_2026-11-21.json")
    base = _base_event(events,"AI Demand",
                       demand0["deduction"]["joint_source_first_available_at"],
                       demand0["deduction"]["score"])
    register(updates,base,[filed_source(x["filed_at"],x["available_at"],x["source_url"])
                           for x in (demand0["prior_guidance_filing"],demand0["actual_filing"])])
    demand1 = read("broadcom_ai_demand_2025q3_2026q2_original_sec_guidance_2026-11-21.json")
    by_period={x["period"]:x for x in demand1["filings"]}
    for r in demand1["observations"]:
        curr=by_period[r["period"]]
        prev=by_period[r["previous_forecast_from_period"]]
        base=_base_event(events,"AI Demand",r["available_at"],r["score"])
        register(updates,base,[filed_source(x["filed_at"],x["available_at"],
                                            x["original_sec_exhibit_url"])
                               for x in (prev,curr)])
    demand2=read("broadcom_ai_semiconductor_revenue_2026_q2_q3.json")
    previous,current=demand2["records"]
    base=[x for x in events if x["node"]=="AI Demand"
          and x["available_at"]==current["available_at"]]
    if len(base)!=1:
        raise ValueError("2026 Q3 AI Demand event not uniquely matched")
    register(updates,base[0],[filed_source(x["filed_at"],x["available_at"],x["source"])
                              for x in (previous,current)])

    # Four-issuer 2026 Hyperscalers originals. For 2026Q3, independent
    # 2026 same-quarter cash-PP&E ledger holds original filed_at, verified
    # against operating cash-flow panel, no 2025 comparative lookahead.
    hyp2=read("hyperscalers_cash_coverage_june_to_september_2026.json")
    hyp3=read("hyperscalers_operating_cash_flow_coverage_2026_q3.json")
    hyp3src=read("hyperscalers_cash_ppe_september_quarter_2026.json")
    hyp3by={x["issuer"]:x for x in hyp3src["rows"]}
    for h, orig_rows, original_date in (
        (hyp2,hyp2["rows"],hyp2["available_at"]),
        (hyp3,hyp3["rows"],hyp3["available_at"])):
        base=[x for x in events if x["node"]=="Hyperscalers"
              and x["available_at"]==original_date]
        if len(base)!=1 or len(orig_rows)!=4:
            raise ValueError("2026 Hyperscalers 4-issuer source incomplete")
        sources=[]
        for row in orig_rows:
            if h is hyp2:
                sources.append(filed_source(row["filed_at"],row["available_at"],row["source"]))
            else:
                cite=hyp3by[row["issuer"]]
                if (cite["available_at"]!=row["available_at"]
                        or cite["source"]!=row["source"]):
                    raise ValueError("2026Q3 cash flow and original SEC cash PP&E differ")
                sources.append(filed_source(cite["filed_at"],cite["available_at"],cite["source"]))
        register(updates,base[0],sources)
    return updates


def _hyperscaler_2025_new():
    # One extra time series, not an invented score: source PP&E and OCF
    # in 2025 originals, exactly as in the existing dedicated overlay.
    previous=read("aics_24m_hyperscalers_research_first_public_overlay_2026-11-21.json")
    if previous["months"]!=24 or previous["source_timestamp_pit_attested"] is not False:
        raise ValueError("2025 original source research overlay invalid")
    events=[]
    for q in previous["research_events"]:
        if q["candidate_gap_score"]!="0.00" or q["original_public_time_verified"] is not False:
            raise ValueError("Unapproved 2025 score / timestamp change")
        events.append({
            "node":"Hyperscalers",
            "available_at":q["legacy_first_eligible_plus14"],
            "score":q["candidate_gap_score"],
            "source":"aics_data/research/aics_24m_hyperscalers_research_first_public_overlay_2026-11-21.json",
            "measurement":q["quarter"]+" first-original cash funding 4 issuers",
            "note":"Original four-issuer 2025 SEC data; research-only post-filing next-calendar-day proxy",
            "research_eligible_date":q["research_first_eligible_date_proxy"],
            "source_policy":"verified_original_sec_filed_date_plus_one_calendar_day_proxy",
            "source_count":q["original_source_count"],
            "historical_pit_certified":False,
            "new_candidate_2025":True,
        })
    return events


def last_weekday_proxy(month_end):
    date=month_end
    while date.weekday()>=5:
        date-=dt.timedelta(days=1)
    return date


def _summarize(month, cutoff, events, weights):
    eligible=[(i,e) for i,e in enumerate(events)
              if day(e["research_eligible_date"])<=cutoff]
    latest={}
    for i,e in sorted(eligible,key=lambda x:(x[1]["research_eligible_date"],x[0])):
        latest[e["node"]]=e
    known=sorted(latest)
    partial=sum((Decimal(weights[n])*Decimal(latest[n]["score"])/100
                 for n in known),Decimal(0))
    return {
        "month":month,
        "cutoff_date":cutoff.isoformat(),
        "known_node_count":len(known),
        "known_weight":sum(weights[n] for n in known),
        "missing_nodes":sorted(set(weights)-set(known)),
        "partial_weighted_points_not_full_aics":quant(partial) if known else None,
        "hyperscalers_source":latest.get("Hyperscalers",{}).get("measurement"),
        "node_scores":{n:{"score":latest[n]["score"],
                          "research_eligible_date":latest[n]["research_eligible_date"],
                          "source_policy":latest[n]["source_policy"]}
                       for n in known},
        "full_aics":None,
        "aics_sp500_spread":None,
        "historical_pit_certified":False,
    }


def build():
    old=read("aics_24_month_no_multiplier_coverage_2026-11-21.json")
    if (old["month_count"]!=24 or old["node_weights_total"]!=1050
            or old["new_11_node_full_aics_months"]!=0
            or old["new_11_node_sp500_spread_months"]!=0
            or old["certified_aics"] is not None
            or len(WEIGHTS)!=11 or sum(WEIGHTS.values())!=1050):
        raise ValueError("Attempt to use certified or non-24m original")
    base=old["score_source_events"]
    updates=source_updates(base)
    events=[]
    for e in base:
        k=(e["node"],e["available_at"],e["score"])
        upgraded=updates.get(k)
        x=dict(e)
        x["research_eligible_date"]=(upgraded["research_eligible_date"]
                                    if upgraded else e["available_at"])
        x["source_policy"]=(upgraded["source_policy"]
                            if upgraded else "preserved_baseline_non_sec_or_unverified")
        x["source_count"]=upgraded["source_count"] if upgraded else None
        x["independently_original_public_timestamp_verified"]=False
        x["historical_pit_certified"]=False
        events.append(x)
    events.extend(_hyperscaler_2025_new())
    if len(events)!=len(base)+4 or len(updates)<20:
        raise ValueError("SEC migration too incomplete for production")
    calendar_rows=[]
    weekday_rows=[]
    for row in old["monthly"]:
        y,m=(int(p) for p in row["month"].split("-"))
        cutoff=dt.date(y,m,calendar.monthrange(y,m)[1])
        calendar_rows.append(_summarize(row["month"],cutoff,events,WEIGHTS))
        weekday_rows.append(_summarize(row["month"],last_weekday_proxy(cutoff),events,WEIGHTS))
    n=24*1050
    weights=sum(row["known_weight"] for row in calendar_rows)
    weekday_weights=sum(row["known_weight"] for row in weekday_rows)
    baseline_weight=sum(sum(WEIGHTS[n] for n in row["latest_eligible_research_scores"])
                        for row in old["monthly"])
    return {
        "schema":"aics-24m-multi-node-first-public-date-research-overlay-v1",
        "window":old["window"],
        "asof_research":"2026-11-21",
        "node_weights":dict(WEIGHTS),
        "source_events":events,
        "converted_existing_sec_events":len(updates),
        "preserved_legacy_or_nonsec_events":len(base)-len(updates),
        "new_original_2025_hyperscaler_events":4,
        "baseline_source_weight_months":baseline_weight,
        "baseline_research_coverage_pct":quant(100*Decimal(baseline_weight)/Decimal(n)),
        "new_calendar_end_research_weight_months":weights,
        "new_calendar_end_research_coverage_pct":quant(100*Decimal(weights)/Decimal(n)),
        "new_last_weekday_proxy_weight_months":weekday_weights,
        "new_last_weekday_proxy_coverage_pct":quant(100*Decimal(weekday_weights)/Decimal(n)),
        "monthly_calendar_end_research":calendar_rows,
        "monthly_last_weekday_market_proxy":weekday_rows,
        "weekend_month_end_rule":"Last weekday, NOT independently proven NYSE holiday/session calendar or price-bar timestamp",
        "date_only_sec_rule":"next_calendar_day_after_original_file_date; no original exact dissemination timestamp",
        "do_not_conflate_calendar_month_end_with_sp500_last_close":True,
        "independently_historical_pit_attested":False,
        "independently_oos_24m":False,
        "complete_11_node_aics_months":0,
        "aics_sp500_spread_months":0,
        "production_change":False,
        "trades_created":False,
    }


if __name__=="__main__":
    print(json.dumps(build(),indent=2,ensure_ascii=False))
