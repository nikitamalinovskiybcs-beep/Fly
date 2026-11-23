"""Safeguard the adapted user-supplied AICS master runner."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.aics_master_pipeline import FROZEN_AS_OF, run_master


class TestMasterAudit(unittest.TestCase):
    def test_master_outputs_real_frozen_registry_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            report = run_master(FROZEN_AS_OF, output_dir=output)
            saved = json.loads((output / "aics_master_ci_report_2026-11-18.json").read_text())
            source = json.loads((output / "aics_11_node_free_source_pit_2026-11-18.json").read_text())
            self.assertEqual(report, saved)
            self.assertEqual(source["fixed_total_weight"], 1050)
            self.assertEqual(len(source["source_inventory"]), 11)
            self.assertEqual(report["source_sec_docs_embargoed"], 1)
            self.assertEqual(report["source_sec_docs_date_eligible"], 4)
            self.assertEqual(report["nyfed_original_archived_rows"], 2997)
            self.assertEqual(report["alfred_original_asof_source_files_rehashed"], 48)
            self.assertEqual(report["alfred_power_ppi_revision_events"], 69)
            self.assertEqual(report["alfred_power_ppi_unique_economic_dates_revised"], 25)
            self.assertEqual(report["alfred_iorb_revision_events"], 0)
            self.assertFalse(report["alfred_revision_historical_release_pit_attested"])
            self.assertFalse(report["collection_performed_by_master"])
            self.assertFalse(report["source_audit_as_of_relabeling_allowed"])
            self.assertIsNone(report["index_aics"])
            self.assertEqual(report["promotion"], "BLOCKED")
            self.assertFalse(report["trades_created"])

    def test_other_historical_cutoff_relabeling_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_master("2026-11-17", output_dir=Path(tmp))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_future_cutoff_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_master("2099-12-31", output_dir=Path(tmp))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_invalid_asof_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for invalid in ("not-a-date", "2026-02-30", "2026-11", ""):
                with self.subTest(value=invalid):
                    with self.assertRaises(ValueError):
                        run_master(invalid, output_dir=Path(tmp))

    def test_source_9_of_11_false_certification_rejected(self):
        source_stub = {
            "as_of": FROZEN_AS_OF,
            "fixed_total_weight": 1050,
            "node_count": 11,
            "independently_verified_pit_nodes": 0,
            "independently_certified_nodes": 9,
            "index_aics": 490,
            "predictive_skill_score": 0.92,
            "promotion": "CERTIFIED",
            "reweight_after_ipo_permitted": False,
            "source_inventory": [{"node_score": 90} for _ in range(11)],
        }
        with patch("scripts.aics_master_pipeline.audit", return_value=source_stub):
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    run_master(FROZEN_AS_OF, output_dir=Path(tmp))
                self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
