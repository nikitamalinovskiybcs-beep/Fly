"""AICS MASTER: one 11-node, 1050-weight research nowcast from REAL source files.

This unifies the ORIGINAL index instead of replacing it with a three-node
index. As of 2026-10-30 only 8/11 original V18 research node scores exist.
A clearly marked illustrative full 11-node SHADOW can be constructed from
three retroactively observed, unapproved source-to-score hypotheses (V60/V61).
The six previously published scenarios, plus the rigorous missing-node
interval and 24-month partial-coverage ledger, are shown alongside it.

No price is synthesized; the illustrative proxy rules were selected after
2024-2026 results were observed, so NO historical PIT or untouched OOS skill
is claimed. Official certified AICS stays NULL, no trade actions, 22/66.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_v59_24m_uncertainty_envelope import build as v59_build, multiplier
from scripts.aics_v61_repo_ai_source_to_score_model_risk import (
    V18,DGS30,VOL,REPO,AI,EQUITY_DIRECTORY,REHASH,
    build as v61_build,
)

OUT=Path("aics_data/research/aics_master_11node_research_nowcast_2026-11-22.json")
SPEC=(("UST 30Y","Vol10","UST_VOL10_POSTHOC"),
      ("Repo","RepoPremium20bpPostHoc","REPO_PREMIUM20_POSTHOC"),
      ("AI Equities","seven_equities_decliners_last_session","AI_RETRO7_ONE_DAY"))
TARGET="2026-10"
LATEST_CUTOFF="2026-10-30"
TOTAL=1050
assert len(WEIGHTS)==11 and sum(WEIGHTS.values())==TOTAL

def _r(x):
    return float(Decimal(str(x)).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))

def _read_sources():
    paths=(V18,DGS30,VOL,REPO,AI,EQUITY_DIRECTORY,REHASH)
    originals={str(p):p.read_bytes() for p in paths}
    sha={k:hashlib.sha256(v).hexdigest() for k,v in originals.items()}
    content=[json.loads(originals[str(p)]) for p in paths]
    return content,sha

def build(sources,sha):
    overlay,_,_,_,_,_,_=sources
    r61=v61_build(*sources,hashes=sha)
    r59=v59_build(overlay)
    if (overlay.get("scores_are_expost_not_preregistered") is not True
        or overlay.get("historical_pit_source_bytes_independently_attested") is not False
        or overlay.get("full_11node_index_months")!=0
        or overlay.get("production_index_changed") is not False
        or r61.get("official_full_11node_AICS") is not None
        or r61.get("research_24m_independent_PIT_certified_nodes")!=0
        or r59.get("months_with_certified_full_11_node_AICS")!=0
        or r59.get("original_24_market_months")!=24):
        raise ValueError("Only actual 24-month unapproved research source history is allowed")
    market=overlay["monthly_last_weekday_market_proxy"]
    october=next((x for x in market if x["month"]==TARGET),None)
    if october is None or october["cutoff_date"]!=LATEST_CUTOFF:
        raise ValueError("No original October research score source")
    original=october["node_scores"]
    missing=october["missing_nodes"]
    if set(original)|set(missing)!=set(WEIGHTS) or set(original)&set(missing):
        raise ValueError("Original 11 weights must partition full and missing nodes")
    if len(original)!=8 or set(missing)!={"UST 30Y","Repo","AI Equities"}:
        raise ValueError("Original incomplete node roster altered; cannot fill from thin air")
    v61rows=r61["three_months_2026Q3_research_model_definition_risk"]
    research_oct=next(x for x in v61rows if x["month"]==TARGET)
    cases=research_oct["six_nonofficial_score_combinations"]
    center=next((x for x in cases if
        x["candidate_UST_rule"]=="Vol10" and
        x["candidate_Repo_rule"]=="RepoPremium20bpPostHoc"),None)
    if center is None:
        raise ValueError("Original V61 UST/Repo scenario not available")
    patches={
        "UST 30Y":center["hypothetical_UST30_nonofficial_score"],
        "Repo":center["hypothetical_Repo_nonofficial_score"],
        "AI Equities":center["hypothetical_AI_Equities_retro_nonofficial_score"],
    }
    why={
        "UST 30Y":"V60: original ALFRED DGS30, 20 actual daily rate changes; arbitrary 10 bp research scale",
        "Repo":"V61: original NY Fed SOFR / ALFRED IORB; +4bp / 20bp scale posthoc research assumption",
        "AI Equities":"V61: 4/7 retrospective one-session declining symbols; historical basket / actions not attested",
    }
    nodes=[]
    for name,weight in WEIGHTS.items():
        from_original=name in original
        score=Decimal(str(original[name]["score"])) if from_original else Decimal(str(patches[name]))
        if not Decimal(0)<=score<=Decimal(100):
            raise ValueError("Real source/proxy score outside admissible bound")
        nodes.append({
            "node":name,
            "weight":weight,
            "risk_score_0_100":_r(score),
            "raw_weighted_contribution":_r(Decimal(weight)*score/Decimal(100)),
            "hot_strictly_gt_60":bool(score>Decimal(60)),
            "source_status":"ORIGINAL_EXPOST_RESEARCH_PROXY_NOT_CERTIFIED" if from_original
                            else "ADDED_POSTHOC_SHADOW_UNAPPROVED_NOT_HISTORICALLY_ELIGIBLE",
            "source_eligible_proxy_date":original[name]["research_eligible_date"] if from_original else None,
            "source_policy_or_limitation":original[name]["source_policy"] if from_original else why[name],
            "is_official_certified_score":False,
        })
    hot=sum(x["hot_strictly_gt_60"] for x in nodes)
    raw=sum(Decimal(x["weight"])*Decimal(str(x["risk_score_0_100"]))/Decimal(100) for x in nodes)
    mult=multiplier(hot)
    estimate=raw*mult
    # Independently recompute with FULL ORIGINAL decimal precision (no
    # accidental entry/cash threshold change due to output rounding).
    exact=sum(
        Decimal(WEIGHTS[n])*(Decimal(str(original[n]["score"])) if n in original
                             else Decimal(str(patches[n])))/Decimal(100)
        for n in WEIGHTS
    )*mult
    if exact!=estimate:
        raise ValueError("Master component rounding changed true 11-node index")
    if _r(estimate)!=center["risk_if_ALL_nonapproved_shadows_assumed_NOT_REAL_AICS"]:
        raise ValueError("Master AICS fails original independent V61 11-node cross-check")
    if _r(estimate)!=489.33 or hot!=3 or mult!=Decimal("1.20"):
        raise ValueError("V61 original reference scenario was altered")
    boundaries=r59["monthly_24m_conditional_research_envelopes"]
    old_last=boundaries[-1]
    if old_last["month"]!=TARGET or old_last["conditional_full_index_lower_if_all_missing_scores_ZERO_BOUND_CASE"]!=322.06 or old_last["conditional_full_index_upper_if_all_missing_scores_100_BOUND_CASE"]!=801.07:
        raise ValueError("Original V59 exact incomplete-index interval changed")
    rows=[]
    for r in boundaries:
        rows.append({
            "month":r["month"],
            "month_original_research_node_count":r["known_node_count"],
            "source_covered_weight_of_1050":r["known_weight"],
            "observed_research_partial_raw_not_full":r["observed_partial_weighted_sum_not_full_index"],
            "conditional_original_AICS_lower":r["conditional_full_index_lower_if_all_missing_scores_ZERO_BOUND_CASE"],
            "conditional_original_AICS_upper":r["conditional_full_index_upper_if_all_missing_scores_100_BOUND_CASE"],
            "full_original_AICS":None,
            "full_eleven_node_research_shadow_if_all_source_assumptions":_r(estimate) if r["month"]==TARGET else None,
            "independently_PIT_certified":False,
        })
    scenario=[]
    for case in cases:
        scenario.append({
            "UST_scenario":case["candidate_UST_rule"],
            "Repo_scenario":case["candidate_Repo_rule"],
            "AI_equity_same_retro_score":case["hypothetical_AI_Equities_retro_nonofficial_score"],
            "shadow_AICS_11node":case["risk_if_ALL_nonapproved_shadows_assumed_NOT_REAL_AICS"],
            "hypothetical_old_threshold_zone_not_actionable":case["hypothetical_threshold_zone_NOT_ACTIONABLE"],
        })
    zones=set(x["hypothetical_old_threshold_zone_not_actionable"] for x in scenario)
    if len(zones)!=3:
        raise ValueError("Source-dependent three contradictory policy zones changed")
    if len(nodes)!=11 or sum(x["weight"] for x in nodes)!=TOTAL:
        raise ValueError("Not an original 11-node AICS formula")
    result={
        "schema":"aics-master-11-node-source-evidence-research-nowcast-v1",
        "research_document_version":"2026-11-22",
        "source_observed_market_cutoff":LATEST_CUTOFF,
        "as_of_knowledge":"2026-11-22; NOT model input strictly eligible at original October 2026 cutoff",
        "full_original_nodes":11,
        "original_weight_total":1050,
        "original_weights_changed":False,
        "hot_node_definition":"score strictly greater than 60/100",
        "original_hot_multiplier":float(mult),
        "hot_node_count":hot,
        "raw_11node_weighted_score":_r(raw),
        "illustrative_full_11node_shadow_AICS":_r(estimate),
        "illustrative_shadow_interpretation_if_old_450_500_thresholds_APPLIED":"WATCH_450_TO_500",
        "never_trading_signal_or_validated_historical_index":True,
        "original_expost_research_nodes":len(original),
        "additional_posthoc_nonapproved_hypothesis_nodes":len(patches),
        "additional_nodes_are_real_observed_SOURCE_rates_and_prices_but_NOT_official_scores":True,
        "source_to_score_posthoc_selection_has_seen_market_outcomes":True,
        "no_untouched_forward_oos_trading_accuracy_proven":True,
        "official_full_11node_AICS":None,
        "official_trading_zone":None,
        "production_promotion":"BLOCKED",
        "production_trades_created":False,
        "readiness_22_of_66":True,
        "independently_certified_nodes_out_of_11":0,
        "original_missing_nodes_lower_upper_conditional_on_V18_research":[322.06,801.07],
        "scenario_score_min_max_from_original_V61_six_rules":[
            min(x["shadow_AICS_11node"] for x in scenario),
            max(x["shadow_AICS_11node"] for x in scenario)],
        "hypothetical_score_scenarios_include_entry_watch_and_cash":True,
        "center_choice_is_original_V61_existing_research_rule_not_economic_validation":True,
        "fixed_11_node_component_table":nodes,
        "full_24month_original_index_missing_data_intervals_not_fabricated":rows,
        "six_already_computed_ust_repo_what_if_scenarios":scenario,
        "why_simple_3node_is_not_master_AICS":"Three-node score 43.05 is a separate component-only research diagnostic; the full original index always has 11 nodes and hot-multiplier. Never replace 11-node AICS with it.",
        "real_next_step":"Preserve full 11-node AICS, replace posthoc three nodes only on independent prospective first-seen approved sources, keep official index NULL until independently certified."
    }
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=OUT)
    a=parser.parse_args()
    source,sha=_read_sources()
    report=build(source,sha)
    report["source_sha256"]=sha
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items()
                      if k not in ("fixed_11_node_component_table",
                                   "full_24month_original_index_missing_data_intervals_not_fabricated",
                                   "six_already_computed_ust_repo_what_if_scenarios")},ensure_ascii=False))
    print("ELEVEN original AICS node contributions:")
    for n in report["fixed_11_node_component_table"]:
        print(n["node"],n["weight"],n["risk_score_0_100"],n["raw_weighted_contribution"],n["source_status"])
    return 0

if __name__=="__main__":
    raise SystemExit(main())
