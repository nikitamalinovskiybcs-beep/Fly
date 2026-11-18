"""Offline integrity checks for forward Nasdaq captures; fixture prices are NOT market data."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_collect_ai_equities_prices import RESEARCH_SYMBOLS, collect
from scripts.aics_validate_ai_equities_capture import audit_capture

CLOCK = dt.datetime(2026, 11, 19, 12, 0, tzinfo=dt.timezone.utc)
AS_OF = CLOCK.date()
START = dt.date(2026, 11, 16)


def fixture(url):
    symbol = url.split("/quote/")[1].split("/")[0]
    return json.dumps({
        "status": {"rCode": 200},
        "data": {"symbol": symbol, "tradesTable": {"rows": [
            {"date": "11/18/2026", "close": "$12.34", "volume": "1,200"}
        ]}},
    }).encode("utf-8")


def capture(root, *, as_of=AS_OF, symbols=RESEARCH_SYMBOLS, fetcher=fixture):
    return collect(root, as_of=as_of, start=START, symbols=symbols,
                   fetcher=fetcher, clock=lambda: CLOCK)


class TestProspectiveEquitiesRehash(unittest.TestCase):
    def test_all_seven_originals_are_rehashed_but_never_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture(root)
            report = audit_capture(root)
            self.assertEqual(report["local_original_rehashes"], 7)
            self.assertEqual(report["original_candidate_rows"], 7)
            self.assertFalse(report["historical_price_pit_attested"])
            self.assertFalse(report["point_in_time_membership_attested"])
            self.assertFalse(report["corporate_action_adjustment_pit_attested"])
            self.assertIsNone(report["index_aics"])
            self.assertEqual(report["promotion"], "BLOCKED")
            self.assertEqual(len(report["source_receipts"]), 7)

    def test_tampered_original_and_manifest_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = capture(root)
            p = Path(data["sources"][0]["raw_path"])
            p.write_bytes(p.read_bytes() + b" ")
            with self.assertRaises(ValueError):
                audit_capture(root)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture(root)
            p = root / "manifest.json"
            manifest = json.loads(p.read_text())
            manifest["index_aics"] = 500
            p.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                audit_capture(root)

    def test_backdated_capture_does_not_become_historical_vintage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture(root, as_of=dt.date(2026, 11, 18))
            with self.assertRaisesRegex(ValueError, "Backdated"):
                audit_capture(root)

    def test_incomplete_roster_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture(root, symbols=RESEARCH_SYMBOLS[:-1])
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                audit_capture(root)

    def test_wrong_provider_symbol_cannot_be_rehashed_as_another(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def wrong(_url):
                return fixture("https://api.nasdaq.com/api/quote/NVDA/historical")
            capture(root, fetcher=wrong)
            with self.assertRaisesRegex(ValueError, "symbol"):
                audit_capture(root)

    def test_disallows_source_file_outside_capture_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture(root)
            p = root / "manifest.json"
            manifest = json.loads(p.read_text())
            manifest["sources"][0]["raw_path"] = str(root / "elsewhere.json")
            p.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "outside archive"):
                audit_capture(root)


if __name__ == "__main__":
    unittest.main()
