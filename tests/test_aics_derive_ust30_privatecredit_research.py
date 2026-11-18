"""No artificial economic observations in repository research; negative integrity tests only."""
import datetime as dt
import json
import tempfile
import unittest
import zipfile
from decimal import Decimal
from pathlib import Path

from scripts.aics_derive_ust30_privatecredit_research import (
    SourceIntegrityError, _date, _decimal, derive,
)
from scripts.aics_index import WEIGHTS


class TestUst30AndPrivateCreditSourceIntegrity(unittest.TestCase):
    def test_hundredth_percent_becomes_one_basis_point(self):
        self.assertEqual((Decimal("5.59") - Decimal("5.32")) * 100, Decimal("27.00"))

    def test_nonfinite_or_non_numeric_official_observation_rejected(self):
        for v in ("NaN", "Inf", "", None, ".", "no data"):
            with self.subTest(v=str(v)):
                with self.assertRaises(SourceIntegrityError):
                    _decimal(v)

    def test_invalid_date_rejected(self):
        for v in ("2026-02-30", "yesterday", None, ""):
            with self.subTest(v=str(v)):
                with self.assertRaises(SourceIntegrityError):
                    _date(v)

    def test_source_zip_or_receipt_must_rehash_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zippath = root / "bad.zip"
            with zipfile.ZipFile(zippath, "w") as z:
                z.writestr("manifest.json", "{}")
            receipt = root / "receipt.json"
            receipt.write_text(json.dumps({
                "schema_version": "aics-alfred-macro-research-recheck-v1",
                "scope": "REHASHED_ARCHIVED_ALFRED_SNAPSHOTS_NOT_PROVIDER_VINTAGE_ATTESTATION",
                "historical_pit_certified": False,
                "independent_provider_vintage_attestation": False,
                "score_eligible": False,
                "index_aics": None,
                "series_count": 4,
                "monthly_vintages_per_series": 24,
                "source_rows_total": 165913,
                "artifact_zip_sha256": "f" * 64,
            }))
            with self.assertRaisesRegex(SourceIntegrityError, "mismatch"):
                derive(zippath, receipt)

    def test_impossible_source_certification_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = root / "receipt.json"
            receipt.write_text(json.dumps({
                "schema_version": "aics-alfred-macro-research-recheck-v1",
                "scope": "REHASHED_ARCHIVED_ALFRED_SNAPSHOTS_NOT_PROVIDER_VINTAGE_ATTESTATION",
                "historical_pit_certified": True,
                "independent_provider_vintage_attestation": False,
                "score_eligible": False,
                "index_aics": None,
                "series_count": 4, "monthly_vintages_per_series": 24,
                "source_rows_total": 165913, "artifact_zip_sha256": "0" * 64,
            }))
            with self.assertRaises(SourceIntegrityError):
                derive(root / "absent.zip", receipt)

    def test_existing_aics_weights_and_certification_unchanged(self):
        self.assertEqual(len(WEIGHTS), 11)
        self.assertEqual(sum(WEIGHTS.values()), 1050)


if __name__ == "__main__":
    unittest.main()
