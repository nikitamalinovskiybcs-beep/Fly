"""AICS V40–V49: ten focused PIT forensic agents, one source-evidence batch.

Their job is to expose/repair a known +1-day vs +14-day filing-clock
mismatch in retrospective overlays, identify contaminated market/calendar
snapshots, and quarantine candidate dates. Archived bytes captured TODAY
do not certify historical delivery to a provider on a past day. No synthetic
backfill, no live trade, no promotion to an independently validated index.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_early_imbalance_cashflow_shadow import (
    build as build_cash, read, Y2025,Q42025,Q12026,Q22026,Q32026,
)
from scripts.aics_historical_crisis_analog import build as build_analog

ROOT=Path("aics_data/research")
RUN=Path("aics_data/agent_runs/ten_real_collection_rounds")
OVERLAY=ROOT/"aics_24m_multi_node_publication_overlay_2026-11-21.json"
CREDIT=ROOT/"aics_v18_private_credit_24m_pit_proxy_overlay_2026-11-22.json"
REGISTRY=Path("aics_data/source_registry/neocloud_cash_h1_sec.json")
REPO=ROOT/"repo_24_month_observed_research_2026-11-18.json"
EQUITIES=ROOT/"ai_equities_aug_oct_2026_retrospective_shadow_2026-11-21.json"
STATUS=Path("aics_data/progress/status.json")
OUT=RUN/"aics_v40_v49_ten_pit_forensics_agents.json"

NAMES=[
    "V40_SEC_ISSUER_FILING_CLOCK",
    "V41_PRIVATE_CREDIT_PREMATURE_REPORTS",
    "V42_MARKET_MONTH_END_PIT_QUARANTINE",
    "V43_CALENDAR_MONTH_END_PIT_QUARANTINE",
    "V44_HYPERSCALER_ORIGINAL_DOCUMENT_PROVENANCE",
    "V45_NEOCLOUD_SEC_ARCHIVE_RECEIPT_ATTESTATION",
    "V46_REPO_ALFRED_RELEASE_VINTAGES",
    "V47_AI_EQUITIES_CONSTITUENT_VINTAGES",
    "V48_HISTORICAL_CRISIS_FIRST_ONSET",
    "V49_ELEVEN_NODE_CERTIFICATION_GATE",
]
SEC_POLICY="verified_original_sec_filed_date_plus_one_calendar_day_proxy"
PERIODS=24


def date(s):
    return dt.date.fromisoformat(s)


def read_bytes(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def checked_overlay(overlay):
    if (overlay.get("schema")!="aics-24m-multi-node-first-public-date-research-overlay-v1"
        or overlay.get("window")!=["2024-11","2026-10"]
        or overlay.get("node_weights")!=WEIGHTS
        or overlay.get("independently_historical_pit_attested") is not False
        or overlay.get("independently_oos_24m") is not False
        or overlay.get("complete_11_node_aics_months")!=0
        or overlay.get("aics_sp500_spread_months")!=0
        or overlay.get("production_change") is not False
        or overlay.get("trades_created") is not False):
        raise ValueError("Retrospective monthly overlay must not be promoted")
    events=overlay.get("source_events",[])
    if not isinstance(events,list) or not events:
        raise ValueError("Empty original retrospective source-event list")
    premature=[]
    for i,e in enumerate(events):
        if (e.get("node") not in WEIGHTS
            or date(e["research_eligible_date"])>date(e["available_at"])
            or e.get("historical_pit_certified") is not False):
            raise ValueError("Unknown node, late proxy or falsely certified source event")
        if e.get("source_policy")==SEC_POLICY:
            before,strict=date(e["research_eligible_date"]),date(e["available_at"])
            if (strict-before).days!=13:
                raise ValueError("SEC +1 -> SEC +14 mismatch must be exactly 13 days")
            premature.append({
                "event_idx":i,"node":e["node"],"research_proxy":before.isoformat(),
                "strict_sec_plus14":strict.isoformat(),
                "premature_calendar_days":13,
                "source_ledger":e["source"],
                "issuer_or_quarter_description":e.get("measurement"),
                "historical_provider_first_receipt_verified":False,
            })
        elif e.get("source_policy")=="preserved_baseline_non_sec_or_unverified":
            if e["research_eligible_date"]!=e["available_at"]:
                raise ValueError("Non-SEC first-date proxy unexpectedly advanced")
        else:
            raise ValueError("Unrecognized source-vintage policy")
    return events,premature


def a40(events,early):
    return {
        "candidate_events_inspected":len(events),
        "SEC_events_with_13day_premature_research_proxy":len(early),
        "premature_by_node":dict(sorted(Counter(x["node"] for x in early).items())),
        "original_event_and_safe_eligibility_corrections":early,
        "original_source_ledger_kept_unchanged":True,
        "asof_pit_approved_events":0,
    }


def a41(credit):
    if (credit.get("schema")!="aics-v18-24m-private-credit-original-sec-expost-research-overlay-v1"
        or credit.get("scores_are_expost_not_preregistered") is not True
        or credit.get("historical_pit_source_bytes_independently_attested") is not False
        or credit.get("full_11node_index_months")!=0
        or credit.get("aics_sp500_spread_months")!=0):
        raise ValueError("Retrospective credit overlay is not PIT certified")
    result=[]
    for event in credit["source_events"]:
        early,strict=date(event["research_available_at_proxy"]),date(event["legacy_sec_plus14_available_at"])
        if ((strict-early).days!=13
            or event["historically_contemporaneous_pit_attested"] is not False
            or event["pre_registered_historical_formula"] is not False
            or set(event["issuer_source_provenance"])!={"ARCC","BXSL","OBDC"}):
            raise ValueError("Private Credit issuer filings or publication date inconsistent")
        result.append({
            "quarter":event["quarter"],
            "research_eligible_proxy":early.isoformat(),
            "strict_SEC_plus14":strict.isoformat(),
            "premature_days":13,"original_bdc_issuers":sorted(event["issuer_source_provenance"]),
            "can_train_time_series_before_strict_date":False,
        })
    return {
        "original_BDC_quarters":len(result),
        "quarters_premature_under_SEC_plus14":len(result),
        "repaired_research_only_source_date_journal":result,
        "PIT_filing_bytes_independently_attested":False,
        "approved_private_credit_score":None,
    }


def replay_window(overlay,early,field):
    months=overlay.get(field,[])
    if (len(months)!=PERIODS
        or [r["month"] for r in months]!=[
            f"{(2024+(10+i)//12):04d}-{((10+i)%12)+1:02d}"
            for i in range(PERIODS)]):
        raise ValueError("24 chronological month-end evidence windows required")
    repairs=[]
    safe_window=[]
    for month in months:
        cutoff=date(month["cutoff_date"])
        quarantined=[]
        safe_nodes=[]
        originals=month["node_scores"]
        if (not isinstance(originals,dict)
            or set(originals)|set(month["missing_nodes"])!=set(WEIGHTS)):
            raise ValueError("Monthly feature count, weights or missing nodes inconsistent")
        for node,score in originals.items():
            matched=[x for x in early
                     if x["node"]==node
                     and x["research_proxy"]==score["research_eligible_date"]
                     and overlay["source_events"][x["event_idx"]]["score"]==score["score"]]
            if len(matched)>1:
                raise ValueError("Ambiguous SEC proxy-to-monthly source selection")
            source=matched[0] if matched else None
            if (source is not None
                and source["research_proxy"]<=month["cutoff_date"]<source["strict_sec_plus14"]):
                quarantined.append(node)
                repairs.append({
                    "month":month["month"],"cutoff_date":month["cutoff_date"],
                    "node":node,"original_research_proxy":source["research_proxy"],
                    "strict_SEC_plus14":source["strict_sec_plus14"],
                    "score_removed_from_PIT_candidate_at_this_cutoff":True,
                })
            else:
                safe_nodes.append(node)
        if month["known_weight"]!=sum(WEIGHTS[n] for n in originals):
            raise ValueError("Legacy retrospective known weight mismatch")
        safe_window.append({
            "month":month["month"],"cutoff_date":month["cutoff_date"],
            "original_research_node_count":len(originals),
            "original_research_known_weight":month["known_weight"],
            "quarantined_early_SEC_nodes":sorted(quarantined),
            "safe_date_only_research_node_count":len(safe_nodes),
            "safe_date_only_research_known_weight":sum(WEIGHTS[n] for n in safe_nodes),
            "safe_date_only_scores_are_still_not_independently_PIT_or_preregistered":True,
            "full_11node_index":None,
            "aics_sp500_spread":None,
        })
    return {
        "monthly_source_windows":PERIODS,
        "quarantined_node_months":len(repairs),
        "affected_months":sorted(set(x["month"] for x in repairs)),
        "quarantine_journal":repairs,
        "date_safe_source_eligibility_replay_not_scored_index":safe_window,
        "historical_PIT_certified":False,
        "OOS_certified":False,
    }


def a44(asof):
    cash=build_cash(read(Y2025),read(Q42025),read(Q22026),read(Q32026),
                    q1=read(Q12026),as_of=asof)
    if (cash["full_11_node_aics"] is not None
        or cash["primary_source_document_bytes_independently_historical_pit_attested"] is not False
        or cash["fixed_original_aics_node_weights_total"]!=1050):
        raise ValueError("Hyperscaler original document research falsely promoted")
    journal=[]
    for q in cash["quarterly_original_issuer_records"]:
        if q["first_complete_source_eligible_at_sec_plus14"]>asof.isoformat():
            raise ValueError("SEC cashflow observation leaked before eligibility")
        journal.append({
            "quarter":q["period"],"issuer":q["issuer"],
            "available_at":q["first_complete_source_eligible_at_sec_plus14"],
            "original_source_reference_available":True,
            "independent_original_historical_receipt_attested":False,
        })
    group=[r for r in cash["complete_or_partial_quarters"] if r["four_issuer_complete"]]
    return {
        "eligible_original_SEC_issuer_quarters":len(journal),
        "complete_four_issuer_quarters":len(group),
        "source_date_ledger":journal,
        "verified_historical_first_provider_receipts":0,
        "false_backfill_issuer_quarters":0,
        "full_index_using_unverified_cashflow":None,
    }


def a45(registry):
    if not isinstance(registry,dict) or len(registry)!=10:
        raise ValueError("Unexpected SEC original document source registry")
    records=[]
    for ident,rec in sorted(registry.items()):
        filed=date(rec["filed_at"])
        strict=date(rec["available_at"])
        if ((strict-filed).days!=14
            or not str(rec["source_page"]).startswith("https://www.sec.gov/Archives/edgar/data/")
            or not str(rec["original"]["url"]).startswith("https://www.sec.gov/Archives/edgar/data/")
            or len(str(rec["original"]["sha256"]))!=64
            or len(str(rec["document_text_sha256"]))!=64
            or int(rec["original"]["bytes"])<1):
            raise ValueError("SEC original bytes, dates or source identity altered")
        records.append({
            "source_id":ident,"issuer_CIK":rec["cik"],
            "original_archive_bytes":rec["original"]["bytes"],
            "original_SHA256":rec["original"]["sha256"],
            "original_filed_date":rec["filed_at"],
            "strict_sec_plus14":rec["available_at"],
            "historical_first_feed_delivery_attested":False,
        })
    return {
        "independently_source_hashed_original_SEC_archives":len(records),
        "SEC_date_rule_violations":0,
        "historically_PIT_attested_original_provider_receipts":0,
        "raw_source_to_eligible_date_journal":records,
        "source_raw_hash_today_does_not_backdate_source_delivery":True,
    }


def a46(repo):
    if (repo.get("schema_version")!="aics-repo-24-matched-source-observed-rates-v2"
        or repo.get("observed_months")!=24
        or repo.get("independent_24_month_oos") is not False
        or repo.get("source_release_timestamp_pit_attested") is not False
        or repo.get("contemporaneous_alfred_snapshots_attested") is not False
        or repo.get("stress_score") is not None
        or repo.get("index_aics") is not None):
        raise ValueError("Repo/ALFRED vintage falsely promoted")
    missing=[]
    for r in repo["monthly_observations"]:
        if date(r["market_effective_date"])>date(r["publication_proxy_date"]):
            raise ValueError("Repo publication before real market effective date")
        if date(r["publication_proxy_date"])>date(r["as_of"]):
            raise ValueError("Repo market-month proxy improperly time-traveled")
        missing.append({
            "month":r["as_of"][:7],
            "original_effective_date":r["market_effective_date"],
            "unverified_release_proxy":r["publication_proxy_date"],
            "ALFRED_historical_data_vintage_sha":None,
            "first_historical_provider_receipt":None,
        })
    return {
        "retrospective_repo_months":len(missing),
        "ALFRED_release_vintages_independently_attested":0,
        "release_timestamp_proof_missing_months":len(missing),
        "exact_missing_vintage_manifest":missing,
        "can_promote_repo_node":False,
    }


def a47(equities):
    archive=equities["original_archive"]
    if (equities.get("schema")!="aics-ai-equities-month-end-2026q3-retrospective-shadow-v1"
        or equities.get("original_provider_historical_vintages_attested") is not False
        or equities.get("approved_historical_constituency") is not False
        or equities.get("corporate_actions_complete_original_timeline_attested") is not False
        or equities.get("independent_historical_pit_24m") is not False
        or equities.get("certified_aics") is not None
        or equities.get("trades_created") is not False
        or archive.get("original_rows_total")!=441
        or len(equities["research_symbols"])!=7):
        raise ValueError("Nasdaq retrospective archive cannot certify historical constituents")
    m=equities["observations"]
    if [x["month"] for x in m]!=["2026-08","2026-09","2026-10"]:
        raise ValueError("Original equity market date grid changed")
    for x in m:
        if not x["last_trading_session"].startswith(x["month"]):
            raise ValueError("Equity source month/last trading date mismatch")
    return {
        "ticker_count_source_archived":len(equities["research_symbols"]),
        "retrospective_original_price_records":archive["original_rows_total"],
        "research_month_end_points":len(m),
        "point_in_time_constituent_history_certified":False,
        "historical_price_adjustment_vintages_certified":False,
        "historical_retail_node_score_promotable":False,
        "fresh_raw_price_bytes_not_2026_august_feed_receipt":True,
    }


def a48(overlay,analog):
    if (analog.get("schema")!="aics-2026-vs-2000-2008-historical-mechanisms-and-timing-v1"
        or analog.get("feature_axis_count")!=8
        or analog.get("quantitative_similarity_percent_2000") is not None
        or analog.get("quantitative_similarity_percent_2008") is not None
        or analog.get("verified_precrisis_index_lead_time") is not None
        or analog.get("independent_24month_OOS_backtest") is not False):
        raise ValueError("Historical crisis early-warning was not reproduced")
    events=[]
    for episode in ("telecom2000","subprime2008"):
        p=analog["comparison_eras"][episode]["timing_audit"]
        if p["early_warning_of_crisis_onset_status"]!="OLD_CROSSING_AFTER_OBSERVED_CRISIS_ONSET":
            raise ValueError("Old threshold crossing not earlier than initial distress")
        events.append({"episode":episode,"original_early_warning_reproduced":False,
                       "crisis_onset":p["first_market_or_funding_crisis_date"],
                       "old_cited_threshold_crossing":p["old_report_crossing_window"]})
    return {
        "measured_failure_mechanism_axes":analog["feature_axis_count"],
        "historical_event_date_audits":events,
        "independently_reconstructed_2000_11node_months":0,
        "independently_reconstructed_2008_11node_months":0,
        "verified_pre_onset_lead_months":None,
        "historical_2000_vs_2008_similarity_probability":None,
    }


def a49(status,waves,finance):
    if (status.get("schema_version")!="aics-progress-status-v1"
        or status.get("scope")!="PROJECT_MILESTONES_NOT_MODEL_QUALITY"
        or status.get("milestones_total")!=66
        or status.get("total_nodes")!=11
        or status.get("milestones_completed")!=22
        or status.get("independently_certified_nodes")!=0
        or status.get("source_pit_attested_nodes")!=0
        or status.get("audited_scoring_nodes")!=0
        or status.get("untouched_24m_oos_nodes")!=0
        or status.get("index_aics") is not None
        or status.get("promotion")!="BLOCKED"
        or sum(WEIGHTS.values())!=1050):
        raise ValueError("Cannot auto-promote project milestones as PIT certification")
    if waves is not None:
        if (waves.get("schema")!="aics-ten-real-source-acquisition-waves-with-companyfacts-v1"
            or waves.get("independently_pit_verified_node_count")!=0
            or waves.get("complete_index") is not None
            or waves.get("production_weights_changed") is not False
            or waves.get("trades_created") is not False):
            raise ValueError("Live collector has no certified historic source receipt")
    if finance is not None:
        if (finance.get("independently_pit_attested") is not False
            or finance.get("source_bytes_historical_first_filing_verified") is not False
            or finance.get("node_scores_promoted")!=0
            or finance.get("full_11_node_aics") is not None):
            raise ValueError("Live XBRL research evidence not independently historic")
    return {
        "current_verified_project_gates_completed":status["milestones_completed"],
        "total_independent_project_gates":status["milestones_total"],
        "project_progress_pct_not_accuracy":status["project_progress_pct"],
        "newly_certified_PIT_nodes_from_retroactive_date_correction":0,
        "independently_PIT_certified_nodes":0,
        "approved_11_node_score":None,
        "approved_2000_2008_prediction_skill":None,
        "new_certified_milestones_automatically_awarded":0,
        "live_current_collector_original_http_archives":
            waves.get("successful_http_archives") if waves is not None else None,
        "original_numeric_records_from_current_SEC_snapshots":
            finance.get("original_numeric_rows_inspected") if finance is not None else None,
        "evidence_and_portfolio_must_remain_separate":True,
    }


def build(overlay,credit,registry,repo,equities,status,analog,*,as_of,waves=None,finance=None):
    as_of=date(as_of) if isinstance(as_of,str) else as_of
    if not isinstance(as_of,dt.date) or isinstance(as_of,dt.datetime):
        raise ValueError("Research as-of calendar date required")
    events,early=checked_overlay(overlay)
    agents=[
        a40(events,early),
        a41(credit),
        replay_window(overlay,early,"monthly_last_weekday_market_proxy"),
        replay_window(overlay,early,"monthly_calendar_end_research"),
        a44(as_of),
        a45(registry),
        a46(repo),
        a47(equities),
        a48(overlay,analog),
        a49(status,waves,finance),
    ]
    if len(agents)!=10 or len(NAMES)!=10:
        raise ValueError("Exactly ten PIT forensic agents")
    for i,entry in enumerate(agents):
        entry["name"]=NAMES[i]
        entry["research_audit_not_independently_historical_PIT"]=True
        entry["production_model_promotion"]=False
    return {
        "schema":"aics-v40-v49-ten-specialist-pit-replay-agents-v1",
        "as_of":as_of.isoformat(),
        "source_event_count":len(events),
        "source_premature_SEC_proxies":len(early),
        "private_credit_premature_quarters":agents[1]["quarters_premature_under_SEC_plus14"],
        "market_close_quarantined_node_months":agents[2]["quarantined_node_months"],
        "calendar_close_quarantined_node_months":agents[3]["quarantined_node_months"],
        "strict_source_date_event_quarantine_only_no_synthetic_replacements":True,
        "ten_agent_research_results":agents,
        "same_10_model_improvement_roles_repurposed_for_PIT":True,
        "total_30_roles_unchanged":True,
        "approved_pit_certified_nodes":0,
        "newly_completed_certification_gates":0,
        "current_project_milestone_completion":22,
        "approved_11node_aics":None,
        "independent_24m_OOS":False,
        "crisis_probability":None,
        "historical_2000_2008_quantitative_similarity":None,
        "unchanged_total_weight":1050,
        "model_weights_changed":False,
        "trades_created":False,
    }


def build_from_repository(*,as_of,waves=None,finance=None):
    return build(read_bytes(OVERLAY),read_bytes(CREDIT),read_bytes(REGISTRY),
                 read_bytes(REPO),read_bytes(EQUITIES),read_bytes(STATUS),
                 build_analog(read_bytes(CREDIT)),as_of=as_of,waves=waves,finance=finance)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--waves",type=Path)
    p.add_argument("--finance",type=Path)
    a=p.parse_args()
    paths=[OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,STATUS,
           Y2025,Q42025,Q12026,Q22026,Q32026]
    report=build_from_repository(
        as_of=a.as_of,
        waves=read_bytes(a.waves) if a.waves is not None else None,
        finance=read_bytes(a.finance) if a.finance is not None else None)
    if a.waves:paths.append(a.waves)
    if a.finance:paths.append(a.finance)
    report["input_SHA256"]={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in paths}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "pit_agents":len(report["ten_agent_research_results"]),
        "legacy_SEC_plus1_events":report["source_premature_SEC_proxies"],
        "private_credit_quarters_early":report["private_credit_premature_quarters"],
        "market_close_exposures_quarantined":report["market_close_quarantined_node_months"],
        "calendar_close_exposures_quarantined":report["calendar_close_quarantined_node_months"],
        "new_certified_nodes":0,
        "certified_index":None,
        "trades":False,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
