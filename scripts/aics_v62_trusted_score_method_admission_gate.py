"""AICS V62: TRUSTED source-to-score method admission; no self-approval.

Old aics_score_reproducibility_gate can output a numerical candidate for
untrusted all-11-node user attestations of PIT. Only a separately reviewed
and pinned method registry can ever authorize a trusted official AICS.
All 11 methods are currently UNAPPROVED. This historical registry cannot
be promoted by input fields, source URI, SHA-shaped strings or backdated
official declarations. Explicit code & independent governance revision
required before future approvals.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from scripts.aics_score_reproducibility_gate import WEIGHTS,evaluate as candidate_arithmetic
from scripts.aics_v61_repo_ai_source_to_score_model_risk import (
    V18,DGS30,VOL,REPO,AI,EQUITY_DIRECTORY,REHASH,build as v61_build
)

REGISTRY=Path("aics_data/governance/aics_v62_official_score_method_registry_2026-11-22.json")
STATUS=Path("aics_data/progress/status.json")
OUT=Path("aics_data/governance/aics_v62_trusted_score_method_admission_2026-11-22.json")
PIN="240e5bcd1bbaf1cf808cc184485e9b51956eb8a3"
SCHEMA="aics-v62-trusted-score-method-governance-registry-v1"
EXPECTED_ZONES=(
    "HYPOTHETICAL_ENTRY_LT_450_NOT_ACTIONABLE",
    "HYPOTHETICAL_WATCH_450_TO_500_NOT_ACTIONABLE",
    "HYPOTHETICAL_CASH_GT_500_NOT_ACTIONABLE",
)
assert sum(WEIGHTS.values())==1050 and len(WEIGHTS)==11

def git_blob_sha(raw):
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii")+raw).hexdigest()

def registry_frozen(path=REGISTRY):
    if path.resolve()!=REGISTRY.resolve():
        raise ValueError("Unpinned governance registry path substitution")
    raw=path.read_bytes()
    if git_blob_sha(raw)!=PIN:
        raise ValueError("Frozen registry content digest changed; new approval requires reviewed version")
    r=json.loads(raw)
    if (r.get("schema")!=SCHEMA or r.get("recorded_at_date")!="2026-11-22"
        or r.get("approved_method_count")!=0
        or r.get("independently_certified_method_count")!=0
        or r.get("source_pit_independently_attested_node_count")!=0
        or r.get("official_11node_weight_total")!=1050
        or r.get("official_hot_threshold_score_strictly_gt")!=60
        or r.get("official_entry_if_below")!=450
        or r.get("official_exit_if_above")!=500
        or r.get("production_trades_allowed") is not False
        or r.get("prohibit_backdating_historical_method_approval") is not True
        or r.get("pre_register_method_before_future_evaluation") is not True):
        raise ValueError("Governance method approval must not be self asserted")
    nodes=r.get("nodes",[])
    if len(nodes)!=11 or len({n.get("name") for n in nodes})!=11:
        raise ValueError("Original 11-node governance roster missing/duplicated")
    for n in nodes:
        if (n.get("name") not in WEIGHTS or n.get("weight")!=WEIGHTS[n["name"]]
            or n.get("admission_status")!="UNAPPROVED"
            or n.get("old_2024_2026_pit_retroactive_approval") is not False
            or any(n.get(key) is not None for key in (
                "approved_method_version","approved_code_sha256","approved_effective_from_utc",
                "independent_source_pit_attestation_reference","committee_approval_reference",
                "untouched_forward_validation_reference"))):
            raise ValueError("Unreviewed official method or historical PIT promotion")
    return r,hashlib.sha256(raw).hexdigest()

def verify_progress(status):
    if (status.get("schema_version")!="aics-progress-status-v1"
        or status.get("scope")!="PROJECT_MILESTONES_NOT_MODEL_QUALITY"
        or status.get("total_nodes")!=11 or status.get("total_weight")!=1050
        or status.get("milestones_completed")!=22 or status.get("milestones_total")!=66
        or status.get("source_pit_attested_nodes")!=0
        or status.get("audited_scoring_nodes")!=0
        or status.get("untouched_24m_oos_nodes")!=0
        or status.get("independently_certified_nodes")!=0
        or status.get("index_aics") is not None
        or status.get("promotion")!="BLOCKED"
        or status.get("trades_created") is not False
        or len(status.get("node_progress",[]))!=11):
        raise ValueError("Independent project progress cannot be relabeled as certified AICS")
    seen=set()
    for n in status["node_progress"]:
        name=n.get("node")
        if name in seen or name not in WEIGHTS or n.get("weight")!=WEIGHTS[name]:
            raise ValueError("Malformed original node progress roster")
        seen.add(name)
        if (n.get("independently_certified") is not False
            or n.get("node_stress_score") is not None
            or any(n.get("gates",{}).get(key) is not False for key in (
                "independently_attested_pit","audited_node_scoring",
                "untouched_24m_oos","independent_certification"))):
            raise ValueError("Unverified individual AICS node promotion")
    return status["milestones_completed"],status["milestones_total"]

def actual_v61_source_report():
    p=(V18,DGS30,VOL,REPO,AI,EQUITY_DIRECTORY,REHASH)
    data={str(path):path.read_bytes() for path in p}
    hashes={name:hashlib.sha256(raw).hexdigest() for name,raw in data.items()}
    return v61_build(*(json.loads(data[str(path)]) for path in p),hashes=hashes)

def gate(registry,status,v61,*,candidate=None,registry_sha256=None):
    complete,total=verify_progress(status)
    if (registry.get("schema")!=SCHEMA
        or len(registry.get("nodes",[]))!=11
        or any(n.get("admission_status")!="UNAPPROVED" or
               n.get("approved_method_version") is not None
               for n in registry["nodes"])):
        raise ValueError("Only the original unapproved V62 registry is admissible")
    if (v61.get("schema")!="aics-v61-original-repo-and-ai-source-gated-six-model-rule-ambiguity-v1"
        or v61.get("real_repo_original_monthly_observations")!=24
        or v61.get("ust30_actual_monthly_observations_already")!=24
        or v61.get("real_nasdaq_equity_retro_session_months")!=3
        or v61.get("scenarios_calculated_real_original_source_not_real_scores")!=18
        or v61.get("official_full_11node_AICS") is not None
        or v61.get("research_24m_independent_PIT_certified_nodes")!=0
        or v61.get("trading_approved") is not False):
        raise ValueError("V61 original-source post-hoc uncertainty was overwritten")
    months=v61.get("three_months_2026Q3_research_model_definition_risk",[])
    if len(months)!=3 or set(months[-1].get("hypothetical_zones",[]))!=set(EXPECTED_ZONES):
        raise ValueError("Original October model rule ambiguity altered")
    upstream=None
    claims=[]
    if candidate is not None:
        if not isinstance(candidate,dict):
            raise ValueError("Candidate score must be JSON object")
        result=candidate_arithmetic(candidate)
        upstream=result["index_aics"]
        for name,node in candidate.get("nodes",{}).items():
            if name in WEIGHTS and isinstance(node,dict) and isinstance(node.get("evidence"),dict):
                if node["evidence"].get("independently_verified_pit") is True:
                    claims.append(name)
    blockers={}
    for n in registry["nodes"]:
        name=n["name"]
        reason=("UST original DGS30 source exists; approve source-to-score economic method and historical first-delivery PIT"
                if name=="UST 30Y" else
                "Repo original 24-month rates exist; SOFR-IORB alone is not a certified node-risk scale"
                if name=="Repo" else
                "AI one-session prices received after historical session; member roster and corporate actions unverified"
                if name=="AI Equities" else
                "Approve precommitted source-to-score formula, provider-first-delivery PIT, independent future validation")
        blockers[name]={"official_weight":n["weight"],"trusted_method":False,
                        "independent_source_PIT":False,"future_oos":False,
                        "committee_approval":False,"first_remediation":reason}
    return {
        "schema":"aics-v62-11node-trusted-method-admission-report-v1",
        "as_of":"2026-11-22",
        "pinned_governance_git_blob_sha1":PIN,
        "actual_governance_file_sha256":registry_sha256,
        "legacy_candidate_arithmetic_value_NOT_OFFICIAL":upstream,
        "candidate_claimed_independent_PIT_count_NOT_VERIFIED":len(claims),
        "candidate_claimed_PIT_nodes_NOT_VERIFIED":sorted(claims),
        "trusted_method_count":0,
        "independent_PIT_certified_node_count":0,
        "original_node_count":11,
        "original_weights_total":1050,
        "original_entry_threshold":450,
        "original_cash_threshold":500,
        "official_AICS":None,
        "production_promotion":"BLOCKED",
        "can_candidate_self_attest_into_official_index":False,
        "historical_source_to_score_method_can_be_backdated":False,
        "v61_original_Repo_source_months":24,
        "v61_original_UST_source_months":24,
        "v61_AI_retro_price_months":3,
        "v61_Oct_2026_three_conflicting_research_zones":list(EXPECTED_ZONES),
        "source_to_score_ambiguity_still_unresolved":True,
        "project_readiness_milestones":[complete,total],
        "eleven_individual_admission_blockers":blockers,
        "trading_action":None,
        "trades_created":False,
        "conductor_next_action":"Versioned independent method specification + first-delivery PIT proofs; never backfill old index or promote V61 hypothetical zones"
    }

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-json",type=Path)
    parser.add_argument("--out",type=Path,default=OUT)
    a=parser.parse_args()
    registry,sha=registry_frozen()
    status=json.loads(STATUS.read_text(encoding="utf-8"))
    original=actual_v61_source_report()
    proposal=json.loads(a.candidate_json.read_text(encoding="utf-8")) if a.candidate_json else None
    result=gate(registry,status,original,candidate=proposal,registry_sha256=sha)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in (
        "eleven_individual_admission_blockers","candidate_claimed_PIT_nodes_NOT_VERIFIED")},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
