"""AICS PIT100: rebuild 24 monthly research panels under active SEC filed-day policy.

Never silently recycle V17/V18 legacy monthly score panels. Original V17
source-events are re-clocked to their actual original SEC filing dates; BDC
source events are reconstructed from the first original three-company filing
date proxy, not +1/+14. Same-day market-close uses strictly earlier date
when exact SEC acceptance ET is unavailable. Calendar EOD uses filing day
only as unverified date-level research proxy.

This is a descriptive ex-post overlay, not a historically attested PIT index,
nor 24-month untouched OOS. Unavailable nodes remain absent (NOT zero).
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_pit_100_real_cutoff_agents import (
    OVERLAY,CREDIT,OUT as PIT100,source_preflight,read_bytes,
    SEC_LEGACY,date,num,
)
from scripts.aics_pit_100_real_cutoff_agents import REGISTRY,REPO,EQUITIES,TERMS,FUNDING,STATUS

OUT=Path("aics_data/agent_runs/ten_real_collection_rounds/aics_pit100_rebuilt_24m_public_filing_date_panels.json")
HORIZON=90
G17=Path("aics_data/research/fed_g17_naics3344_24_month_original_release_2026-11-21.json")
G17_RELEASE="https://www.federalreserve.gov/releases/g17/20251223/table7.htm"
G17_PERIOD=re.compile(r"^(20[0-9]{2}-(?:0[1-9]|1[0-2])) (?:first-published|initial) Fed G\\.17")


def event_roster(overlay,credit):
    original=read_bytes(G17)
    joint={e["observation_month"]:e for e in original["observations"]
           if e["observation_month"] in ("2025-10","2025-11")}
    if (original["schema"]!="aics-g17-naics3344-first-release-monthly-24-v1"
        or original["independent_historical_pit_certified"] is not False
        or set(joint)!={"2025-10","2025-11"}
        or any(v["official_release_date"]!="2025-12-23"
               or v["source_url"].lower()!=G17_RELEASE.lower() for v in joint.values())
        or {k:num(v["initially_observed_utilization_pct"]) for k,v in joint.items()}!=
           {"2025-10":Decimal("74.7"),"2025-11":Decimal("74.4")}):
        raise ValueError("Original same Fed release contains two distinct measured months")
    roster=[]
    for i,x in enumerate(overlay["source_events"]):
        if x["source_policy"]==SEC_LEGACY:
            filing=(date(x["available_at"])-dt.timedelta(days=14)).isoformat()
            if x["research_eligible_date"]!=(date(filing)+dt.timedelta(days=1)).isoformat():
                raise ValueError("SEC +1 legacy source chronology mismatch")
            source_kind="SEC_FILED_DATE_ONLY"
        elif x["source_policy"]=="preserved_baseline_non_sec_or_unverified":
            filing=x["available_at"]
            source_kind="NONSEC_RELEASE_DATE_ONLY_UNVERIFIED"
        else:
            raise ValueError("Unsupported original source event policy")
        match=G17_PERIOD.match(str(x.get("measurement",""))) if x["node"]=="Semiconductors Supply" else None
        period=match.group(1) if match else None
        if period in joint:
            o=joint[period]
            if filing!=o["official_release_date"] or num(x["score"])!=num(o["initially_observed_utilization_pct"]):
                raise ValueError("Fed G17 date, measured month or numeric original inconsistent")
        roster.append({
            "id":f"V17-{i:03d}","node":x["node"],"score":str(num(x["score"])),
            "observation_month":period,
            "filing_or_release_date":filing,"source_kind":source_kind,
            "original_ledger":x["source"],
            "original_legacy_14day_date":x["available_at"] if source_kind=="SEC_FILED_DATE_ONLY" else None,
            "historical_first_provider_delivery_attested":False,
            "historical_score_formula_preregistered":False,
        })
    for i,x in enumerate(credit["source_events"]):
        filed=(date(x["research_available_at_proxy"])-dt.timedelta(days=1)).isoformat()
        if (date(x["legacy_sec_plus14_available_at"])-date(filed)).days!=14:
            raise ValueError("BDC SEC filing date inconsistent")
        roster.append({
            "id":f"V18-BDC-{i:02d}","node":"Private Credit",
            "score":str(num(x["score"])),"filing_or_release_date":filed,
            "source_kind":"SEC_3BDC_DATE_ONLY_MAX_FILED_PROXY",
            "original_ledger":"aics_data/research/aics_v18_private_credit_24m_pit_proxy_overlay_2026-11-22.json",
            "original_legacy_14day_date":x["legacy_sec_plus14_available_at"],
            "original_quarter":x["quarter"],
            "original_source_urls":x["issuer_source_provenance"],
            "historical_first_provider_delivery_attested":False,
            "historical_score_formula_preregistered":False,
        })
    if len(roster)!=len(overlay["source_events"])+len(credit["source_events"]):
        raise ValueError("Not all historical events re-clocked")
    return roster


def conflicting_same_publication_day_events(roster):
    """Never select an arbitrary later ID for conflicting same-day source values."""
    groups={}
    for event in roster:
        groups.setdefault((event["node"],event["filing_or_release_date"],
                           event.get("observation_month") or event["id"]),[]).append(event)
    quarantine=[]
    for (node,day,period),events in sorted(groups.items()):
        if len({num(e["score"]) for e in events})>1:
            quarantine.append({
                "node":node,"source_public_day_proxy":day,
                "observation_month":period,
                "original_event_ids":[e["id"] for e in events],
                "conflicting_source_scores":[e["score"] for e in events],
                "decision":"QUARANTINE_ALL_CONFLICTING_SAME_DAY_VALUES",
                "original_release_vintage_independently_verified":False,
            })
    return quarantine


def replay(overlay,credit,*,market):
    key="monthly_last_weekday_market_proxy" if market else "monthly_calendar_end_research"
    rows=[]
    roster=event_roster(overlay,credit)
    conflict=conflicting_same_publication_day_events(roster)
    excluded={event_id for entry in conflict for event_id in entry["original_event_ids"]}
    for x in overlay[key]:
        cutoff=date(x["cutoff_date"])
        current={}
        for e in roster:
            if e["id"] in excluded:
                continue
            day=date(e["filing_or_release_date"])
            # Without source intraday timestamp, even non-SEC same-day
            # release cannot be assumed pre-close. No +14 delay.
            if day>=cutoff if market else day>cutoff:
                continue
            if e["node"]=="Private Credit" and e["id"].startswith("V18-BDC-"):
                if (cutoff-day).days>HORIZON:
                    continue
            previous=current.get(e["node"])
            if (previous is None or
                (day,e.get("observation_month") or "",e["id"])>(
                date(previous["filing_or_release_date"]),
                previous.get("observation_month") or "",previous["id"])):
                current[e["node"]]=e
        scores={}
        for node,e in sorted(current.items()):
            if not (Decimal(0)<=num(e["score"])<=Decimal(100)):
                raise ValueError("Research node score outside 0..100")
            scores[node]={
                "research_score_not_PIT_certified":e["score"],
                "original_source_event_id":e["id"],
                "source_filing_or_release_date":e["filing_or_release_date"],
                "source_kind":e["source_kind"],
                "historical_first_delivery_attested":False,
                "formula_preregistered":False,
            }
        known=sum(WEIGHTS[n] for n in scores)
        partial=sum((num(v["research_score_not_PIT_certified"])*WEIGHTS[n]/100
                     for n,v in scores.items()),Decimal(0))
        rows.append({
            "month":x["month"],"cutoff_date":x["cutoff_date"],
            "market_close_time_unverified":market,
            "known_node_count_research_only":len(scores),
            "known_weight_research_only":known,
            "missing_nodes":sorted(set(WEIGHTS)-set(scores)),
            "research_partial_weighted_points_not_full_AICS":
                str(partial.quantize(Decimal(".01"),rounding=ROUND_HALF_UP)),
            "node_scores_rebuilt_from_original_events":scores,
            "full_11node_AICS":None,
            "AICS_SP500_spread":None,
            "historical_PIT_certified":False,
            "independent_OOS_certified":False,
        })
    if len(rows)!=24:
        raise ValueError("Expected exactly 24 actual month cutoffs")
    return rows


def build(overlay,credit,registry,repo,equities,terms,finance,status,pit100):
    source_preflight(overlay,credit,registry,repo,equities,terms,finance,status)
    if (pit100.get("schema")!="aics-100-real-dated-PIT-audit-role-replays-v1"
        or pit100.get("PIT_runs_successfully_computed")!=100
        or pit100.get("SEC_14day_delay_is_active") is not False
        or pit100.get("certified_11_node_AICS") is not None
        or len({r["historical_cutoff"] for r in pit100["100_audit_results"]})!=100):
        raise ValueError("100 source-derived PIT roles must run before rebuilding")
    market=replay(overlay,credit,market=True)
    calendar=replay(overlay,credit,market=False)
    roster=event_roster(overlay,credit)
    conflicts=conflicting_same_publication_day_events(roster)
    if conflicts:
        raise ValueError("Real duplicate same-measurement publication conflict")
    joint=[e for e in roster if e["node"]=="Semiconductors Supply"
           and e["filing_or_release_date"]=="2025-12-23"
           and e.get("observation_month") in ("2025-10","2025-11")]
    if len(joint)!=2:
        raise ValueError("Joint October-November G17 publication not preserved")
    changes={}
    for name,series in (("market",market),("calendar",calendar)):
        legacy=credit["monthly_last_weekday_market_proxy" if name=="market"
                      else "monthly_calendar_end_research"]
        if [r["month"] for r in series]!=[r["month"] for r in legacy]:
            raise ValueError("Mismatched monthly research history")
        diffs=[]
        for x,y in zip(series,legacy):
            old={n:v["score"] for n,v in y["node_scores"].items()}
            new={n:v["research_score_not_PIT_certified"]
                 for n,v in x["node_scores_rebuilt_from_original_events"].items()}
            diffs.append({
                "month":x["month"],
                "newly_present_nodes":sorted(set(new)-set(old)),
                "no_longer_present_nodes":sorted(set(old)-set(new)),
                "changed_research_score_nodes":
                    sorted(n for n in set(old)&set(new) if num(old[n])!=num(new[n])),
                "old_known_weight":y["known_weight"],
                "new_known_weight":x["known_weight_research_only"],
                "old_partial_points_research_only":y["partial_weighted_points_not_full_aics"],
                "new_partial_points_research_only":x["research_partial_weighted_points_not_full_AICS"],
            })
        changes[name]=diffs
    return {
        "schema":"aics-pit100-24m-public-filing-day-rebuilt-research-v1",
        "source_replay_count":100,
        "historical_months":24,
        "active_SEC_public_filing_date_no_14day_delay":True,
        "date_only_same_day_market_close_blocked":True,
        "market_monthly_rebuilt":market,
        "calendar_monthly_rebuilt":calendar,
        "comparison_to_legacy_plus14_or_plus1_research":changes,
        "reclocked_original_events":len(event_roster(overlay,credit)),
        "quarantined_same_day_research_conflicts":conflicts,
        "same_day_joint_observation_months":{
            "original_official_Fed_release_url":G17_RELEASE,
            "publication_day":"2025-12-23",
            "observation_period_values":[
                {"observation_month":e["observation_month"],"value":e["score"]}
                for e in sorted(joint,key=lambda x:x["observation_month"])],
            "both_values_distinct_periods_no_source_quarantine":True,
            "independent_historical_first_feed_receipt":False,
        },
        "source_events_with_independent_historical_first_receipt":0,
        "newly_certified_PIT_nodes":0,
        "fully_rebuilt_production_AICS":None,
        "24month_independent_OOS":False,
        "AICS_SP500_spread":None,
        "model_weights_changed":False,
        "trades_created":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--pit100",type=Path,default=PIT100)
    args=p.parse_args()
    data=[read_bytes(x) for x in (OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,TERMS,FUNDING,STATUS)]
    pit=read_bytes(args.pit100)
    result=build(*data,pit)
    result["input_sha256"]={
        str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,TERMS,FUNDING,STATUS,args.pit100)}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "months":24,"reclocked_source_events":result["reclocked_original_events"],
        "market_changed_months":sum(any(v for k,v in row.items()
            if k in ("newly_present_nodes","no_longer_present_nodes","changed_research_score_nodes")
            and v) for row in result["comparison_to_legacy_plus14_or_plus1_research"]["market"]),
        "calendar_changed_months":sum(any(v for k,v in row.items()
            if k in ("newly_present_nodes","no_longer_present_nodes","changed_research_score_nodes")
            and v) for row in result["comparison_to_legacy_plus14_or_plus1_research"]["calendar"]),
        "PIT_certified_nodes":0,"production_index":None,"trades":False
    }))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
