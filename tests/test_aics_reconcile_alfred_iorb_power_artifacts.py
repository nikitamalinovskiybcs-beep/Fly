"""Offline lossless-merge fixtures; never feed these samples to market models."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_collect_alfred_iorb_power import SERIES, month_ends
from scripts.aics_reconcile_alfred_iorb_power_artifacts import reconcile


def fake_original(date: str, value: str = "1") -> bytes:
    return json.dumps({
        "realtime_start": date, "realtime_end": date, "count": 1,
        "observations": [{
            "realtime_start": date, "realtime_end": date,
            "date": "2018-01-01", "value": value,
        }],
    }).encode()


def make_fixture(directory: Path, blocked: set[tuple[str, str]],
                 drift: dict | None = None):
    directory.mkdir(parents=True)
    results, errors = [], []
    for series in SERIES:
        for date in month_ends():
            day = date.isoformat()
            key = (series, day)
            if key in blocked:
                errors.append({"series_id": series, "as_of": day, "status": "HTTP_429"})
                results.append({"series_id": series, "as_of": day,
                                "status": "BLOCKED", "failure_code": "HTTP_429",
                                "stress_score_eligible": False})
                continue
            filename = f"{series}_asof_{day}.json"
            raw = fake_original(day, (drift or {}).get(key, "1"))
            (directory / filename).write_bytes(raw)
            results.append({
                "series_id": series, "as_of": day,
                "raw_file": filename, "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "rows": 1, "non_missing_observations": 1,
                "status": "downloaded_unverified",
            })
    (directory / "manifest.json").write_text(json.dumps({
        "schema_version": "aics-alfred-iorb-power-asof-research-v1",
        "research_as_of": "2026-11-18",
        "captured_at_utc": "2026-11-18T21:00:00Z",
        "expected_snapshots": 48, "successful_snapshots": 48 - len(blocked),
        "all_sources_downloaded": len(blocked) == 0,
        "blocked": errors, "series_results": results,
        "provider_publication_lag_pit_attested": False,
        "aics_index": None, "promotion": "BLOCKED",
    }), encoding="utf-8")


class TestCrossRunReconciliation(unittest.TestCase):
    B1 = {("IORB", "2025-03-31")}
    B2 = {("WPU0543", f"2025-{m:02d}-{last}") for m, last in
          [(2, 28), (3, 31), (4, 30), (5, 31), (6, 30)]}

    def sources(self, base: Path, *, drift=None, extra_missing=None):
        one, two = base / "a", base / "b"
        make_fixture(one, self.B1)
        make_fixture(two, self.B2 | (extra_missing or set()), drift=drift)
        return one, two

    def test_exact_48_real_source_bytes_selected_and_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one, two = self.sources(root)
            out = root / "output"
            manifest = reconcile(one, two, out)
            self.assertEqual(manifest["unique_genuine_asof_snapshots"], 48)
            self.assertEqual(manifest["identical_overlap_files"], 42)
            self.assertEqual(manifest["replaced_or_synthetically_interpolated_snapshots"], 0)
            self.assertEqual(manifest["iorb_snapshots"], 24)
            self.assertEqual(manifest["industrial_power_ppi_snapshots"], 24)
            self.assertEqual(len(manifest["original_files"]), 48)
            self.assertFalse(manifest["independent_provider_publication_timestamp_pit"])
            self.assertFalse(manifest["original_2018_release_vintages_verified"])
            self.assertIsNone(manifest["index_aics"])
            self.assertEqual(manifest["promotion"], "BLOCKED")
            self.assertFalse(manifest["trades_created"])
            for entry in manifest["original_files"]:
                name = entry["source_file"]
                selected = one if entry["source_run_id"] == 44396812187 else two
                self.assertEqual((out / name).read_bytes(), (selected / name).read_bytes())
                self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(),
                                 entry["raw_sha256"])
            missing = next(x for x in manifest["original_files"] if x["series_id"] == "IORB"
                           and x["as_of"] == "2025-03-31")
            self.assertEqual(missing["source_run_id"], 44397399928)

    def test_drifting_overlap_requires_manual_review(self):
        key = ("IORB", "2026-10-31")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one, two = self.sources(root, drift={key: "2"})
            out = root / "output"
            with self.assertRaisesRegex(ValueError, "drift"):
                reconcile(one, two, out)
            self.assertFalse(out.exists())

    def test_both_sources_missing_must_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one, two = self.sources(root, extra_missing=self.B1)
            out = root / "output"
            with self.assertRaisesRegex(ValueError, "no fabrication"):
                reconcile(one, two, out)
            self.assertFalse(out.exists())

    def test_tampered_file_fails_sha_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one, two = self.sources(root)
            (two / "IORB_asof_2025-03-31.json").write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                reconcile(one, two, root / "out")

    def test_wrong_observation_date_fails_pit_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one, two = self.sources(root)
            filename = "IORB_asof_2025-03-31.json"
            raw = json.loads((two / filename).read_bytes())
            raw["observations"][0]["date"] = "2026-10-31"
            encoded = json.dumps(raw).encode("utf-8")
            (two / filename).write_bytes(encoded)
            manifest = json.loads((two / "manifest.json").read_text())
            for row in manifest["series_results"]:
                if row.get("raw_file") == filename:
                    row["raw_sha256"] = hashlib.sha256(encoded).hexdigest()
            (two / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "look-ahead"):
                reconcile(one, two, root / "out")


if __name__ == "__main__":
    unittest.main()
