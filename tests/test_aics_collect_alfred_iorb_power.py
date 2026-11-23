"""Offline anti-look-ahead tests for new IORB/electricity ALFRED coverage."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path

from scripts.aics_collect_alfred_iorb_power import (
    FREEZE_AS_OF, SERIES, VintageValidationError, collect,
    month_ends, validate_vintage,
)


def raw_asof(as_of: dt.date, *, value="3.5") -> bytes:
    data = {"realtime_start": as_of.isoformat(),
            "realtime_end": as_of.isoformat(),
            "count": 1,
            "observations": [{
                "realtime_start": as_of.isoformat(),
                "realtime_end": as_of.isoformat(),
                "date": "2018-01-01", "value": value,
            }]}
    return json.dumps(data).encode("utf-8")


class FakeResponse:
    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _max):
        return self.raw


class TestAlfredFreeGapVintage(unittest.TestCase):
    DAY = dt.date(2026, 10, 31)
    CAPTURED_AT = dt.datetime(2026, 11, 18, 21, 0, tzinfo=dt.timezone.utc)

    def test_correct_month_end_schedule_and_no_future(self):
        days = month_ends()
        self.assertEqual(len(days), 24)
        self.assertEqual(days[0].isoformat(), "2024-11-30")
        self.assertEqual(days[-1].isoformat(), "2026-10-31")
        self.assertTrue(all(day < FREEZE_AS_OF for day in days))

    def test_raw_sha_date_and_nopromotion(self):
        raw = raw_asof(self.DAY)
        info = validate_vintage(raw, "IORB", self.DAY)
        self.assertEqual(info["raw_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(info["rows"], 1)
        self.assertEqual(info["as_of"], "2026-10-31")
        self.assertFalse(info["independent_provider_release_pit_attested"])
        self.assertFalse(info["stress_score_eligible"])

    def test_future_observation_date_blocked(self):
        x = json.loads(raw_asof(self.DAY))
        x["observations"][0]["date"] = "2026-11-01"
        with self.assertRaises(VintageValidationError):
            validate_vintage(json.dumps(x).encode(), "IORB", self.DAY)

    def test_future_vintage_start_blocked(self):
        x = json.loads(raw_asof(self.DAY))
        x["observations"][0]["realtime_start"] = "2026-11-01"
        with self.assertRaises(VintageValidationError):
            validate_vintage(json.dumps(x).encode(), "IORB", self.DAY)

    def test_asof_top_level_mismatch_blocked(self):
        x = json.loads(raw_asof(self.DAY))
        x["realtime_end"] = "2026-11-01"
        with self.assertRaises(VintageValidationError):
            validate_vintage(json.dumps(x).encode(), "IORB", self.DAY)

    def test_missing_rows_and_missing_page_blocked(self):
        for raw in (b'{}', b'{"observations":[]}', b'not-json'):
            with self.assertRaises(VintageValidationError):
                validate_vintage(raw, "WPU0543", self.DAY)
        x = json.loads(raw_asof(self.DAY))
        x["count"] = 2
        with self.assertRaises(VintageValidationError):
            validate_vintage(json.dumps(x).encode(), "IORB", self.DAY)

    def test_cannot_mint_future_or_duplicate_snapshot_schedule(self):
        future = (dt.date(2026, 11, 30),)
        with self.assertRaises(ValueError):
            collect("test-key", snapshots=future)
        with self.assertRaises(ValueError):
            collect("test-key", snapshots=(self.DAY, self.DAY))

    def test_absent_key_blocked_without_request(self):
        with self.assertRaises(ValueError):
            collect("", snapshots=(self.DAY,))

    def test_exact_4_original_vintages_for_two_sources(self):
        dates = (dt.date(2026, 9, 30), self.DAY)
        urls = []
        def transport(request, timeout):
            urls.append(request.full_url)
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
            day = dt.date.fromisoformat(query["realtime_start"][0])
            assert query["realtime_end"][0] == day.isoformat()
            assert query["observation_start"][0] == "2018-01-01"
            assert query["observation_end"][0] == day.isoformat()
            assert timeout == 40
            return FakeResponse(raw_asof(day))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            result = collect(
                "test-api-key", dest=path, snapshots=dates, transport=transport,
                captured_at=self.CAPTURED_AT, pace_seconds=0,
            )
            self.assertEqual(result["successful_snapshots"], 4)
            self.assertEqual(result["expected_snapshots"], 4)
            self.assertTrue(result["all_sources_downloaded"])
            self.assertEqual(len(urls), 4)
            self.assertEqual(
                json.loads((path / "manifest.json").read_text()), result
            )
            self.assertIsNone(result["aics_index"])
            self.assertEqual(result["promotion"], "BLOCKED")
            self.assertFalse(result["provider_publication_lag_pit_attested"])
            self.assertNotIn("test-api-key", json.dumps(result))
            self.assertEqual(sorted({r["series_id"] for r in result["series_results"]}),
                             sorted(SERIES))
            for entry in result["series_results"]:
                self.assertEqual(
                    hashlib.sha256((path / entry["raw_file"]).read_bytes()).hexdigest(),
                    entry["raw_sha256"]
                )

    def test_transient_502_retried_and_exact_provider_bytes_kept(self):
        attempts = []
        def transport(request, timeout):
            attempts.append(request.full_url)
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
            if query["series_id"][0] == "IORB" and len(attempts) == 1:
                raise urllib.error.HTTPError(request.full_url, 502, "temporary", None, None)
            return FakeResponse(raw_asof(self.DAY))
        with tempfile.TemporaryDirectory() as tmp:
            report = collect(
                "test-api-key", dest=Path(tmp), snapshots=(self.DAY,),
                transport=transport, captured_at=self.CAPTURED_AT, pace_seconds=0
            )
            self.assertEqual(report["successful_snapshots"], 2)
            self.assertEqual(len(attempts), 3)
            self.assertFalse(report["blocked"])
            self.assertEqual((Path(tmp) / "IORB_asof_2026-10-31.json").read_bytes(),
                             raw_asof(self.DAY))
            self.assertNotIn("test-api-key", json.dumps(report))

    def test_provider_failure_is_explicit_and_no_fabricated_snapshot(self):
        def transport(request, timeout):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
            if query["series_id"][0] == "WPU0543":
                raise urllib.error.HTTPError(request.full_url, 429, "limit", None, None)
            return FakeResponse(raw_asof(self.DAY))
        with tempfile.TemporaryDirectory() as tmp:
            result = collect(
                "test-api-key", dest=Path(tmp), snapshots=(self.DAY,),
                transport=transport, captured_at=self.CAPTURED_AT, pace_seconds=0
            )
            self.assertEqual(result["successful_snapshots"], 1)
            self.assertEqual(result["expected_snapshots"], 2)
            self.assertFalse(result["all_sources_downloaded"])
            self.assertEqual(len(result["blocked"]), 1)
            self.assertEqual(result["blocked"][0]["status"], "HTTP_429")
            self.assertEqual(result["promotion"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
