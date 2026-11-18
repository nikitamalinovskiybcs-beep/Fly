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
        self.assertEqual(s["archived_candidate_nodes"], 3)
        self.assertEqual(s["milestones_completed"], 14)
        self.assertEqual(s["milestones_total"], 66)
        self.assertEqual(s["project_progress_pct"], 21.2)
        self.assertEqual(s["certification_pct"], 0)
        self.assertEqual(s["independently_certified_nodes"], 0)

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
        self.assertIn("21.2%", md)
        self.assertIn("0.0%", md)
        self.assertIn("AICS = **N/A**", md)
        for name in WEIGHTS:
            self.assertIn(name, md)


if __name__ == "__main__":
    unittest.main()
