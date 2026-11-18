"""Research-only macro receipt safeguards, not provider vintage certification."""
import copy
import json
import unittest
from pathlib import Path

from scripts.aics_validate_alfred_macro_rehash import check_receipt

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "aics_data/research/alfred_macro_archive_rehash_2026_11_18.json"


class TestALFREDMacroReceipt(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads(PATH.read_text(encoding="utf-8"))

    def test_rehashed_original_registry_metadata_stays_uncertified(self):
        result = check_receipt(self.receipt)
        self.assertEqual(result["sources"], 4)
        self.assertEqual(result["vintage_months_per_series"], 24)
        self.assertEqual(result["archived_rows"], 165913)
        self.assertEqual(result["metadata_audit"], "PASS_RESEARCH_ONLY")
        self.assertFalse(result["source_zip_independently_rehashed_in_this_script"])
        self.assertFalse(result["historical_provider_pit_certified"])
        self.assertIsNone(result["index_aics"])
        self.assertEqual(result["promotion"], "BLOCKED")
        self.assertEqual({x["series_id"]: x["monthly_change_basis_points"]
                          for x in result["public_macro_changes"]},
                         {"DGS30": "-27.00", "SOFR": "6.00"})

    def test_never_publish_ice_credit_spread_values_in_public_receipt(self):
        for field, value in (("numeric_observations_publicly_republished", True),
                             ("source_license_public_redistribution_cleared", True),
                             ("sept_snapshot", {"value_percent": 12.3})):
            d = copy.deepcopy(self.receipt)
            d["series"][2][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                check_receipt(d)

    def test_no_model_score_promotion(self):
        for field, value in (("index_aics", 500), ("historical_pit_certified", True),
                             ("approved_investment_signal", True),
                             ("additional_project_milestones", 1)):
            d = copy.deepcopy(self.receipt)
            d[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                check_receipt(d)

    def test_reject_bad_vintage_dates_or_fabricated_delta(self):
        for field, value in (("month_end_asof_change_basis_points", 50),
                             ("source_rows", 10)):
            d = copy.deepcopy(self.receipt)
            d["series"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                check_receipt(d)
        d = copy.deepcopy(self.receipt)
        d["series"][0]["oct_snapshot"]["observation_date"] = "2026-11-01"
        with self.assertRaises(ValueError):
            check_receipt(d)

    def test_reject_mismatched_archive_identity_or_hash(self):
        d = copy.deepcopy(self.receipt)
        d["artifact_zip_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            check_receipt(d)
        d = copy.deepcopy(self.receipt)
        d["series"][3]["csv_sha256"] = "INVALID"
        with self.assertRaises(ValueError):
            check_receipt(d)


if __name__ == "__main__":
    unittest.main()
