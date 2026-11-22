"""AICS V61 — source-to-score model-risk falsification, NOT a repaired index.

Three missing candidate nodes of October 2026 already have PARTIAL,
historically retrospective raw observations. The question is NOT whether we
can fabricate 3 risk scores, but whether arbitrary normalized research
formulas flip an AICS entry/watch/cash decision.

For Aug/Sep/Oct 2026 only, combine:
 - V18 source-partial 11-node history with correct known weights/hotness;
 - V60 two explicitly post-hoc UST30 candidate normalizations;
 - Repo archived 24m observed SOFR-IORB original spread (never a full
   secured-funding-market stress score), candidate max(spread,0)/10bp
   or /20bp and a mathematical zero boundary case;
 - AI Equities the EXISTING retrospectively captured 7-stock 1-day
   close/open decliner-fraction score, which has no historical basket
   authorization, split/corporate action timeline or source date PIT.

The 2*3=6 entirely HYPOTHETICAL scenarios for each of the last three
months are NOT a pre-registered trading strategy, model selection or official
index. All changeable model components are unapproved as-of and remain
unknown in the original AICS. Strong safety: full index=NULL and zero trades.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_v59_24m_uncertainty_envelope import build as v59_build, multiplier
from scripts.aics_v60_ust30_shadow_score_hypotheses import build as v60_build

ROOT=Path("aics_data/research")
V18=ROOT/"aics_v18_private_credit_24m_pit_proxy_overlay_2026-11-22.json"
DGS30=ROOT/"ust30_24_month_public_observed_panel_2026-11-18.json"
VOL=ROOT/"ust30_yield_change_volatility_2024_2026.json"
REPO=ROOT/"repo_24_month_observed_research_2026-11-18.json"
AI=ROOT/"ai_equities_aug_oct_2026_retrospective_shadow_2026-11-21.json"
EQUITY_DIRECTORY=ROOT/"ai_equities_prospective_directory_first_capture_2026-11-19.json"
REHASH=ROOT/"ust_repo_joint_original_replay_external_rehash_2026-11-19.json"
OUT=ROOT/"aics_v61_three_unapproved_scores_model_risk_matrix_2026-11-22.json"
D=Decimal
assert len(WEIGHTS)==11 and sum(WEIGHTS.values())==1050

def _numeric(x):
    try:
        v=D(str(x))
    except (ValueError,InvalidOperation,TypeError) as exc:
        raise ValueError("Invalid true source market reading") from exc
    if not v.is_finite():
        raise ValueError("Non-finite source market observation")
    return v

def _clip(x):
    return max(D(0),min(D(100),x))

def _round(x):
    return float(x.quantize(D("0.01"),rounding=ROUND_HALF_UP))

def _zone(index):
    if index<D(450):
        return "HYPOTHETICAL_ENTRY_LT_450_NOT_ACTIONABLE"
    if index>D(500):
        return "HYPOTHETICAL_CASH_GT_500_NOT_ACTIONABLE"
    return "HYPOTHETICAL_WATCH_450_TO_500_NOT_ACTIONABLE"

def _accept_repo(repo):
    if (repo.get("schema_version")!="aics-repo-24-matched-source-observed-rates-v2"
        or repo.get("fixed_node")!="Repo" or repo.get("fixed_node_weight")!=100
        or repo.get("observed_months")!=24 or repo.get("missing_months")!=0
        or repo.get("synthetic_market_rows")!=0
        or repo.get("source_release_timestamp_pit_attested") is not False
        or repo.get("contemporaneous_alfred_snapshots_attested") is not False
        or repo.get("independent_24_month_oos") is not False
        or repo.get("stress_score") is not None or repo.get("index_aics") is not None
        or repo.get("promotion")!="BLOCKED"
        or len(repo.get("monthly_observations",[]))!=24):
        raise ValueError("Repo source must remain unscored research-only")
    month_map={}
    for row in repo["monthly_observations"]:
        month=row["as_of"][:7]
        if month in month_map:
            raise ValueError("Duplicate original Repo month")
        if row["as_of"][:7]!=month or row["market_effective_date"]>=row["as_of"]:
            raise ValueError("Original repo source chronology changed")
        sofr=_numeric(row["sofr_pct"])
        iorb=_numeric(row["iorb_pct"])
        bgcr=_numeric(row["bgcr_pct"])
        tgcr=_numeric(row["tgcr_pct"])
        if (tgcr>bgcr or
            (sofr-iorb)*100!=_numeric(row["sofr_minus_iorb_bps"])
            or (sofr-bgcr)*100!=_numeric(row["sofr_minus_bgcr_bps"])):
            raise ValueError("Repo as-of source spread arithmetic mismatch")
        month_map[month]=row
    return month_map

def _accept_ai(ai,directory):
    if (ai.get("schema")!="aics-ai-equities-month-end-2026q3-retrospective-shadow-v1"
        or ai.get("node")!="AI Equities" or ai.get("node_weight")!=100
        or ai.get("approved_historical_constituency") is not False
        or ai.get("original_provider_historical_vintages_attested") is not False
        or ai.get("corporate_actions_complete_original_timeline_attested") is not False
        or ai.get("score_eligible_at_2026_08_31") is not False
        or ai.get("score_eligible_at_2026_09_30") is not False
        or ai.get("score_eligible_at_2026_10_31") is not False
        or ai.get("original_score_coverage_panel_promotion") is not False
        or ai.get("certified_aics") is not None or ai.get("trades_created") is not False
        or len(ai.get("observations",[]))!=3
        or len(ai.get("research_symbols",[]))!=7
        or directory.get("schema_version")!="aics-ai-equities-prospective-official-directory-independent-rehash-v1"
        or directory.get("node")!="AI Equities"
        or directory.get("fixed_weight")!=100
        or directory.get("historical_basket_membership_attested") is not False
        or directory.get("corporate_action_history_pit_attested") is not False
        or directory.get("historical_initial_24_months_reconstructed") is not False
        or directory.get("score_eligible") is not False
        or directory.get("node_stress_score") is not None
        or directory.get("index_aics") is not None
        or directory.get("promotion")!="BLOCKED"
        or directory.get("research_as_of")!="2026-11-19"):
        raise ValueError("AI Equities research cannot masquerade as old eligible score")
    symbols=set(ai["research_symbols"])
    found={x["symbol"] for x in directory.get("research_symbols",[])}
    if len(found)!=7 or symbols!=found:
        raise ValueError("Historical research stock symbols and current Nasdaq directory differ")
    claims={}
    for row in ai["observations"]:
        month=row["month"]
        if month not in ("2026-08","2026-09","2026-10") or month in claims:
            raise ValueError("Only the three observed research equity months exist")
        falling=row["decliners"]
        if len(set(falling))!=len(falling) or not set(falling)<=symbols:
            raise ValueError("Equity original declining ticker set is not valid")
        score=_numeric(row["score"])
        expected=(D(len(falling))*D(100)/D(7)).quantize(
            D("0.01"),rounding=ROUND_HALF_UP)
        if score!=expected or row["last_trading_session"][:7]!=month:
            raise ValueError("Retrospective AI basket research score arithmetic changed")
        claims[month]=row
    if len(claims)!=3:
        raise ValueError("Missing a required observed 2026Q3 stock session")
    return claims

def _original_hash_check(hashmap,receipt):
    declared=receipt.get("original_committed_source_file_sha256")
    if (receipt.get("schema_version")!="aics-ust30-repo-joint-24-matched-real-original-replay-external-rehash-v1"
        or receipt.get("zip_crc_test_passed") is not True
        or receipt.get("matched_real_month_ends")!=24
        or receipt.get("independent_pit_nodes_certified")!=0
        or receipt.get("ust30_node_score") is not None
        or receipt.get("repo_node_score") is not None
        or receipt.get("index_aics") is not None
        or not isinstance(declared,dict)):
        raise ValueError("Independent source rehash receipt cannot be promoted")
    for p in (REPO,DGS30,VOL):
        if hashmap[str(p)]!=declared.get(str(p)):
            raise ValueError("Original separately downloaded source SHA256 mismatch")

def _scenario(row,repo_raw,ai_score,ust_score,repo_score,method):
    if row["month"] not in ("2026-08","2026-09","2026-10"):
        raise ValueError("Unsupported AI scores before retrospective provider observation")
    base_raw=D(row["observed_partial_weighted_sum_exact"])
    h=row["known_hot_nodes_strict_gt_60"]
    for n in ("UST 30Y","Repo","AI Equities"):
        if n not in row["missing_nodes_not_imputed"]:
            raise ValueError("Cannot substitute a genuinely known node")
    missing_others=set(row["missing_nodes_not_imputed"])-{"UST 30Y","Repo","AI Equities"}
    if missing_others:
        raise ValueError("What-if three-node completion is valid only for selected 2026 dates")
    h+=sum(x>D(60) for x in (ai_score,ust_score,repo_score))
    raw=base_raw+D(WEIGHTS["AI Equities"])*ai_score/D(100)+D(WEIGHTS["UST 30Y"])*ust_score/D(100)+D(WEIGHTS["Repo"])*repo_score/D(100)
    index=raw*multiplier(h)
    return {
        "hypothetical_UST30_nonofficial_score":_round(ust_score),
        "hypothetical_Repo_nonofficial_score":_round(repo_score),
        "hypothetical_AI_Equities_retro_nonofficial_score":_round(ai_score),
        "candidate_Repo_rule":method,
        "hot_nodes_if_all_3_unapproved_model_scores_assumed":h,
        "risk_if_ALL_nonapproved_shadows_assumed_NOT_REAL_AICS":_round(index),
        "hypothetical_threshold_zone_NOT_ACTIONABLE":_zone(index),
        "official_AICS":None,
        "trade_action":None,
    }

def build(overlay,ust,vol,repo,ai,directory,receipt,*,hashes):
    _original_hash_check(hashes,receipt)
    v59=v59_build(overlay)
    v60=v60_build(overlay,ust,vol)
    repo_data=_accept_repo(repo)
    ai_data=_accept_ai(ai,directory)
    base={x["month"]:x for x in v59["monthly_24m_conditional_research_envelopes"]}
    uscore={x["month"]:x for x in v60["observed_months_and_hypothetical_score_stress_tests"]}
    outcomes=[]
    for month in ("2026-08","2026-09","2026-10"):
        a=ai_data[month]
        rp=repo_data[month]
        u=uscore[month]
        if (rp["as_of"][:7]!=month or u["month"]!=month
            or ust["public_series_observations"][int(month[-2:])-8+21]["as_of_month_end"][:7]!=month):
            raise ValueError("Original source month of research scenario does not match")
        # Repo premia = observed basis-point arithmetic. Scaling is an
        # *unregistered model choice*, not a historical score source.
        premium=max(D(0),_numeric(rp["sofr_minus_iorb_bps"]))
        points={
            "RepoZeroBoundary":D(0),
            "RepoPremium20bpPostHoc":_clip(D(100)*premium/D(20)),
            "RepoPremium10bpPostHoc":_clip(D(100)*premium/D(10)),
        }
        ai_score=_numeric(a["score"])
        trials=[]
        for ust_name,key in (
            ("Vol10","candidate_Vol10_risk_proxy_0_100_NOT_OFFICIAL"),
            ("VolPlusRise","candidate_VolPlusRise_risk_proxy_0_100_NOT_OFFICIAL"),
        ):
            ustscore=u[key]
            if ustscore is None:
                raise ValueError("Missing UST score hypothesis at observed 2026Q3 date")
            for method,rep_score in points.items():
                p=_scenario(base[month],rp,ai_score,D(str(ustscore)),rep_score,method)
                p["candidate_UST_rule"]=ust_name
                trials.append(p)
        zones=sorted(set(x["hypothetical_threshold_zone_NOT_ACTIONABLE"] for x in trials))
        outcomes.append({
            "month":month,
            "historical_original_repo_spreads_observed":True,
            "original_observed_SOFR_percent":rp["sofr_pct"],
            "original_observed_IORB_percent":rp["iorb_pct"],
            "original_observed_SOFR_minus_IORB_bp":rp["sofr_minus_iorb_bps"],
            "original_observed_SOFR_minus_BGCR_bp":rp["sofr_minus_bgcr_bps"],
            "equity_retro_declining_tickers":a["decliners"],
            "equity_retro_decliners_count":len(a["decliners"]),
            "equity_retro_7_symbol_research_score_NOT_ELIGIBLE":str(ai_score),
            "UST_retro_ALFRED_original_yield_percent":u["original_ALFRED_DGS30_yield_percent"],
            "old_known_8_7_nodes_fixed_as_V18":base[month]["known_node_count"],
            "old_known_hot_nodes":base[month]["known_hot_nodes_strict_gt_60"],
            "conditional_old_interval":[base[month]["conditional_full_index_lower_if_all_missing_scores_ZERO_BOUND_CASE"],
                                        base[month]["conditional_full_index_upper_if_all_missing_scores_100_BOUND_CASE"]],
            "six_nonofficial_score_combinations":trials,
            "number_of_different_hypothetical_regions":len(zones),
            "hypothetical_zones":zones,
            "new_approved_node_scores":0,
            "official_full_AICS":None,
            "trades_created":False,
        })
    count=sum(x["number_of_different_hypothetical_regions"]>1 for x in outcomes)
    return {
        "schema":"aics-v61-original-repo-and-ai-source-gated-six-model-rule-ambiguity-v1",
        "research_asof_date":"2026-11-22",
        "real_repo_original_monthly_observations":len(repo_data),
        "real_nasdaq_equity_retro_session_months":len(ai_data),
        "real_nasdaq_current_seven_company_directory_found":len(directory["research_symbols"]),
        "ust30_actual_monthly_observations_already":24,
        "research_partial_11node_history_original":24,
        "AI_retro_price_retrieved_after_2026_Aug_Sep_Oct":True,
        "Repo_intraday_historical_release_independently_attested":False,
        "AI_historical_seven_member_basket_and_split_adjustments_attested":False,
        "UST_official_0_to_100_risk_node_score_found":False,
        "Repo_official_0_to_100_risk_node_score_found":False,
        "AI_Equities_approved_old_month_price_to_score_verified":False,
        "new_score_normalizers_10_20_basis_points_are_post_hoc_research_only":True,
        "market_outcome_used_to_select_scenario":False,
        "scenarios_calculated_real_original_source_not_real_scores":len(outcomes)*6,
        "months_where_posthoc_reasonable_normalizers_disagree_on_450_500_regime":count,
        "official_index_still_unknown_for_all_24_months":True,
        "october_original_conditional_range":[322.06,801.07],
        "official_full_11node_AICS":None,
        "research_24m_independent_PIT_certified_nodes":0,
        "strict_readiness_delivered_milestones_22_of_66_unchanged":True,
        "trading_approved":False,
        "new_trades_created":0,
        "conductor_decision":"Refuse to infer trading zone from retrospectively chosen repo scales and AI one-day basket. Pin official score methods and true as-of receipts before anything can be promoted.",
        "three_months_2026Q3_research_model_definition_risk":outcomes,
    }

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=OUT)
    a=parser.parse_args()
    paths=(V18,DGS30,VOL,REPO,AI,EQUITY_DIRECTORY,REHASH)
    source={str(p):p.read_bytes() for p in paths}
    hashes={name:hashlib.sha256(raw).hexdigest() for name,raw in source.items()}
    objs=[json.loads(source[str(p)]) for p in paths]
    result=build(*objs,hashes=hashes)
    result["source_files_with_original_bytes_sha256"]=hashes
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="three_months_2026Q3_research_model_definition_risk"},ensure_ascii=False))
    for row in result["three_months_2026Q3_research_model_definition_risk"]:
        print(row["month"],[(x["candidate_UST_rule"],x["candidate_Repo_rule"],x["risk_if_ALL_nonapproved_shadows_assumed_NOT_REAL_AICS"],x["hypothetical_threshold_zone_NOT_ACTIONABLE"])
                            for x in row["six_nonofficial_score_combinations"]])
    return 0

if __name__=="__main__":
    raise SystemExit(main())
