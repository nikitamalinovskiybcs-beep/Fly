"""Static receipt integrity tests, not a substitute for archive byte replay."""
import copy
import json
import unittest
from pathlib import Path

from scripts.aics_validate_sec_rehash_receipt import verify

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "aics_data/research/sec_primary_archive_independent_rehash_2026_11_18.json"


class TestSECSourceRehashReceipt(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(RECEIPT.read_text(encoding="utf-8"))

    def test_actual_sec_receipt_remains_research_only(self):
        r = verify(self.data)
        self.assertEqual(r["receipt_integrity"], "PASS_METADATA_AND_ARITHMETIC_ONLY")
        self.assertEqual(r["archived_sec_json"], 6)
        self.assertEqual(r["archived_sec_html"], 4)
        self.assertEqual(r["sec_candidate_observations"], 521)
        self.assertFalse(r["raw_zip_rehash_performed_by_this_script"])
        self.assertFalse(r["independently_verified_historical_pit"])
        self.assertEqual(r["promotion"], "BLOCKED")
        self.assertIsNone(r["index_aics"])
        self.assertEqual(
            {x["issuer"]: x["afs_to_assets_pct"]
             for x in r["asset_mix_research_only"]},
            {"MET": "42.4276", "PRU": "41.8031"})

    def test_change_any_node_promotion_or_progress_fails_closed(self):
        for field, value in (("index_aics", 480.5),
                             ("new_node_score", 17),
                             ("independently_certified_nodes", 1),
                             ("additional_project_milestones", 1),
                             ("promotion", "CERTIFIED")):
            d = copy.deepcopy(self.data)
            d[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify(d)

    def test_research_ratio_must_match_original_integer_facts(self):
        for field, value in (("assets_usd", 0),
                             ("afs_debt_securities_usd", 800000000000),
                             ("afs_to_assets_pct", 45.1234),
                             ("stress_score", 71)):
            d = copy.deepcopy(self.data)
            d["insurers"]["research_asset_mix"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify(d)

    def test_sec_available_at_embargo_is_exact_and_future_values_block(self):
        d = copy.deepcopy(self.data)
        d["insurers"]["research_asset_mix"][1]["available_at"] = "2026-11-17"
        with self.assertRaises(ValueError):
            verify(d)
        d = copy.deepcopy(self.data)
        d["neocloud_spv"]["date_excluded"]["available_at"] = "2026-11-18"
        with self.assertRaises(ValueError):
            verify(d)

    def test_companyfacts_lineage_hash_cannot_be_reassigned(self):
        d = copy.deepcopy(self.data)
        d["insurers"]["research_asset_mix"][0]["source_companyfacts_sha256"] = (
            d["insurers"]["research_asset_mix"][1]["source_companyfacts_sha256"])
        with self.assertRaises(ValueError):
            verify(d)

    def test_missing_raw_html_or_duplicate_sec_json_source_is_blocked(self):
        d = copy.deepcopy(self.data)
        d["neocloud_spv"]["original_sec_html_files"].pop()
        with self.assertRaises(ValueError):
            verify(d)
        d = copy.deepcopy(self.data)
        d["insurers"]["original_sec_json_files"][1]["kind"] = "submissions"
        with self.assertRaises(ValueError):
            verify(d)

    def test_receipt_does_not_conflate_internal_hash_with_provider_vintage(self):
        d = copy.deepcopy(self.data)
        d["insurers"]["independent_historical_pit_verified"] = True
        with self.assertRaises(ValueError):
            verify(d)
        d = copy.deepcopy(self.data)
        d["neocloud_spv"]["independently_verified_spv_contracts"] = 1
        with self.assertRaises(ValueError):
            verify(d)


if __name__ == "__main__":
    unittest.main()
