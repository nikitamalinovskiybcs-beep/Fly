"""Strict unit tests for a project-management bar, never synthetic market data."""
import copy
import json
import unittest
from pathlib import Path

from scripts.aics_progress_dashboard import (
    WEIGHTS, GATES, build, as_markdown, DEFAULT_MANIFEST
)

ROOT = Path(__file__).resolve().parent.parent


def ledger():
    return json.loads((ROOT / DEFAULT_MANIFEST).read_text(encoding="utf-8"))


class TestAICSProgress(unittest.TestCase):
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
        self.assertEqual(s["archived_candidate_nodes"], 6)
        self.assertEqual(s["milestones_completed"], 17)
        self.assertEqual(s["milestones_total"], 66)
        self.assertEqual(s["project_progress_pct"], 25.8)
        self.assertEqual(s["certification_pct"], 0)
        self.assertEqual(s["independently_certified_nodes"], 0)

    def test_insurers_stage2_depends_on_real_source_archive_receipt(self):
        status=build(ROOT, ledger())
        insurers=next(x for x in status["node_progress"] if x["node"] == "Insurers")
        self.assertEqual(insurers["completed_milestones"], 2)
        self.assertTrue(insurers["gates"]["raw_candidate_archive"])
        self.assertFalse(insurers["gates"]["independently_attested_pit"])
        self.assertEqual(status["raw_ir_archive_nodes"], ["Insurers", "Neoclouds", "SPV"])

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
        self.assertIn("25.8%", md)
        self.assertIn("0.0%", md)
        self.assertIn("AICS = **N/A**", md)
        for name in WEIGHTS:
            self.assertIn(name, md)


if __name__ == "__main__":
    unittest.main()
