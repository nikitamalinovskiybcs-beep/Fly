#!/usr/bin/env python3
"""Offline safety tests: no market data, no synthetic price or stress series."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class AicsResearchSafetyTests(unittest.TestCase):
    def run_script(self, name):
        with tempfile.TemporaryDirectory() as folder:
            script = ROOT / "scripts" / name
            return subprocess.run([sys.executable, str(script)],
                                  cwd=folder, text=True, capture_output=True, check=False), Path(folder)

    def test_coverage_fails_closed_without_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            proc = subprocess.run([sys.executable, str(ROOT/"scripts/aics_audit_node_coverage.py")],
                                  cwd=folder, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads((Path(folder)/"aics_data/research/node_coverage.json").read_text())
            self.assertEqual(data["fixed_weight_sum"], 1050)
            self.assertEqual(len(data["nodes"]), 11)
            self.assertEqual(data["validated_nodes"], 0)
            self.assertIsNone(data["index_aics"])
            self.assertEqual(data["promotion"], "BLOCKED")
            self.assertFalse(data["production_weights_changed"])
            self.assertFalse(data["trades_created"])

    def test_readiness_never_promotes_without_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            proc = subprocess.run([sys.executable, str(ROOT/"scripts/aics_research_readiness.py")],
                                  cwd=folder, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads((Path(folder)/"aics_data/research/readiness_report.json").read_text())
            self.assertFalse(data["ready_for_production"])
            self.assertIsNone(data["index_aics"])
            self.assertIsNone(data["model_score"])
            self.assertIn("chronological_24m_oos_validated", data["blocking_checks"])
            self.assertIn("committee_approval_recorded", data["blocking_checks"])

    def test_ten_stage_receipt_blocks_missing_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            proc = subprocess.run([sys.executable, str(ROOT/"scripts/aics_ten_stage_receipt.py")],
                                  cwd=folder, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads((Path(folder)/"aics_data/research/ten_stage_receipt.json").read_text())
            self.assertEqual(data["total"], 10)
            self.assertEqual(data["passed"], 0)
            self.assertEqual(len(data["stages"]), 10)
            self.assertFalse(data["ready_for_production"])
            self.assertIsNone(data["index_aics"])
            self.assertFalse(data["trades_created"])

    def test_evidence_validation_blocks_missing_sources(self):
        proc, _ = self.run_script("aics_validate_evidence.py")
        self.assertNotEqual(proc.returncode, 0)

    def test_xbrl_validation_blocks_missing_sources(self):
        proc, _ = self.run_script("aics_validate_xbrl.py")
        self.assertNotEqual(proc.returncode, 0)

if __name__ == "__main__":
    unittest.main()
