"""Offline 11-node PIT integrity tests: no phantom 9/11, no weight changes."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_fill_11_nodes_pit import (
    NYFED, ALFRED_REVISIONS, SEC_REGISTRY, STATUS, UNIVERSE, WEIGHTS, audit,
)


class TestElevenNodePITGate(unittest.TestCase):
    def test_11_nodes_fixed_1050_and_no_score(self):
        result = audit()
        self.assertEqual(result["node_count"], 11)
        self.assertEqual(result["fixed_total_weight"], 1050)
        self.assertEqual(len(result["source_inventory"]), 11)
        self.assertFalse(result["reweight_after_ipo_permitted"])
        self.assertFalse(result["unobserved_nodes_renormalized"])
        self.assertTrue(all(x["node_score"] is None and not x["certified"]
                            for x in result["source_inventory"]))
        self.assertEqual(result["independently_certified_nodes"], 0)
        self.assertEqual(result["promotion"], "BLOCKED")
        self.assertIsNone(result["index_aics"])
        self.assertFalse(result["trades_created"])

    def test_all_source_leads_not_claimed_closed(self):
        result = audit()
        self.assertEqual(result["research_company_names"], 37)
        self.assertEqual(result["nyfed_repo"]["source_rows"], 2997)
        self.assertFalse(result["nyfed_repo"]["historical_release_vintages_attested"])
        self.assertTrue(result["nyfed_repo"]["current_capture_not_2018_to_2026_pit"])
        self.assertFalse(result["historical_alFred_monthly_vintage_coverage_from_2018_proven"])
        self.assertEqual(result["sec_sources"]["registry_documents"], 5)
        self.assertEqual(result["sec_sources"]["date_eligible"], 4)
        self.assertEqual(result["sec_sources"]["embargoed"], 1)
        self.assertIn("IORB", result["further_candidate_series"])
        self.assertIn("WPU0543", result["further_candidate_series"])

    def _mutated_file(self, source, edit, keyword):
        original = json.loads(source.read_text(encoding="utf-8"))
        edit(original)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "modified.json"
            path.write_text(json.dumps(original), encoding="utf-8")
            with self.assertRaises(ValueError) as raised:
                audit(**{keyword: path})
            return str(raised.exception)

    def test_node_weight_must_not_renormalize(self):
        self._mutated_file(STATUS, lambda x: x["node_progress"][0].__setitem__("weight", 149),
                           "status_path")

    def test_no_forged_node_stress_score(self):
        self._mutated_file(STATUS, lambda x: x["node_progress"][0].__setitem__("node_stress_score", 60),
                           "status_path")

    def test_no_forged_certification(self):
        self._mutated_file(STATUS, lambda x: x.__setitem__("independently_certified_nodes", 9),
                           "status_path")

    def test_no_forged_skill_or_index(self):
        for key in ("predictive_skill_score", "index_aics"):
            with self.subTest(key=key):
                self._mutated_file(STATUS, lambda x: x.__setitem__(key, 456),
                                   "status_path")

    def test_never_shorten_sec_embargo(self):
        self._mutated_file(
            SEC_REGISTRY,
            lambda x: x["documents"][-1].__setitem__("available_at", "2026-11-25"),
            "sec_path",
        )

    def test_nyfed_rehash_must_not_be_self_attested(self):
        self._mutated_file(
            NYFED, lambda x: x.__setitem__("independent_original_byte_rehash_passed", False),
            "nyfed_path",
        )
        self._mutated_file(
            NYFED, lambda x: x.__setitem__("market_stress_score", 42),
            "nyfed_path",
        )

    def test_research_lead_cannot_be_promoted_to_fact(self):
        self._mutated_file(
            UNIVERSE, lambda x: x["companies"][-1].__setitem__("model_eligible", True),
            "universe_path",
        )

    def test_power_ppi_revisions_are_reported_without_pit_promotion(self):
        out = audit()["alfred_iorb_power_revision_audit"]
        self.assertEqual(out["source_original_files_rehashed"], 48)
        self.assertEqual(out["repeated_source_observation_rows"], 39934)
        self.assertEqual(out["iorb_changed_value_events"], 0)
        self.assertEqual(out["industrial_power_ppi_changed_value_events"], 69)
        self.assertEqual(out["unique_power_ppi_observation_dates_revised"], 25)
        self.assertFalse(out["independent_release_timestamp_pit"])
        self.assertEqual(out["node_stress_scores"],
                         {"Repo": None, "Power/Data Centers": None})
        self.assertEqual(out["certification_milestones_advanced"], 0)

    def test_forged_revision_receipt_or_pit_promotion_fails(self):
        for field, value in (
            ("observed_revision_events_total", 0),
            ("original_provider_historical_publication_timestamps_independently_attested", True),
            ("independent_24_month_out_of_sample_proven", True),
            ("index_aics", 499),
            ("synthetic_or_interpolated_rows", 1),
        ):
            with self.subTest(field=field):
                self._mutated_file(
                    ALFRED_REVISIONS, lambda x: x.__setitem__(field, value),
                    "revision_path",
                )

    def test_only_original_weights_allowed(self):
        self.assertEqual(sum(WEIGHTS.values()), 1050)
        self.assertEqual(len(WEIGHTS), 11)


if __name__ == "__main__":
    unittest.main()
