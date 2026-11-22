"""AICS PIT100 — 100 genuinely executed historical-cutoff audits by 100 roles.

Retains 30 existing distinct AICS execution roles and adds 70 source-audit
specialists. Exactly 100 distinct PIT audits across 100 distinct observed
source/event/month-end dates, each reporting source-specific evidence.
Not 100 separately trained LLMs or 100 new publisher HTTP downloads.

Active RESEARCH PIT policy supersedes artificial SEC filed+14 waiting:
  * SEC candidate filing date = public filing calendar date, not +14.
  * Calendar day EOD: filing-day eligibility is only a DATE proxy.
  * 16:00 New York stock-market close: when acceptance time is missing,
    the filing date itself is NOT eligible (could be after the close).
  * Actual verified acceptance ET + actual session calendar is required
    for same-day close eligibility. No such first-delivery attestations
    exist in these retrospective ledgers.
  * Historic original first-byte receipt is NEVER inferred from today's SHA.
Previously built +14 reports remain immutable legacy research, not active
PIT policy or a source of certified 11-node AICS / S&P500 spread.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_ten_node_agents import NODE_TASKS
from scripts.aics_ten_analysis_agents import AGENT_NAMES
from scripts.aics_ten_model_improvement_agents import NAMES as IMPROVEMENT_NAMES
from scripts.aics_v40_v49_ten_pit_forensics_agents import (
    OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,STATUS,read_bytes,
)
from scripts.aics_early_imbalance_cashflow_shadow import (
    build as cash_build,read as read_sec,Y2025,Q42025,Q12026,Q22026,Q32026,
)
from scripts.aics_v29_refinancing_maturity_overlay import TERMS
from scripts.aics_v30_cashflow_financing_bridge import FUNDING

ROOT=Path("aics_data/agent_runs/ten_real_collection_rounds")
OUT=ROOT/"aics_100_pit_audit_runs_public_release_policy.json"
POLICY="SEC_PUBLIC_FILING_DATE_WITH_VERIFIED_INTRADAY_IF_AVAILABLE_v2"
SEC_LEGACY="verified_original_sec_filed_date_plus_one_calendar_day_proxy"
SOURCE_GROUPS=(
    "SEC_PUBLIC_FILING_AND_ACCEPTANCE",
    "PRIVATE_CREDIT_3BDC_SOURCE_DATES",
    "MARKET_CLOSE_ORIGINAL_PUBLICATION",
    "CALENDAR_CLOSE_ORIGINAL_PUBLICATION",
    "HYPERSCALER_28_ORIGINAL_ISSUER_QUARTERS",
    "NEOCLOUD_Q2_SEC_FINANCING_SOURCES",
    "REPO_RATE_RELEASE_VINTAGE",
    "AI_EQUITIES_PRICE_CONSTITUENCY_VINTAGE",
    "NEOCLOUD_CONTRACT_BORROWER_RECOURSE",
    "PIT_GOVERNANCE_AND_SCORE_PROHIBITIONS",
)
FIRST_30=(
    tuple("SourceCollector:"+n for n in NODE_TASKS)
    +tuple("HistoricAnalyst:"+n for n in AGENT_NAMES)
    +tuple("ModelResearch:"+n for n in IMPROVEMENT_NAMES)
)
assert len(FIRST_30)==30 and len(set(FIRST_30))==30
EXTRA_70=tuple(
    "PITSpecialist:"+SOURCE_GROUPS[i//10]+":"+f"{i%10+1:02d}"
    for i in range(30,100)
)
ROLES=FIRST_30+EXTRA_70
assert len(ROLES)==len(set(ROLES))==100


def date(x):
    return dt.date.fromisoformat(x)


def num(x):
    if isinstance(x,bool):
        raise ValueError("Boolean numeric")
    v=Decimal(str(x))
    if not v.is_finite():
        raise ValueError("Non-finite source value")
    return v


def eligible(filed,cutoff,*,market_close):
    """With date-only source, NEVER certify an intraday same-day trade."""
    return date(filed)<cutoff if market_close else date(filed)<=cutoff


def source_preflight(overlay,credit,registry,repo,equities,terms,finance,status):
    if (overlay.get("schema")!="aics-24m-multi-node-first-public-date-research-overlay-v1"
        or overlay.get("node_weights")!=WEIGHTS
        or len(overlay.get("monthly_last_weekday_market_proxy",[]))!=24
        or len(overlay.get("monthly_calendar_end_research",[]))!=24
        or overlay.get("independently_historical_pit_attested") is not False
        or credit.get("schema")!="aics-v18-24m-private-credit-original-sec-expost-research-overlay-v1"
        or credit.get("scores_are_expost_not_preregistered") is not True
        or credit.get("historical_pit_source_bytes_independently_attested") is not False
        or repo.get("source_release_timestamp_pit_attested") is not False
        or repo.get("contemporaneous_alfred_snapshots_attested") is not False
        or equities.get("original_provider_historical_vintages_attested") is not False
        or equities.get("approved_historical_constituency") is not False
        or status.get("milestones_completed")!=22
        or status.get("independently_certified_nodes")!=0
        or status.get("index_aics") is not None
        or terms.get("known_current_lender_dollar_exposures")!=0
        or finance.get("index_aics") is not None
        or finance.get("trades_created") is not False
        or sum(WEIGHTS.values())!=1050):
        raise ValueError("PIT100 source inputs falsely certified or altered")
    if len(registry)!=10 or len(terms.get("contracts",[]))!=3:
        raise ValueError("Unexpected original SEC archive or loan agreement count")
    events=[]
    for i,x in enumerate(overlay["source_events"]):
        if (x["node"] not in WEIGHTS or x.get("historical_pit_certified") is not False):
            raise ValueError("Source node, vintage or PIT flag missing")
        if x.get("source_policy")==SEC_LEGACY:
            filed=date(x["available_at"])-dt.timedelta(days=14)
            if (filed+dt.timedelta(days=1)).isoformat()!=x["research_eligible_date"]:
                raise ValueError("Legacy SEC source filing date cannot be reconstructed")
            if (filed+dt.timedelta(days=14)).isoformat()!=x["available_at"]:
                raise ValueError("SEC legacy source date not consistent with source filing")
            kind="SEC_ORIGINAL"
        elif x.get("source_policy")=="preserved_baseline_non_sec_or_unverified":
            if x["research_eligible_date"]!=x["available_at"]:
                raise ValueError("Non SEC original release proxy inconsistent")
            filed=date(x["available_at"])
            kind="NON_SEC_RELEASE_PROXY"
        else:
            raise ValueError("Unknown legacy source release policy")
        events.append({
            "event_id":i,"node":x["node"],"kind":kind,
            "original_filing_or_release_date":filed.isoformat(),
            "legacy_14day_date":x["available_at"] if kind=="SEC_ORIGINAL" else None,
            "historic_public_first_byte_delivery_attested":False,
            "research_score":x["score"],
            "source_ledger":x["source"],
        })
    for id,r in registry.items():
        filed=date(r["filed_at"])
        if ((date(r["available_at"])-filed).days!=14
            or len(r["original"]["sha256"])!=64
            or not r["source_page"].startswith("https://www.sec.gov/Archives/edgar/data/")):
            raise ValueError("Original SEC document archive hash/filing date inconsistent")
    for e in credit["source_events"]:
        if (date(e["legacy_sec_plus14_available_at"])-date(e["research_available_at_proxy"])).days!=13:
            raise ValueError("Private Credit public filing date not reconciled")
        if e["historically_contemporaneous_pit_attested"] is not False:
            raise ValueError("Historical BDC vintage not attested")
    if len(repo["monthly_observations"])!=24 or len(equities["observations"])!=3:
        raise ValueError("Expected 24 repo and 3 equity months missing")
    return events


def historical_observation_dates(overlay,credit,repo,registry,cash,terms):
    """Select 100 *actual dated source events*, never fabricate timestamps."""
    candidates={}
    def put(value,source):
        d=date(value).isoformat()
        candidates.setdefault(d,set()).add(source)
    for x in overlay["source_events"]:
        put(x["research_eligible_date"],"legacy_research_date")
        put(x["available_at"],"legacy_plus14_or_release_date")
    for field in ("monthly_calendar_end_research","monthly_last_weekday_market_proxy"):
        for x in overlay[field]:
            put(x["cutoff_date"],field)
    for x in credit["source_events"]:
        put(x["research_available_at_proxy"],"BDC_source_research_date")
        put(x["legacy_sec_plus14_available_at"],"BDC_legacy_plus14")
    for x in repo["monthly_observations"]:
        for field in ("market_effective_date","publication_proxy_date","as_of"):
            put(x[field],"repo_"+field)
    for id,r in registry.items():
        put(r["filed_at"],"original_SEC_archive_file_date")
        put(r["available_at"],"legacy_SEC_archive_plus14_date")
    for x in cash["quarterly_original_issuer_records"]:
        for s in x["original_sec_sources"]:
            put(s["filed"],"original_hyperscaler_source_file_date")
    for x in terms["contracts"]:
        put(x["filed_at"],"original_SEC_loan_contract_date")
    ordered=sorted(candidates)
    if len(ordered)<100:
        raise ValueError("Fewer than 100 REAL historical input cutoff dates")
    # Equal rank stratification over real event dates: no synthetic date added.
    chosen=[ordered[(i*(len(ordered)-1))//99] for i in range(100)]
    if len(set(chosen))!=100:
        raise ValueError("Repeated PIT replay cutoff")
    return chosen,candidates


def signed_finance_bridge(row):
    x=row["financing_components_signed"]
    if sum((num(v) for v in x.values()),Decimal(0))!=num(row["net_financing_cash"]):
        raise ValueError("Issuer financing cashflow does not reconcile")
    return {"issuer":row["issuer"],"observed_quarter":row["period"],
            "reported_financing_cash_usd_m":row["net_financing_cash"],
            "not_borrower_specific_funded_lender_exposure":True}


def audit_domain(kind,cutoff,*,events,overlay,credit,registry,repo,
                 equities,cash,terms,finance,status):
    # All 100 runs perform a shared documented cutoff audit before a
    # distinctly scoped domain check, never change historical raw ledgers.
    sec=[e for e in events if e["kind"]=="SEC_ORIGINAL"]
    non=[e for e in events if e["kind"]=="NON_SEC_RELEASE_PROXY"]
    sec_calendar=[e for e in sec if eligible(e["original_filing_or_release_date"],cutoff,market_close=False)]
    sec_market=[e for e in sec if eligible(e["original_filing_or_release_date"],cutoff,market_close=True)]
    legacy=[e for e in sec if e["legacy_14day_date"]<=cutoff.isoformat()]
    shared={
        "source_events_sec_filed_day_calendar_dateonly":len(sec_calendar),
        "source_events_sec_pre_market_close_safe_dayonly":len(sec_market),
        "source_events_sec_plus14_LEGACY_ONLY":len(legacy),
        "source_events_nonsec_release_proxy_at_cutoff":
            sum(e["original_filing_or_release_date"]<=cutoff.isoformat() for e in non),
        "source_acceptance_time_et_verified_count":0,
        "first_historical_provider_byte_receipt_verified_count":0,
    }
    if len(sec_market)>len(sec_calendar) or len(legacy)>len(sec_calendar):
        raise ValueError("Source clock reverses chronological time")
    if kind==0:
        docs=[r for r in registry.values() if eligible(r["filed_at"],cutoff,market_close=False)]
        specific={"original_SEC_submissions_hashed_today_published_dateonly":len(docs),
                  "original_SECs_not_yet_filed":len(registry)-len(docs),
                  "legacy_14day_disqualified_but_public_filed_day_possible":
                      len(sec_calendar)-len(legacy),
                  "no_14calendar_day_artificial_delay_active":True}
    elif kind==1:
        rows=credit["source_events"]
        filed=[(date(r["research_available_at_proxy"])-dt.timedelta(days=1)).isoformat()
               for r in rows]
        date_only=sum(x<=cutoff.isoformat() for x in filed)
        previous=sum(r["legacy_sec_plus14_available_at"]<=cutoff.isoformat() for r in rows)
        specific={"BDC_filing_day_candidate_quarters":date_only,
                  "BDC_pre_market_close_safe_quarters":sum(x<cutoff.isoformat() for x in filed),
                  "legacy_14day_candidate_quarters":previous,
                  "expost_not_preregistered":True,
                  "candidate_quarter_scores_are_not_PIT_certified":True}
    elif kind in (2,3):
        field="monthly_last_weekday_market_proxy" if kind==2 else "monthly_calendar_end_research"
        windows=[r for r in overlay[field] if date(r["cutoff_date"])<=cutoff]
        latest=windows[-1] if windows else None
        safe_sec=sum(eligible(e["original_filing_or_release_date"],cutoff,
                              market_close=kind==2) for e in sec)
        # Period score references are original retrospective research only.
        same_day_unknown=sum(e["original_filing_or_release_date"]==cutoff.isoformat() for e in sec)
        specific={"window_kind":"market_close" if kind==2 else "calendar_day_end",
                  "actual_original_window_count":len(windows),
                  "latest_month_cutoff":latest["cutoff_date"] if latest else None,
                  "legacy_research_known_weight":latest["known_weight"] if latest else None,
                  "strict_date_only_SEC_source_event_count":safe_sec,
                  "same_day_unverified_SEC_acceptance_event_count":same_day_unknown,
                  "same_day_source_must_wait_next_market_session":kind==2,
                  "period_research_scores_not_certified":True}
    elif kind==4:
        records=[]
        for r in cash["quarterly_original_issuer_records"]:
            refs=r["original_sec_sources"]
            if all(eligible(x["filed"],cutoff,market_close=False) for x in refs):
                records.append(r)
        quarters={}
        for r in records:quarters.setdefault(r["period"],set()).add(r["issuer"])
        if any(len(v)>4 for v in quarters.values()):raise ValueError("Duplicate hyperscaler row")
        specific={"original_consolidated_issuer_quarters_filed_calendar_proxy":len(records),
                  "fully_source_filed_four_issuer_quarters":
                      sum(len(v)==4 for v in quarters.values()),
                  "partial_issuer_quarters_without_full_cohort":
                      {k:len(v) for k,v in quarters.items() if len(v)<4},
                  "cashflow_not_pure_AI_revenue_or_debt":True,
                  "source_count_no_synthetic_backfill":True}
    elif kind==5:
        ready=[];filed_day=[]
        for row in finance["cash_bridges"]:
            ok=all(eligible(registry[key]["filed_at"],cutoff,market_close=False) for key in row["sources"])
            if ok:
                ready.append(signed_finance_bridge(row))
                filed_day.append(row["issuer"])
        specific={"original_Q2_2026_funding_statements_filed_by_date":ready,
                  "issuer_roster":sorted(filed_day),
                  "named_lender_funded_exposure_usd_m":None,
                  "same_quarter_funding_is_not_lending_causality":True}
    elif kind==6:
        visible=[x for x in repo["monthly_observations"]
                 if date(x["publication_proxy_date"])<=cutoff]
        if len(visible)>24:raise ValueError("Invalid repo history")
        latest=visible[-1] if visible else None
        specific={"repo_monthly_releases_dateonly_proxy_visible":len(visible),
                  "latest_repo_market_month":latest["as_of"] if latest else None,
                  "latest_observed_sofr_minus_iorb_bps":latest["sofr_minus_iorb_bps"] if latest else None,
                  "ALFRED_historic_vintages_verified":0,
                  "source_release_timestamp_attested":False,
                  "repo_is_not_named_SPV_credit_spread":True}
    elif kind==7:
        archive_date=date(equities["original_archive"]["capture_utc"][:10])
        specific={"actual_retrospectively_captured_price_rows":
                      equities["original_archive"]["original_rows_total"]
                      if archive_date<=cutoff else 0,
                  "original_provider_capture_at":equities["original_archive"]["capture_utc"],
                  "source_historic_constituents_verified":False,
                  "equity_instrument_corporate_action_history_attested":False,
                  "24m_oos_equity_score":None,
                  "price_archive_today_does_not_prove_historical_PIT":True}
    elif kind==8:
        contracts=[r for r in terms["contracts"]
                   if eligible(r["filed_at"],cutoff,market_close=False)]
        if any(r["lender_by_lender_amount_usd_m"] is not None for r in contracts):
            raise ValueError("Lender per-bank holdings fabricated")
        specific={"dated_contract_terms_available_by_filing_day":len(contracts),
                  "known_legal_maturity_dates":[r["contractual_maturity"] for r in contracts],
                  "contractual_capacity_not_actual_draws":True,
                  "named_current_lender_dollar_exposures":0,
                  "verified_same_facility_repricing_pairs":0}
    elif kind==9:
        if status["independently_certified_nodes"]!=0 or status["milestones_total"]!=66:
            raise ValueError("Invalid project certification")
        specific={"fixed_model_weight_total":1050,
                  "project_control_milestones":22,
                  "independently_certified_11node_scores":0,
                  "24_month_independent_oos":False,
                  "2000_2008_before_onset_prediction_proven":False,
                  "production_score":None}
    else:
        raise ValueError("Unknown PIT agent domain")
    return shared,specific


def build(overlay,credit,registry,repo,equities,terms,finance,status,cash,
          *,as_of,cycle=None):
    if isinstance(as_of,str):as_of=date(as_of)
    if not isinstance(as_of,dt.date) or isinstance(as_of,dt.datetime):
        raise ValueError("Invalid research cutoff")
    events=source_preflight(overlay,credit,registry,repo,equities,terms,finance,status)
    chosen,origin=historical_observation_dates(overlay,credit,repo,registry,cash,terms)
    if chosen[-1]>as_of.isoformat():
        raise ValueError("Future source-derived cutoff before research asof")
    if len(cash["quarterly_original_issuer_records"])!=28:
        raise ValueError("Four issuers by seven original quarters required")
    if cycle is not None and (
        cycle.get("agent_groups",{}).get("total_distinct_roles_executed")!=30
        or cycle.get("PIT_source_forensics",{}).get("ten_existing_improvement_agents_focused_on_PIT")!=10
        or cycle.get("complete_11_node_aics") is not None
        or cycle.get("trades_created") is not False):
        raise ValueError("The 30 earlier roles must have genuinely executed first")
    records=[]
    for i,role in enumerate(ROLES):
        # Distribute each domain's ten distinct roles across the full
        # 2024-2026 calendar rather than clustering one domain in one year.
        pos=(i%10)*10+(i//10)
        cutoff=date(chosen[pos])
        family=i//10
        shared,answer=audit_domain(family,cutoff,events=events,overlay=overlay,
                                    credit=credit,registry=registry,repo=repo,
                                    equities=equities,cash=cash,terms=terms,
                                    finance=finance,status=status)
        records.append({
            "PIT_audit_number":i+1,
            "AICS_role_id":role,
            "existing_core_role":i<30,
            "new_specialist_role":i>=30,
            "audit_family":SOURCE_GROUPS[family],
            "historical_cutoff":cutoff.isoformat(),
            "cutoff_is_exact_observed_source_or_month_end_date":True,
            "date_origin_categories":sorted(origin[cutoff.isoformat()]),
            "active_policy":POLICY,
            "historical_provider_receipt_independently_verified":False,
            "eligible_event_counts":shared,
            "domain_specific_source_derived_audit":answer,
            "accepted_into_production_model":False,
        })
    if (len(records)!=100 or len({r["AICS_role_id"] for r in records})!=100
        or len({r["historical_cutoff"] for r in records})!=100
        or sum(r["new_specialist_role"] for r in records)!=70
        or sum(r["existing_core_role"] for r in records)!=30):
        raise ValueError("Must actually execute 100 distinct PIT role/date audits")
    counts=[sum(r["audit_family"]==g for r in records) for g in SOURCE_GROUPS]
    if counts!=[10]*10:
        raise ValueError("Ten audit families need ten unique executions each")
    sec=[e for e in events if e["kind"]=="SEC_ORIGINAL"]
    if len(sec)!=27 or len(credit["source_events"])!=7:
        raise ValueError("Legacy original SEC early-date ledger changed")
    return {
        "schema":"aics-100-real-dated-PIT-audit-role-replays-v1",
        "as_of":as_of.isoformat(),
        "active_historical_research_source_policy":POLICY,
        "SEC_14day_delay_is_active":False,
        "calendar_public_filing_date_proxy_used":True,
        "same_day_market_close_protected_without_verified_acceptance_time":True,
        "exact_SEC_acceptance_time_captured_and_independently_verified":False,
        "historical_first_delivery_PIT_certified":False,
        "original_30_existing_roles_executed_before_overlay":
            cycle is not None,
        "actual_distinct_aics_roles":100,
        "original_base_aics_roles":30,
        "new_PIT_specialist_roles":70,
        "unique_historical_replay_cutoffs":100,
        "available_unique_original_observation_dates":len(origin),
        "PIT_runs_successfully_computed":len(records),
        "distinct_audit_families":list(SOURCE_GROUPS),
        "checks_per_family":dict(zip(SOURCE_GROUPS,counts)),
        "legacy_14day_proxy_SEC_events_count":len(sec),
        "legacy_14day_date_difference_is_not_violation_under_active_policy":True,
        "ten_original_BDC_plus1_ledger_does_not_imply_attested_release":True,
        "100_audit_results":records,
        "newly_certified_historical_PIT_nodes":0,
        "certified_11_node_AICS":None,
        "AICS_SP500_spread":None,
        "supervised_forward_skill":None,
        "historical_2000_2008_numeric_similarity":None,
        "production_model_weights_changed":False,
        "trades_created":False,
        "publisher_request_count_from_these_100_replays":0,
        "meaning_of_runs":"100 executed original-source-derived historical asof checks; not 100 fetched historical vintages or independently certified models",
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--cycle",type=Path)
    a=p.parse_args()
    paths=[OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,TERMS,FUNDING,STATUS,
           Y2025,Q42025,Q12026,Q22026,Q32026]
    data=[read_bytes(x) for x in paths[:8]]
    cash=cash_build(read_sec(Y2025),read_sec(Q42025),read_sec(Q22026),
                    read_sec(Q32026),q1=read_sec(Q12026),
                    as_of=dt.date(2026,11,22))
    c=read_bytes(a.cycle) if a.cycle is not None else None
    rep=build(*data,cash,as_of=a.as_of,cycle=c)
    rep["source_file_sha256"]={
        str(x):hashlib.sha256(x.read_bytes()).hexdigest()
        for x in paths+( [a.cycle] if a.cycle else [])
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "actual_distinct_aics_roles":rep["actual_distinct_aics_roles"],
        "new_pit_specialist_roles":rep["new_PIT_specialist_roles"],
        "unique_cutoff_dates_replayed":rep["unique_historical_replay_cutoffs"],
        "PIT_runs":rep["PIT_runs_successfully_computed"],
        "SEC_14day_delay":rep["SEC_14day_delay_is_active"],
        "PIT_certified_nodes":0,
        "production_score":None,
        "trades":False,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
