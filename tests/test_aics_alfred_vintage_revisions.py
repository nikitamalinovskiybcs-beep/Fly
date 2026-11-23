"""Artificial fixture-only tests; original ALFRED bytes are audited separately in CI."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.aics_audit_alfred_vintage_revisions import AuditError, analyze
from scripts.aics_collect_alfred_iorb_power import SERIES, month_ends


def fixture(directory: Path, *, changed=True, future=False):
    archive = directory / "originals.zip"
    receipt_path = directory / "receipt.json"
    records = []
    rows = {}
    schedule = month_ends()
    for sid in SERIES:
        for idx, day in enumerate(schedule):
            latest_value = "101.0" if sid == "WPU0543" and idx > 0 and changed else "100.0"
            raw = json.dumps({
                "realtime_start": day.isoformat(),
                "realtime_end": day.isoformat(),
                "count": 1,
                "observations": [{
                    "realtime_start": day.isoformat(),
                    "realtime_end": day.isoformat(),
                    "date": "2099-01-01" if future and sid == "WPU0543" and idx == 0
                        else "2018-01-01",
                    "value": latest_value,
                }],
            }).encode("utf-8")
            filename = f"{sid}_asof_{day.isoformat()}.json"
            rows[filename] = raw
            records.append({
                "series_id": sid, "as_of": day.isoformat(), "source_file": filename,
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_bytes": len(raw), "observation_rows": 1,
                "non_missing_observations": 1,
            })
    manifest = {
        "original_files": records, "unique_genuine_asof_snapshots": 48,
        "replaced_or_synthetically_interpolated_snapshots": 0,
        "independent_provider_publication_timestamp_pit": False,
        "index_aics": None, "promotion": "BLOCKED",
    }
    mbytes = json.dumps(manifest).encode("utf-8")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as f:
        for name, raw in rows.items():
            f.writestr(name, raw)
        f.writestr("manifest.json", mbytes)
    receipt = {
        "schema_version": "aics-alfred-iorb-power-independent-rehash-receipt-v1",
        "unique_original_raw_json_files": 48,
        "independent_historical_publication_time_pit_verified": False,
        "all_original_file_sha256_verified": True,
        "aics_index": None, "aics_promotion": "BLOCKED",
        "merged_artifact_zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "merged_manifest_sha256": hashlib.sha256(mbytes).hexdigest(),
        "original_provider_response_observation_rows": 48,
        "merged_workflow_run_id": 100, "merged_artifact_id": 200,
    }
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return archive, receipt_path


class TestStrictOriginalALFREDRevisionAudit(unittest.TestCase):
    def test_one_real_revision_comparison_in_test_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, receipt = fixture(Path(tmp))
            report = analyze(archive, receipt)
            self.assertEqual(report["original_provider_files_rehashed"], 48)
            self.assertEqual(report["recounted_original_observation_rows"], 48)
            self.assertEqual(report["observed_revision_event_count"], 1)
            self.assertEqual(report["series"]["IORB"]["changed_existing_nonmissing_observations"], 0)
            self.assertEqual(report["series"]["WPU0543"]["changed_existing_nonmissing_observations"], 1)
            self.assertEqual(len(report["series"]["WPU0543"]["transitions"]), 23)
            self.assertEqual(report["observed_cross_vintage_revisions"][0]["delta"], "1.0")
            self.assertTrue(report["retrospective_api_asof_replay_only"])
            self.assertFalse(report["independent_contemporaneous_publication_proof"])
            self.assertEqual(report["promotion"], "BLOCKED")
            self.assertIsNone(report["index_aics"])
            self.assertEqual(report["certified_node_stress_scores"],
                             {"Repo": None, "Power/Data Centers": None})

    def test_no_revisions_is_zero_not_fabricated(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, receipt = fixture(Path(tmp), changed=False)
            report = analyze(archive, receipt)
            self.assertEqual(report["observed_revision_event_count"], 0)
            self.assertEqual(report["synthetically_filled_rows"], 0)

    def test_mutated_zip_fails_independent_archive_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, receipt = fixture(Path(tmp))
            with archive.open("ab") as out:
                out.write(b"tampered")
            with self.assertRaisesRegex(AuditError, "ZIP"):
                analyze(archive, receipt)

    def test_wrong_raw_sha_fails_even_if_zip_hash_rehashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, receipt = fixture(Path(tmp))
            files = {}
            with zipfile.ZipFile(archive) as z:
                for name in z.namelist():
                    files[name] = z.read(name)
            bad = json.loads(files["IORB_asof_2026-10-31.json"])
            bad["observations"][0]["value"] = "99.0"
            files["IORB_asof_2026-10-31.json"] = json.dumps(bad).encode()
            with zipfile.ZipFile(archive, "w") as z:
                for name, raw in files.items():
                    z.writestr(name, raw)
            rec = json.loads(receipt.read_text())
            rec["merged_artifact_zip_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
            receipt.write_text(json.dumps(rec))
            with self.assertRaisesRegex(AuditError, "SHA mismatch"):
                analyze(archive, receipt)

    def test_future_observation_even_if_file_hashes_adjusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, receipt = fixture(Path(tmp), future=True)
            with self.assertRaisesRegex(AuditError, "chronology"):
                analyze(archive, receipt)

    def test_refuse_forged_original_publication_pit(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, receipt = fixture(Path(tmp))
            rec = json.loads(receipt.read_text())
            rec["independent_historical_publication_time_pit_verified"] = True
            receipt.write_text(json.dumps(rec))
            with self.assertRaisesRegex(AuditError, "receipt mismatch"):
                analyze(archive, receipt)

    def test_refuse_claimed_market_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, receipt = fixture(Path(tmp))
            rec = json.loads(receipt.read_text())
            rec["aics_index"] = 475
            receipt.write_text(json.dumps(rec))
            with self.assertRaisesRegex(AuditError, "receipt mismatch"):
                analyze(archive, receipt)


if __name__ == "__main__":
    unittest.main()
