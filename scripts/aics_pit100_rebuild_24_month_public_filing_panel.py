"""AICS: source-event reconstruction of 24 research months after PIT100 public-date policy.

No artificial SEC+14 wait. For the close of a market session, if historical
SEC acceptance/public dissemination time is NOT archived, the source is used
only AFTER its filing calendar date. Non-SEC sources with unverified intraday
publication timestamps get the same protection. Calendar end source event
proxy may include the source calendar date.

Rebuild from *individual* original-source-ledger events; never copy the old
monthly scores to the newly dated panel. There is NO 11-node approved AICS,
training, historical publication certification, S&P500 spread, or trading.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_pit_100_real_cutoff_agents import (
    OVERLAY,CREDIT,REPO,REGISTRY,EQUITIES,TERMS,FUNDING,STATUS,
    POLICY, read_bytes, source_preflight, date, eligible,
)

SP500=Path("aics_data/research/sp500_24_month_closes_2026-11-21.json")
RUN=Path("aics_data/agent_runs/ten_real_collection_rounds")
PIT100=RUN/"aics_100_pit_audit_runs_public_release_policy.json"
OUT=RUN/"aics_24m_publication_date_rebuilt_research_panel.json"
REPORT=RUN/"aics_24m_publication_date_rebuild_quality_report.md"
SEC_LEGACY="verified_original_sec_filed_date_plus_one_calendar_day_proxy"
NON_SEC="preserved_baseline_non_sec_or_unverified"
FRESH_DAYS=90
TOTAL_WEIGHT=1050
MONTHS=24


def dec(value):
    if isinstance(value,bool):
        raise ValueError("Boolean as numeric source")
    v=Decimal(str(value))
    if not v.is_finite():
        raise ValueError("Nonfinite numeric source")
    return v


def q2(v):
    return str(v.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))


def normalized_events(overlay,credit):
    """Transform 57+7 unchanged research events into source-dated audit rows."""
    if (overlay.get("schema")!="aics-24m-multi-node-first-public-date-research-overlay-v1"
        or credit.get("schema")!="aics-v18-24m-private-credit-original-sec-expost-research-overlay-v1"
        or overlay.get("node_weights")!=WEIGHTS
        or overlay.get("independently_historical_pit_attested") is not False
        or credit.get("historical_pit_source_bytes_independently_attested") is not False
        or credit.get("scores_are_expost_not_preregistered") is not True):
        raise ValueError("Original source-ledger lineage required")
    events=[]
    for i,r in enumerate(overlay["source_events"]):
        if (r["node"] not in WEIGHTS
            or r.get("historical_pit_certified") is not False
            or not 0<=dec(r["score"])<=100):
            raise ValueError("Wrong original node, cert flag or score bounds")
        if r["source_policy"]==SEC_LEGACY:
            filing=date(r["available_at"])-dt.timedelta(days=14)
            if date(r["research_eligible_date"])!=filing+dt.timedelta(days=1):
                raise ValueError("SEC original +1 research proxy incompatible with source metadata")
            source_kind="SEC_FILING_DATE_DERIVED_FROM_LEGACY_LEDGER"
        elif r["source_policy"]==NON_SEC:
            filing=date(r["research_eligible_date"])
            if r["research_eligible_date"]!=r["available_at"]:
                raise ValueError("Non SEC release-date proxy unexpectedly different")
            source_kind="NON_SEC_RESEARCH_RELEASE_DATE_PROXY"
        else:
            raise ValueError("Unknown original publication source policy")
        events.append({
            "event_key":f"V17:{i:02d}",
            "node":r["node"],"score":str(dec(r["score"])),
            "first_public_research_day_proxy":filing.isoformat(),
            "source_kind":source_kind,"source_path":r["source"],
            "measurement":r.get("measurement"),
            "legacy_original_plus14_or_release_date":r["available_at"],
            "historical_pubtime_intraday_verified":False,
            "historical_provider_first_byte_receipt_verified":False,
            "retrospective_formula_preregistered":False,
        })
    if len(overlay["source_events"])!=57 or len(credit["source_events"])!=7:
        raise ValueError("Known original 57+7 source-event roster changed")
    for i,r in enumerate(credit["source_events"]):
        filing=date(r["legacy_sec_plus14_available_at"])-dt.timedelta(days=14)
        if (date(r["research_available_at_proxy"])!=filing+dt.timedelta(days=1)
            or set(r["issuer_source_provenance"])!={"ARCC","BXSL","OBDC"}
            or r["historically_contemporaneous_pit_attested"] is not False
            or r["pre_registered_historical_formula"] is not False
            or not 0<=dec(r["score"])<=100):
            raise ValueError("BDC three issuer filing dates or original candidate scores bad")
        events.append({
            "event_key":f"V18_BDC:{i:02d}",
            "node":"Private Credit","score":str(dec(r["score"])),
            "first_public_research_day_proxy":filing.isoformat(),
            "source_kind":"BDC_THREE_FILING_LAST_PUBLIC_DATE_DERIVED",
            "source_path":"; ".join(r["issuer_source_provenance"].values()),
            "measurement":f"{r['quarter']} three BDC retrospective directional nonaccrual breadth",
            "legacy_original_plus14_or_release_date":r["legacy_sec_plus14_available_at"],
            "historical_pubtime_intraday_verified":False,
            "historical_provider_first_byte_receipt_verified":False,
            "retrospective_formula_preregistered":False,
        })
    if len(events)!=64 or len({x["event_key"] for x in events})!=64:
        raise ValueError("Expected 64 original distinct event records")
    return events


def ambiguous_public_release_pairs(events):
    """Quarantine distinct values for a node on the same date-only release."""
    buckets={}
    for e in events:
        buckets.setdefault((e["node"],e["first_public_research_day_proxy"]),[]).append(e)
    conflicts=[]
    for (node,day),bucket in sorted(buckets.items()):
        if len({dec(e["score"]) for e in bucket})>1:
            conflicts.append({
                "node":node,"claimed_public_day":day,
                "source_event_keys":[e["event_key"] for e in bucket],
                "original_measured_items":[e.get("measurement") for e in bucket],
                "conflicting_recorded_scores":[e["score"] for e in bucket],
                "decision":"quarantine conflicting same-date releases; retain previous unambiguous source only",
                "original_release_vintage_needed":True,
            })
    return conflicts


def replay_at(events,cutoff,*,market_close):
    """Use only observations that pass the declared cutoff, no score imputation."""
    if isinstance(cutoff,str):cutoff=date(cutoff)
    conflicts=ambiguous_public_release_pairs(events)
    quarantine={x for c in conflicts for x in c["source_event_keys"]}
    recent={}
    for event in events:
        if event["event_key"] in quarantine:
            continue
        e_date=date(event["first_public_research_day_proxy"])
        if not eligible(e_date.isoformat(),cutoff,market_close=market_close):
            continue
        if e_date>cutoff:
            raise ValueError("A future observation leaked into historical replay")
        existing=recent.get(event["node"])
        if existing is None or (e_date,event["event_key"])>(
                date(existing["first_public_research_day_proxy"]),existing["event_key"]):
            recent[event["node"]]=event
    scores={}
    for node,event in sorted(recent.items()):
        age=(cutoff-date(event["first_public_research_day_proxy"])).days
        if age<0:raise ValueError("Future date in known node")
        scores[node]={
            "score_0_100_research_only":event["score"],
            "source_event_key":event["event_key"],
            "source_public_day_proxy":event["first_public_research_day_proxy"],
            "publication_time_and_historical_receipt_not_independently_verified":True,
            "source_kind":event["source_kind"],
            "source_age_calendar_days":age,
            "freshness_90d":age<=FRESH_DAYS,
        }
    weighted=sum((dec(WEIGHTS[n])*dec(e["score_0_100_research_only"])/100
                  for n,e in scores.items()),Decimal(0))
    fresh={k:v for k,v in scores.items() if v["freshness_90d"]}
    fresh_points=sum((dec(WEIGHTS[n])*dec(v["score_0_100_research_only"])/100
                      for n,v in fresh.items()),Decimal(0))
    return {
        "date":cutoff.isoformat(),
        "source_count":len(events),
        "quarantined_conflicting_source_records":len(quarantine),
        "ambiguous_publication_source_dates":[
            x["claimed_public_day"] for x in conflicts if date(x["claimed_public_day"])<=cutoff],
        "date_only_research_nodes":len(scores),
        "date_only_known_weight":sum(WEIGHTS[n] for n in scores),
        "date_only_partial_points_not_full_AICS":q2(weighted),
        "fresh_90d_nodes":len(fresh),
        "fresh_90d_known_weight":sum(WEIGHTS[n] for n in fresh),
        "fresh_90d_partial_points_not_full_AICS":q2(fresh_points),
        "stale_node_count":len(scores)-len(fresh),
        "missing_nodes":sorted(set(WEIGHTS)-set(scores)),
        "event_source_scores":scores,
        "full_11_node_AICS":None,
        "S&P500_index_spread":None,
        "source_pit_independently_certified":False,
        "out_of_sample_predictive_skill":None,
    }


def sp500_checks(sp500,market):
    if (sp500.get("symbol")!="GSPC"
        or sp500.get("independent_pit_verified") is not False
        or len(sp500.get("points",[]))!=MONTHS):
        raise ValueError("SP500 retrieved research closing prices cannot be advertised PIT")
    vals={}
    previous=None
    for i,point in enumerate(sp500["points"]):
        if point["month"]!=market[i]["month"]:
            raise ValueError("S&P monthly close dates no longer align")
        close=dec(point["sp500_month_end_close"])
        if close<=0:raise ValueError("Invalid index closing price")
        vals[point["month"]]={
            "month_end_observed_close_retrieved_expost":str(close),
            "same_month_return_from_previous_observed_close_pct":
                q2((close/previous-1)*100) if previous is not None else None,
            "historical_original_price_source_vintage_attested":False,
            "prediction_outcome_used_as_input_feature":False,
        }
        previous=close
    return vals


def build(overlay,credit,sp500,pit100,*,as_of):
    if isinstance(as_of,str):as_of=date(as_of)
    if not isinstance(as_of,dt.date) or isinstance(as_of,dt.datetime):
        raise ValueError("Invalid research cutoff")
    if (sum(WEIGHTS.values())!=TOTAL_WEIGHT
        or pit100.get("schema")!="aics-100-real-dated-PIT-audit-role-replays-v1"
        or pit100.get("PIT_runs_successfully_computed")!=100
        or pit100.get("actual_distinct_aics_roles")!=100
        or pit100.get("SEC_14day_delay_is_active") is not False
        or pit100.get("active_historical_research_source_policy")!=POLICY
        or pit100.get("trades_created") is not False):
        raise ValueError("Require genuine completed 100-role PIT public-date audit")
    events=normalized_events(overlay,credit)
    conflicts=ambiguous_public_release_pairs(events)
    if len(conflicts)!=1 or conflicts[0]["node"]!="Semiconductors Supply":
        raise ValueError("Original same-date conflicting G.17 releases need independent review")
    # Guard using original PIT100 primary preflight as an independently
    # separate materialization of the dated SEC +1 legacy ledger.
    panels={}
    old={"calendar":credit["monthly_calendar_end_research"],
         "market":credit["monthly_last_weekday_market_proxy"]}
    for mode,field in (("calendar","monthly_calendar_end_research"),
                       ("market","monthly_last_weekday_market_proxy")):
        months=overlay[field]
        if len(months)!=MONTHS or len(old[mode])!=MONTHS:
            raise ValueError("Month count no longer 24")
        rows=[]
        for row,previous in zip(months,old[mode]):
            if (row["month"]!=previous["month"]
                or row["cutoff_date"]!=previous["cutoff_date"]
                or date(row["cutoff_date"])>as_of
                or previous["full_aics"] is not None
                or previous["historical_pit_certified"] is not False):
                raise ValueError("Old calendar, market or as-of contaminated")
            current=replay_at(events,row["cutoff_date"],market_close=mode=="market")
            old_nodes=previous["node_scores"]
            new_nodes=current["event_source_scores"]
            added=sorted(set(new_nodes)-set(old_nodes))
            removed=sorted(set(old_nodes)-set(new_nodes))
            repriced=sorted(
                n for n in set(old_nodes)&set(new_nodes)
                if dec(new_nodes[n]["score_0_100_research_only"])!=dec(old_nodes[n]["score"]))
            if (len(old_nodes)!=previous["known_node_count"]
                or sum(WEIGHTS[n] for n in old_nodes)!=previous["known_weight"]):
                raise ValueError("Old benchmark source coverage tampered")
            current.update({
                "month":row["month"],"cutoff_date":row["cutoff_date"],
                "panel_type":mode,
                "legacy_expost_known_node_count":previous["known_node_count"],
                "legacy_expost_known_weight":previous["known_weight"],
                "legacy_expost_partial_points_not_full_AICS":
                    previous["partial_weighted_points_not_full_aics"],
                "difference_in_dateonly_known_weight":
                    current["date_only_known_weight"]-previous["known_weight"],
                "difference_in_dateonly_partial_points":
                    q2(dec(current["date_only_partial_points_not_full_AICS"])
                       -dec(previous["partial_weighted_points_not_full_aics"])),
                "nodes_added_vs_legacy_expost":added,
                "nodes_removed_vs_legacy_expost":removed,
                "node_score_values_changed_vs_legacy_expost":repriced,
                "legacy_source_window_not_independent_validation":True,
            })
            rows.append(current)
        if [r["month"] for r in rows]!=[
            f"{2024+(10+i)//12:04d}-{(10+i)%12+1:02d}"
            for i in range(MONTHS)]:
            raise ValueError("24 source month calendar not exact")
        panels[mode]=rows
    spx=sp500_checks(sp500,panels["market"])
    for row in panels["market"]:
        row["SP500_monthly_context_not_AICS_spread"]=spx[row["month"]]
    if len(pit100["100_audit_results"])!=100:
        raise ValueError("Missing specialist audit receipts")
    # Independently validate *all 100* unique historical cutoff receipts by
    # re-materializing public-day vs market-close candidate node states.
    audit_rows=[]
    for entry in pit100["100_audit_results"]:
        c=date(entry["historical_cutoff"])
        if c>as_of:
            raise ValueError("Future source-specific audit cutoff")
        cal=replay_at(events,c,market_close=False)
        market=replay_at(events,c,market_close=True)
        if (cal["date_only_known_weight"]<market["date_only_known_weight"]
            or cal["source_count"]!=64
            or market["source_count"]!=64):
            raise ValueError("Same-day uncertainty guard invalid at specialist audit cutoff")
        base=entry["eligible_event_counts"]
        sec=[e for e in events if e["source_kind"]=="SEC_FILING_DATE_DERIVED_FROM_LEGACY_LEDGER"]
        if (base["source_events_sec_filed_day_calendar_dateonly"]!=
                sum(eligible(e["first_public_research_day_proxy"],c,market_close=False) for e in sec)
            or base["source_events_sec_pre_market_close_safe_dayonly"]!=
                sum(eligible(e["first_public_research_day_proxy"],c,market_close=True) for e in sec)
            or base["first_historical_provider_byte_receipt_verified_count"]!=0
            or entry["accepted_into_production_model"] is not False):
            raise ValueError("100-role original SEC receipts disagree with rebuilt release dates")
        audit_rows.append({
            "original_PIT100_role":entry["AICS_role_id"],
            "original_PIT100_audit_no":entry["PIT_audit_number"],
            "actual_historical_source_cutoff":c.isoformat(),
            "calendar_public_day_rebuilt_candidate_nodes":cal["date_only_research_nodes"],
            "calendar_public_day_rebuilt_known_weight":cal["date_only_known_weight"],
            "market_close_protected_rebuilt_candidate_nodes":market["date_only_research_nodes"],
            "market_close_protected_rebuilt_known_weight":market["date_only_known_weight"],
            "historical_PIT_source_certified":False,
        })
    if len({r["actual_historical_source_cutoff"] for r in audit_rows})!=100:
        raise ValueError("Historical source audit roles not distinct")
    comparisons={}
    for mode,rows in panels.items():
        comparisons[mode]={
            "months":len(rows),
            "legacy_weight_months":sum(x["legacy_expost_known_weight"] for x in rows),
            "rebuilt_dateonly_weight_months":sum(x["date_only_known_weight"] for x in rows),
            "rebuilt_fresh_90d_weight_months":sum(x["fresh_90d_known_weight"] for x in rows),
            "months_with_changed_weight":sum(x["difference_in_dateonly_known_weight"]!=0 for x in rows),
            "months_with_changed_partial_points":sum(dec(x["difference_in_dateonly_partial_points"])!=0 for x in rows),
            "months_with_added_nodes":sum(bool(x["nodes_added_vs_legacy_expost"]) for x in rows),
            "months_with_removed_nodes":sum(bool(x["nodes_removed_vs_legacy_expost"]) for x in rows),
            "months_with_changed_node_score":sum(bool(x["node_score_values_changed_vs_legacy_expost"]) for x in rows),
            "last_month":rows[-1]["month"],
            "last_month_rebuilt_weight":rows[-1]["date_only_known_weight"],
            "last_month_rebuilt_partial_points":rows[-1]["date_only_partial_points_not_full_AICS"],
            "last_month_fresh_90d_weight":rows[-1]["fresh_90d_known_weight"],
            "last_month_missing_nodes":rows[-1]["missing_nodes"],
            "dateonly_research_coverage_pct":
                q2(Decimal(100)*sum(x["date_only_known_weight"] for x in rows)/Decimal(MONTHS*TOTAL_WEIGHT)),
            "fresh_90d_research_coverage_pct":
                q2(Decimal(100)*sum(x["fresh_90d_known_weight"] for x in rows)/Decimal(MONTHS*TOTAL_WEIGHT)),
        }
    return {
        "schema":"aics-24month-public-filing-date-PIT100-rebuilt-candidate-panel-v1",
        "as_of":as_of.isoformat(),
        "active_policy":POLICY,
        "source_events_recomputed_from_unchanged_original_ledgers":64,
        "same_day_ambiguous_release_conflicts_quarantined":conflicts,
        "original_PIT100_roles_individually_verified_against_rebuild":100,
        "original_PIT100_execution_count":pit100["PIT_runs_successfully_computed"],
        "SEC_14day_artificial_delay_active":False,
        "same_day_unverified_market_close_filing_is_eligible":False,
        "pre_registered_historical_stress_node_scores":False,
        "independently_historical_PIT_first_delivery_certified":False,
        "historic_nonSEC_release_vintages_independently_attested":False,
        "official_exchange_session_timestamps_all_verified":False,
        "SP500_monthly_price_history_retrieved_not_PIT_proven":True,
        "retrospective_node_score_source_data_are_research_candidates_not_genuine_exante_predictions":True,
        "24month_independent_OOS_skill":None,
        "full_11node_AICS":None,
        "aics_sp500_spread":None,
        "2000_similarity_probability":None,"2008_similarity_probability":None,
        "frozen_original_weights_total":1050,
        "newly_certified_11node_stress_scores":0,
        "model_weights_changed":False,"trades_created":False,
        "monthly_rebuilt_panels":panels,
        "baseline_vs_rebuilt_quality_metrics":comparisons,
        "audit_100_unique_original_source_cutoffs":audit_rows,
    }


def markdown_report(report):
    metric=report["baseline_vs_rebuilt_quality_metrics"]
    market=report["monthly_rebuilt_panels"]["market"]
    calendar=report["monthly_rebuilt_panels"]["calendar"]
    lines=[
        "# AICS PIT100 — reconstructed 24-month data quality report",
        "",
        f"**Research cutoff:** {report['as_of']}. **Source policy:** public SEC filing calendar date, **no +14-day delay**. Market-close date-only same-day submissions require an independently verified acceptance timestamp; none is attested in these historic ledgers.",
        "",
        "**Audits:** 100 unique role/cutoff replays cross-verified against 64 original SEC / macro / company-credit research events, 24 calendar and 24 market-close month-ends. **None** of the old node scores is independently historic PIT or preregistered.",
        "",
        "## Baseline versus rebuilt data coverage",
        "",
        "| Indicator | Market close | Calendar close |",
        "|---|---:|---:|",
    ]
    for label,k in (
        ("Months rebuilt","months"),
        ("Legacy candidate source weight-months","legacy_weight_months"),
        ("Rebuilt candidate weight-months","rebuilt_dateonly_weight_months"),
        ("Rebuilt **fresh <=90 days** weight-months","rebuilt_fresh_90d_weight_months"),
        ("Months with changed coverage","months_with_changed_weight"),
        ("Months with changed weighted partial points","months_with_changed_partial_points"),
        ("Research source coverage %","dateonly_research_coverage_pct"),
        ("Fresh 90d source coverage %","fresh_90d_research_coverage_pct"),
    ):
        lines.append(f"| {label} | {metric['market'][k]} | {metric['calendar'][k]} |")
    lines += [
        "",
        "## New market-close monthly original-source candidate coverage vs S&P 500",
        "",
        "| Month | Date | Nodes | Weight / 1050 | Partial **NOT AICS** | 90d fresh weight | S&P 500 observed close | S&P 500 observed monthly return | Δ partial vs legacy |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in market:
        spx=row["SP500_monthly_context_not_AICS_spread"]
        lines.append(
            f"| {row['month']} | {row['cutoff_date']} | {row['date_only_research_nodes']} | "
            f"{row['date_only_known_weight']} | {row['date_only_partial_points_not_full_AICS']} | "
            f"{row['fresh_90d_known_weight']} | "
            f"{spx['month_end_observed_close_retrieved_expost']} | "
            f"{spx['same_month_return_from_previous_observed_close_pct'] or 'n/a'}% | "
            f"{row['difference_in_dateonly_partial_points']} |"
        )
    lines += [
        "",
        "The S&P 500 column is **contemporaneous historical context**, not evidence of AICS predictive skill. There is **no numerical AICS–S&P spread** because a full approved index does not exist.",
        "",
        "## Calendar-close changes versus market close",
        "",
        "| Month | Market weight | Calendar weight | Market partial (research) | Calendar partial (research) | Market nodes missing |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for m,c in zip(market,calendar):
        lines.append(
            f"| {m['month']} | {m['date_only_known_weight']} | {c['date_only_known_weight']} | "
            f"{m['date_only_partial_points_not_full_AICS']} | "
            f"{c['date_only_partial_points_not_full_AICS']} | "
            f"{', '.join(m['missing_nodes']) or 'none'} |"
        )
    lines += [
        "",
        "## Original data conflicts discovered during reconstruction",
        "",
        "**G.17 source conflict:** two Semiconductor Supply observations claiming 2025-12-23 first-public dates have different original values (2025-10 and 2025-11 measured periods). Both are quarantined until independently verified against the actual dated original Federal Reserve release/vintage. The preceding unambiguous observation is kept separately with its source age; no interpolated value is used.",
        "",
        "## Quality gates, still open",
        "",
        "- Exact historical SEC **acceptance and public dissemination timestamp**, with exchange trading-session calendar",
        "- Original-source time-travel vintages: ALFRED, NY Fed source releases, SEC first-received bytes and revision lineage",
        "- Fixed historical 11-node input definitions, constituents, cashflow metric definitions and preregistered score formulas",
        "- **24 untouched out-of-sample months**, crisis-onset labels, reproducible strategy baseline; crisis analogy 2000 vs 2008 unproven",
        "- Independently certified source provenance for **0/11** AICS nodes. **Production index, crisis probability, 2000/2008 numeric similarity, portfolio spread and trades remain null**",
        "",
        "### Output safety",
        "",
        "Reconstructed **candidate partial points are not comparable with AICS production entry/exit thresholds**. Missing nodes have never been filled with zero; the report preserves exact source-event IDs, age, timing policy and all 100 cutoff audit receipts. Original archived research ledgers remain unchanged.",
    ]
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument("--pit100",type=Path,default=PIT100)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--report",type=Path,default=REPORT)
    a=p.parse_args()
    paths=[OVERLAY,CREDIT,SP500,a.pit100]
    result=build(*(read_bytes(x) for x in paths),as_of=a.as_of)
    result["source_file_sha256"]={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in paths}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    a.report.write_text(markdown_report(result),encoding="utf-8")
    print(json.dumps({
        "market_months":result["baseline_vs_rebuilt_quality_metrics"]["market"]["months"],
        "calendar_months":result["baseline_vs_rebuilt_quality_metrics"]["calendar"]["months"],
        "market_coverage_pct":result["baseline_vs_rebuilt_quality_metrics"]["market"]["dateonly_research_coverage_pct"],
        "market_changed_months":result["baseline_vs_rebuilt_quality_metrics"]["market"]["months_with_changed_partial_points"],
        "100_auditors_crosschecked":result["original_PIT100_roles_individually_verified_against_rebuild"],
        "SEC_plus14_wait":False,"approved_index":None,"trades":False,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
