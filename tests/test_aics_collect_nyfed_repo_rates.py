"""Offline verifiable NY Fed original-rate capture without manufactured PIT."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError

from scripts.aics_collect_nyfed_repo_rates import (
    ROW_LIMIT, TYPES, SourceValidationError, collect, validate_rows,
)


def payload(rate: str, *, day: str = "2026-11-17") -> bytes:
    return json.dumps({"refRates": [{
        "effectiveDate": day, "type": rate.upper(),
        "percentRate": 3.92, "percentPercentile1": 3.87,
        "percentPercentile25": 3.90, "percentPercentile75": 3.97,
        "percentPercentile99": 3.99, "volumeInBillions": 3173,
        "revisionIndicator": "",
    }]}).encode("utf-8")


class FakeResponse:
    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return self.raw


class TestNyFedRates(unittest.TestCase):
    DAY = dt.date(2026, 11, 18)
    TIME = dt.datetime(2026, 11, 18, 20, 0, tzinfo=dt.timezone.utc)

    def test_real_endpoint_schema_and_sha(self):
        raw = payload("sofr")
        result = validate_rows(raw, "sofr", self.DAY)
        self.assertEqual(result["rate_type"], "SOFR")
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["raw_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertTrue(result["source_url"].endswith("/sofr/last/999.json"))
        self.assertFalse(result["independently_attested_historical_pit"])

    def test_future_effective_date_blocked(self):
        with self.assertRaises(SourceValidationError):
            validate_rows(payload("sofr", day="2026-11-19"), "sofr", self.DAY)

    def test_wrong_rate_type_blocked(self):
        with self.assertRaises(SourceValidationError):
            validate_rows(payload("bgcr"), "sofr", self.DAY)

    def test_duplicate_effective_date_blocked(self):
        x = json.loads(payload("sofr"))
        x["refRates"].append(x["refRates"][0])
        with self.assertRaises(SourceValidationError):
            validate_rows(json.dumps(x).encode(), "sofr", self.DAY)

    def test_non_descending_history_blocked(self):
        x = json.loads(payload("sofr"))
        x["refRates"].append({**x["refRates"][0], "effectiveDate": "2026-11-18"})
        with self.assertRaises(SourceValidationError):
            validate_rows(json.dumps(x).encode(), "sofr", self.DAY)

    def test_invalid_nan_and_bool_blocked(self):
        for bad in (True, float("nan"), "3.92"):
            with self.subTest(bad=str(bad)):
                x = json.loads(payload("sofr"))
                x["refRates"][0]["percentRate"] = bad
                with self.assertRaises(SourceValidationError):
                    validate_rows(json.dumps(x).encode(), "sofr", self.DAY)

    def test_missing_schema_blocked(self):
        for raw in (b'{}', b'{"refRates":null}', b'{"refRates":[]}', b'invalid'):
            with self.subTest(raw=raw):
                with self.assertRaises(SourceValidationError):
                    validate_rows(raw, "sofr", self.DAY)

    def test_three_sources_archived_exactly_and_no_scores(self):
        called = []
        def transport(request, timeout):
            called.append((request.full_url, timeout))
            rate = request.full_url.split("/secured/")[1].split("/")[0]
            return FakeResponse(payload(rate))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            data = collect(path, fetched_at=self.TIME, transport=transport)
            self.assertEqual(len(called), 3)
            self.assertEqual(len(data["series"]), 3)
            self.assertEqual([x["rate_type"] for x in data["series"]],
                             [x.upper() for x in TYPES])
            self.assertEqual(
                json.loads((path / "manifest.json").read_text(encoding="utf-8")),
                data,
            )
            for rate in TYPES:
                source = path / f"nyfed_{rate}_last_{ROW_LIMIT}_as_captured.json"
                self.assertEqual(source.read_bytes(), payload(rate))
            self.assertIsNone(data["index_aics"])
            self.assertIsNone(data["node_stress_score"])
            self.assertIsNone(data["rate_spread_to_iorb_bps"])
            self.assertFalse(data["historical_pit_attested"])
            self.assertFalse(data["raw_provider_publication_vintage"])
            self.assertEqual(data["promotion"], "BLOCKED")

    def test_failed_one_source_persists_nothing(self):
        def transport(request, timeout):
            rate = request.full_url.split("/secured/")[1].split("/")[0]
            if rate == "bgcr":
                raise URLError("Provider unavailable")
            return FakeResponse(payload(rate))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "archive"
            with self.assertRaises(URLError):
                collect(out, fetched_at=self.TIME, transport=transport)
            self.assertFalse(out.exists())

    def test_aware_datetime_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                collect(Path(tmp), fetched_at=dt.datetime(2026, 11, 18))


if __name__ == "__main__":
    unittest.main()
