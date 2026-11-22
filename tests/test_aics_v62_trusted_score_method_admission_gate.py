"""AICS V62 governance regression tests: fabricated input for safety only.

The 11-node 525.0 'score' in fixture is synthetic, represents NO observed
market event, and MUST NOT be published as any actual AICS.
"""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS,evaluate as old_evaluate
from scripts.aics_v62_trusted_score_method_admission_gate import (
    REGISTRY,STATUS,PIN,git_blob_sha,registry_frozen,verify_progress,
    actual_v61_source_report,gate
)


def counterfeit_claims_for_security_test():
    # Pure unit-test canary: every source URI is nonexistent and PIT is fake.
    # It must show the old arithmetic calculation isn't independent approval.
    return {"as_of":"2026-11-18","nodes":{
        name:{"score":50,"evidence":{
            "source_uri":"https://example.invalid/FAKE-UNIT-TEST-NOT-REAL",
            "source_sha256":hashlib.sha256(b"SYNTHETIC_TEST_BYTES").hexdigest(),
            "available_at":"2026-11-01",
            "independently_verified_pit":True,
            "score_method_version":"UNREGISTERED-UNIT-TEST-FAKE",
            "training_cutoff":"2026-10-31"}}
        for name in WEIGHTS
    }}


class AdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry,cls.sha=registry_frozen()
        cls.status=json.loads(STATUS.read_text(encoding="utf-8"))
        cls.actual_v61=actual_v61_source_report()
        cls.output=gate(cls.registry,cls.status,cls.actual_v61,registry_sha256=cls.sha)

    def test_original_methods_unapproved_and_real_status_22_of_66(self):
        r=self.output
        self.assertEqual(r["project_readiness_milestones"],[22,66])
        self.assertEqual(r["original_node_count"],11)
        self.assertEqual(r["original_weights_total"],1050)
        self.assertEqual(r["trusted_method_count"],0)
        self.assertEqual(r["independent_PIT_certified_node_count"],0)
        self.assertIsNone(r["official_AICS"])
        self.assertEqual(r["production_promotion"],"BLOCKED")
        self.assertFalse(r["trades_created"])
        self.assertIsNone(r["trading_action"])
        self.assertFalse(r["can_candidate_self_attest_into_official_index"])

    def test_old_arithmetic_accepts_fake_pit_flags_but_new_gate_denies(self):
        candidate=counterfeit_claims_for_security_test()
        old=old_evaluate(candidate)
        self.assertEqual(old["index_aics"],525)
        self.assertEqual(old["promotion"],"BLOCKED")
        now=gate(self.registry,self.status,self.actual_v61,candidate=candidate)
        self.assertEqual(now["legacy_candidate_arithmetic_value_NOT_OFFICIAL"],525)
        self.assertEqual(now["candidate_claimed_independent_PIT_count_NOT_VERIFIED"],11)
        self.assertEqual(now["candidate_claimed_PIT_nodes_NOT_VERIFIED"],sorted(WEIGHTS))
        self.assertIsNone(now["official_AICS"])
        self.assertIsNone(now["trading_action"])
        self.assertEqual(now["production_promotion"],"BLOCKED")
        self.assertFalse(now["trades_created"])

    def test_frozen_registry_hash_against_real_git_blob_sha(self):
        raw=REGISTRY.read_bytes()
        self.assertEqual(git_blob_sha(raw),PIN)
        self.assertEqual(len(self.registry["nodes"]),11)
        self.assertEqual(len({x["name"] for x in self.registry["nodes"]}),11)
        self.assertEqual(sum(x["weight"] for x in self.registry["nodes"]),1050)
        self.assertEqual(self.output["pinned_governance_git_blob_sha1"],PIN)
        self.assertEqual(self.output["actual_governance_file_sha256"],hashlib.sha256(raw).hexdigest())

    def test_mutating_signature_or_self_approving_registry_cannot_pass_freeze(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"another_method_registry.json"
            p.write_bytes(REGISTRY.read_bytes())
            with self.assertRaisesRegex(ValueError,"Unpinned governance registry"):
                registry_frozen(p)
        wrong=copy.deepcopy(self.registry)
        wrong["nodes"][2]["admission_status"]="APPROVED"
        with self.assertRaises(ValueError):
            gate(wrong,self.status,self.actual_v61)
        wrong=copy.deepcopy(self.registry)
        wrong["nodes"][2]["approved_method_version"]="V60"
        with self.assertRaises(ValueError):
            gate(wrong,self.status,self.actual_v61)

    def test_candidate_including_bad_future_or_missing_node_never_trusted(self):
        fake=counterfeit_claims_for_security_test()
        fake["nodes"]["Repo"]["evidence"]["available_at"]="2026-11-19"
        r=gate(self.registry,self.status,self.actual_v61,candidate=fake)
        self.assertIsNone(r["legacy_candidate_arithmetic_value_NOT_OFFICIAL"])
        self.assertIsNone(r["official_AICS"])
        fake=counterfeit_claims_for_security_test()
        fake["nodes"].pop("Repo")
        r=gate(self.registry,self.status,self.actual_v61,candidate=fake)
        self.assertIsNone(r["official_AICS"])
        self.assertIsNone(r["legacy_candidate_arithmetic_value_NOT_OFFICIAL"])

    def test_unapproved_real_source_exists_for_ust_repo_ai_but_not_valid_risk(self):
        r=self.output
        self.assertEqual(r["v61_original_Repo_source_months"],24)
        self.assertEqual(r["v61_original_UST_source_months"],24)
        self.assertEqual(r["v61_AI_retro_price_months"],3)
        self.assertEqual(len(r["v61_Oct_2026_three_conflicting_research_zones"]),3)
        blocked=r["eleven_individual_admission_blockers"]
        self.assertEqual(set(blocked),set(WEIGHTS))
        for n in ("UST 30Y","Repo","AI Equities"):
            self.assertFalse(blocked[n]["trusted_method"])
            self.assertFalse(blocked[n]["independent_source_PIT"])
            self.assertFalse(blocked[n]["committee_approval"])
        self.assertTrue(r["source_to_score_ambiguity_still_unresolved"])
        self.assertFalse(r["historical_source_to_score_method_can_be_backdated"])

    def test_official_policy_not_downgraded_when_progress_fake_approved(self):
        s=copy.deepcopy(self.status)
        s["independently_certified_nodes"]=1
        with self.assertRaises(ValueError):
            verify_progress(s)
        s=copy.deepcopy(self.status)
        s["node_progress"][0]["gates"]["audited_node_scoring"]=True
        with self.assertRaisesRegex(ValueError,"Unverified individual"):
            gate(self.registry,s,self.actual_v61)
        s=copy.deepcopy(self.status)
        s["index_aics"]=480
        with self.assertRaises(ValueError):
            gate(self.registry,s,self.actual_v61)

    def test_revised_v61_scenarios_cannot_seem_to_pass(self):
        r=copy.deepcopy(self.actual_v61)
        r["three_months_2026Q3_research_model_definition_risk"][-1]["hypothetical_zones"]=[
            "HYPOTHETICAL_WATCH_450_TO_500_NOT_ACTIONABLE"]
        with self.assertRaisesRegex(ValueError,"rule ambiguity"):
            gate(self.registry,self.status,r)
        r=copy.deepcopy(self.actual_v61)
        r["official_full_11node_AICS"]=500
        with self.assertRaisesRegex(ValueError,"uncertainty was overwritten"):
            gate(self.registry,self.status,r)

    def test_complete_five_equivalent_candidate_scores_not_published(self):
        candidate=counterfeit_claims_for_security_test()
        for i,name in enumerate(WEIGHTS):
            candidate["nodes"][name]["score"]=61 if i<3 else 40
        upstream=old_evaluate(candidate)
        self.assertIsNotNone(upstream["index_aics"])
        self.assertEqual(upstream["hot_nodes"],3)
        now=gate(self.registry,self.status,self.actual_v61,candidate=candidate)
        self.assertIsNone(now["official_AICS"])
        self.assertEqual(now["candidate_claimed_independent_PIT_count_NOT_VERIFIED"],11)
        self.assertTrue(now["source_to_score_ambiguity_still_unresolved"])

if __name__=="__main__":
    unittest.main()
