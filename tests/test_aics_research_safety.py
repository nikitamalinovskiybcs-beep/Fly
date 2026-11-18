#!/usr/bin/env python3
"""Offline safety tests: no market data, no synthetic price or stress series."""
import json
import os
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

    def test_pit_collector_missing_key_is_explicit_and_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            env=os.environ.copy()
            env.pop("FRED_API_KEY",None)
            proc=subprocess.run([sys.executable,str(ROOT/"scripts/aics_collect_alfred_pit.py")],
                                cwd=folder,env=env,capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            manifest=json.loads((Path(folder)/"aics_data/pit/manifest.json").read_text())
            self.assertEqual(len(manifest["results"]),4)
            self.assertTrue(all(len(item["snapshots"])==24 for item in manifest["results"]))
            self.assertTrue(all(all(s["status"]=="missing_secret" for s in item["snapshots"])
                                for item in manifest["results"]))
            self.assertFalse(manifest["publishable"])
            self.assertIsNone(manifest["index_aics"])

    def test_pit_coverage_reports_missing_without_imputation(self):
        with tempfile.TemporaryDirectory() as folder:
            proc = subprocess.run([sys.executable, str(ROOT/"scripts/aics_pit_coverage_report.py")],
                                  cwd=folder, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report=json.loads((Path(folder)/"aics_data/pit/coverage_report.json").read_text())
            self.assertEqual(len(report["series"]),4)
            self.assertFalse(report["historical_snapshot_coverage_complete"])
            self.assertTrue(all(s["snapshots_downloaded_unverified"]==0 for s in report["series"]))
            self.assertIsNone(report["index_aics"])

    def test_alfred_historical_pit_blocks_missing_vintages(self):
        proc, _ = self.run_script("aics_validate_alfred_pit.py")
        self.assertNotEqual(proc.returncode, 0)

    def test_readiness_requires_historical_alfred(self):
        with tempfile.TemporaryDirectory() as folder:
            proc = subprocess.run([sys.executable, str(ROOT/"scripts/aics_research_readiness.py")],
                                  cwd=folder, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads((Path(folder)/"aics_data/research/readiness_report.json").read_text())
            self.assertIn("alfred_historical_snapshots_complete",data["blocking_checks"])
            self.assertIn("alfred_asof_structural_validation",data["blocking_checks"])

    def test_xbrl_validation_blocks_missing_sources(self):
        proc, _ = self.run_script("aics_validate_xbrl.py")
        self.assertNotEqual(proc.returncode, 0)

if __name__ == "__main__":
    unittest.main()
