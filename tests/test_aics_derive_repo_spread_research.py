"""No market numbers are generated here. Test only fail-closed archive handling."""
import json
import tempfile
import unittest
import zipfile
from decimal import Decimal
from pathlib import Path

from scripts.aics_derive_repo_spread_research import SourceError, dec, derive


class TestRepoResearchSpreadSafety(unittest.TestCase):
    def test_decimal_basis_point_exactness(self):
        self.assertEqual((dec("3.92") - dec("3.90")) * 100, Decimal("2.00"))
        self.assertEqual((dec("3.89") - dec("3.91")) * 100, Decimal("-2.00"))

    def test_missing_values_never_coerced_to_zero(self):
        for invalid in (None, True, False, float("nan"), float("inf"), "bad", {}):
            with self.subTest(value=str(invalid)):
                with self.assertRaises(SourceError):
                    dec(invalid)

    def test_rejects_unsupported_fake_receipts_before_reading_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "a.json"
            q = root / "b.json"
            p.write_text(json.dumps({"aics_index": 444}), encoding="utf-8")
            q.write_text(json.dumps({"aics_index": 444}), encoding="utf-8")
            with self.assertRaises(SourceError):
                derive(root / "alfred.zip", root / "nyfed.zip", p, q)

    def test_cannot_claim_pit_from_source_even_if_source_zip_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "alfred.json"
            q = root / "nyfed.json"
            p.write_text(json.dumps({
                "unique_original_raw_json_files": 48,
                "independent_historical_publication_time_pit_verified": True,
                "all_original_file_sha256_verified": True,
                "aics_index": None,
            }), encoding="utf-8")
            q.write_text(json.dumps({
                "total_raw_rows": 2997,
                "independent_original_byte_rehash_passed": True,
                "rate_publication_pit_attested": False,
                "aics_index": None,
            }), encoding="utf-8")
            with self.assertRaises(SourceError):
                derive(root / "alfred.zip", root / "nyfed.zip", p, q)

    def test_zip_sha_must_match_before_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "alfred.json"
            q = root / "nyfed.json"
            p.write_text(json.dumps({
                "unique_original_raw_json_files": 48,
                "independent_historical_publication_time_pit_verified": False,
                "all_original_file_sha256_verified": True,
                "aics_index": None,
                "merged_artifact_zip_sha256": "0"*64,
            }))
            q.write_text(json.dumps({
                "total_raw_rows": 2997,
                "independent_original_byte_rehash_passed": True,
                "rate_publication_pit_attested": False,
                "aics_index": None,
                "source_archive_zip_sha256": "1"*64,
            }))
            a = root / "alfred.zip"
            b = root / "nyfed.zip"
            with zipfile.ZipFile(a, "w") as z:
                z.writestr("manifest.json", "{}")
            with zipfile.ZipFile(b, "w") as z:
                z.writestr("manifest.json", "{}")
            with self.assertRaisesRegex(SourceError, "ZIP"):
                derive(a, b, p, q)


if __name__ == "__main__":
    unittest.main()
