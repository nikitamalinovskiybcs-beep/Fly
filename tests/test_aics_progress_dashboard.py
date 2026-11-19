"""Strict unit tests for a project-management bar, never synthetic market data."""
import hashlib
import tempfile
import copy
import json
import unittest
from pathlib import Path

from scripts.aics_progress_dashboard import (
    WEIGHTS, GATES, checked_audit_evidence, build, as_markdown, DEFAULT_MANIFEST
)

ROOT = Path(__file__).resolve().parent.parent


def ledger():
    return json.loads((ROOT / DEFAULT_MANIFEST).read_text(encoding="utf-8"))


class TestAICSProgress(unittest.TestCase):
    def test_joint_review_counts_only_covered_passes(self):
        field = "independently_pit_attested_nodes"
        nodes = {"UST 30Y", "Repo"}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "review.json"
            evidence.write_text(json.dumps({
                "schema_version": "aics-shared-review-v1", "audit_field": field,
                "decisions": {
                    "UST 30Y": {"outcome": "passed", "basis": "review section 1"},
                    "Repo": {"outcome": "open", "basis": "review section 2"},
                },
            }), encoding="utf-8")
            entry = {"evidence_path": evidence.name,
                     "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}
            self.assertEqual(checked_audit_evidence(root, {field: [entry]}, field, nodes),
                             {"UST 30Y"})
            for entries, prior in [([entry, entry], nodes), ([entry], {"Repo"})]:
                with self.assertRaises(ValueError):
                    checked_audit_evidence(root, {field: entries}, field, prior)
            with self.assertRaises(ValueError):
                checked_audit_evidence(root, {"other": [entry]}, "other", nodes)

    def test_all_11_nodes_and_immutable_weights(self):
        self.assertEqual(len(WEIGHTS), 11)
        self.assertEqual(sum(WEIGHTS.values()), 1050)
        self.assertEqual(len(GATES), 6)
        self.assertEqual(WEIGHTS["Private Credit"], 150)
        self.assertEqual(WEIGHTS["Insurers"], 125)
        self.assertEqual(WEIGHTS["UST 30Y"], 125)

    def test_initial_evidence_milestones_are_objective(self):
        s = build(ROOT, ledger())
        self.assertEqual(s["total_nodes"], 11)
        self.assertEqual(s["registry_nodes"], 11)
        self.assertEqual(s["archived_candidate_nodes"], 11)
        self.assertEqual(s["milestones_completed"], 22)
        self.assertEqual(s["milestones_total"], 66)
        self.assertEqual(s["project_progress_pct"], 33.3)
        self.assertEqual(s["certification_pct"], 0)
        self.assertEqual(s["independently_certified_nodes"], 0)

    def test_insurers_stage2_depends_on_real_source_archive_receipt(self):
        status=build(ROOT, ledger())
        insurers=next(x for x in status["node_progress"] if x["node"] == "Insurers")
        self.assertEqual(insurers["completed_milestones"], 2)
        self.assertTrue(insurers["gates"]["raw_candidate_archive"])
        self.assertFalse(insurers["gates"]["independently_attested_pit"])
        self.assertEqual(status["raw_ir_archive_nodes"], ["AI Demand", "Hyperscalers", "Insurers", "Neoclouds", "Power/Data Centers", "SPV", "Semiconductors Supply"])

    def test_reject_raw_receipt_node_spoofing(self):
        m=ledger()
        m["independently_recalculated_raw_archive_receipts"][0]["node"]="SPV"
        with self.assertRaises(ValueError):
            build(ROOT,m)

    def test_reject_missing_original_ir_archive_receipt(self):
        m=ledger()
        m["independently_recalculated_raw_archive_receipts"][0]["receipt_path"]="../receipt.json"
        with self.assertRaises(ValueError):
            build(ROOT,m)

    def test_neocloud_and_spv_raw_archive_stages_do_not_imply_true_spv(self):
        s=build(ROOT, ledger())
        for name in ("Neoclouds", "SPV"):
            row=next(x for x in s["node_progress"] if x["node"] == name)
            self.assertEqual(row["completed_milestones"], 2)
            self.assertTrue(row["gates"]["raw_candidate_archive"])
            self.assertFalse(row["gates"]["independently_attested_pit"])
            self.assertFalse(row["gates"]["independent_certification"])
            self.assertIsNone(row["node_stress_score"])

    def test_reject_spv_or_neocloud_raw_receipt_spoof(self):
        m=ledger()
        m["independently_recalculated_raw_archive_receipts"][1]["node"]="AI Demand"
        with self.assertRaises(ValueError):
            build(ROOT,m)

    def test_reject_missing_neocloud_spv_archive_receipt(self):
        m=ledger()
        m["independently_recalculated_raw_archive_receipts"][1]["receipt_path"]="../fake.json"
        with self.assertRaises(ValueError):
            build(ROOT,m)

    def test_three_new_raw_node_archives_are_not_stress_scores(self):
        status=build(ROOT,ledger())
        for name in ("Hyperscalers","Semiconductors Supply","AI Demand"):
            node=next(x for x in status["node_progress"] if x["node"]==name)
            self.assertEqual(node["completed_milestones"],2)
            self.assertTrue(node["gates"]["raw_candidate_archive"])
            self.assertFalse(node["gates"]["independently_attested_pit"])
            self.assertFalse(node["gates"]["audited_node_scoring"])
            self.assertFalse(node["gates"]["untouched_24m_oos"])
            self.assertFalse(node["gates"]["independent_certification"])
            self.assertIsNone(node["node_stress_score"])

    def test_reject_third_raw_source_receipt_node_spoofing(self):
        m=ledger()
        m["independently_recalculated_raw_archive_receipts"][2]["node"]="AI Equities"
        with self.assertRaises(ValueError):
            build(ROOT,m)

    def test_reject_missing_original_seven_issuer_receipt(self):
        m=ledger()
        m["independently_recalculated_raw_archive_receipts"][2]["receipt_path"]="../not-a-receipt.json"
        with self.assertRaises(ValueError):
            build(ROOT,m)

    def test_power_original_archive_is_not_grid_stress_score(self):
        s=build(ROOT,ledger())
        row=next(x for x in s["node_progress"] if x["node"]=="Power/Data Centers")
        self.assertEqual(row["completed_milestones"],2)
        self.assertTrue(row["gates"]["raw_candidate_archive"])
        self.assertFalse(row["gates"]["independently_attested_pit"])
        self.assertFalse(row["gates"]["audited_node_scoring"])
        self.assertFalse(row["gates"]["untouched_24m_oos"])
        self.assertFalse(row["gates"]["independent_certification"])
        self.assertIsNone(row["node_stress_score"])

    def test_reject_power_receipt_node_spoof(self):
        m=ledger()
        m["independently_recalculated_raw_archive_receipts"][3]["node"]="AI Equities"
        with self.assertRaises(ValueError):
            build(ROOT,m)

    def test_reject_missing_original_power_archive(self):
        m=ledger()
        m["independently_recalculated_raw_archive_receipts"][3]["receipt_path"]="../bad.json"
        with self.assertRaises(ValueError):
            build(ROOT,m)

    def test_nasdaq_price_stage_two_has_no_pit_or_score(self):
        status = build(ROOT, ledger())
        self.assertEqual(status["raw_price_archive_nodes"], ["AI Equities"])
        equity = next(x for x in status["node_progress"] if x["node"] == "AI Equities")
        self.assertEqual(equity["completed_milestones"], 2)
        self.assertFalse(equity["gates"]["independently_attested_pit"])
        self.assertFalse(equity["gates"]["audited_node_scoring"])
        self.assertFalse(equity["gates"]["untouched_24m_oos"])
        self.assertFalse(equity["gates"]["independent_certification"])
        self.assertIsNone(equity["node_stress_score"])

    def test_reject_fake_equity_receipt_path(self):
        x = ledger()
        x["independently_recalculated_raw_archive_receipts"][-1]["receipt_path"] = "../fake.json"
        with self.assertRaises(ValueError):
            build(ROOT, x)

    def test_raw_archive_is_not_node_or_index_certification(self):
        s = build(ROOT, ledger())
        self.assertFalse(s["archive"]["independently_verified"])
        self.assertIsNone(s["index_aics"])
        self.assertIsNone(s["predictive_skill_score"])
        self.assertEqual(s["promotion"], "BLOCKED")
        self.assertFalse(s["trades_created"])
        for row in s["node_progress"]:
            self.assertIsNone(row["node_stress_score"])
            self.assertFalse(row["independently_certified"])

    def test_reject_unsupported_node_raw_promotion(self):
        m = ledger()
        m["research_archive"]["series_by_node"]["Insurers"] = ["SOFR"]
        with self.assertRaises(ValueError):
            build(ROOT, m)

    def test_reject_unsupported_archive_series(self):
        m = ledger()
        m["research_archive"]["series_by_node"]["Repo"] = ["DGS30"]
        with self.assertRaises(ValueError):
            build(ROOT, m)

    def test_reject_tampered_archive_hash(self):
        m = ledger()
        m["research_archive"]["archive_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            build(ROOT, m)

    def test_reject_unproven_pit_claim(self):
        m = ledger()
        m["independent_audit"]["independently_pit_attested_nodes"] = ["Private Credit"]
        with self.assertRaises(ValueError):
            build(ROOT, m)

    def test_reject_out_of_order_certification(self):
        m = ledger()
        m["independent_audit"]["independently_certified_nodes"] = [{
            "node": "Private Credit", "evidence_path": m["registry_path"],
            "evidence_sha256": "0" * 64
        }]
        with self.assertRaises(ValueError):
            build(ROOT, m)

    def test_reject_missing_registry_document(self):
        m = ledger()
        m["registry_path"] = "../not_approved.md"
        with self.assertRaises(ValueError):
            build(ROOT, m)

    def test_markdown_is_explicitly_non_certified(self):
        s = build(ROOT, ledger())
        md = as_markdown(s)
        self.assertIn("33.3%", md)
        self.assertIn("0.0%", md)
        self.assertIn("AICS = **N/A**", md)
        for name in WEIGHTS:
            self.assertIn(name, md)


if __name__ == "__main__":
    unittest.main()
