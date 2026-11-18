"""Offline fail-closed tests: no fabricated prices or certified equity scores."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_collect_ai_equities_prices import (
    RESEARCH_SYMBOLS, collect, quote_url, validate_price_response
)

ASOF = dt.date(2026, 11, 18)
START = dt.date(2026, 11, 1)
CLOCK = dt.datetime(2026, 11, 18, 21, 0, tzinfo=dt.timezone.utc)

# Explicit parser fixtures, NOT historical observations or AICS market inputs.
MOCK = {
    "status": {"rCode": 200},
    "data": {"tradesTable": {"rows": [
        {"date": "11/16/2026", "close": "$12.34", "volume": "1,200"},
        {"date": "11/17/2026", "close": "$12.21", "volume": "900"},
    ]}},
}


def bytes_for(value):
    return json.dumps(value).encode("utf-8")


class TestEquityPriceArchive(unittest.TestCase):
    def test_seven_fixed_research_candidates(self):
        self.assertEqual(RESEARCH_SYMBOLS,
                         ("NVDA", "MSFT", "GOOGL", "AMZN", "META", "ORCL", "MU"))
        self.assertIn("api.nasdaq.com/api/quote/NVDA/historical?",
                      quote_url("NVDA", START, ASOF))
        with self.assertRaises(ValueError):
            quote_url("BAD", START, ASOF)

    def test_raw_candidate_hashing_never_promotes_model(self):
        body = bytes_for(MOCK)
        with tempfile.TemporaryDirectory() as temp:
            doc = collect(Path(temp), as_of=ASOF, start=START,
                          symbols=("NVDA",), fetcher=lambda _: body,
                          clock=lambda: CLOCK)
            self.assertEqual(doc["archive_candidates"], 1)
            self.assertEqual(doc["attempted"], 1)
            self.assertEqual(doc["promotion"], "BLOCKED")
            self.assertIsNone(doc["node_stress_score"])
            self.assertIsNone(doc["index_aics"])
            self.assertFalse(doc["independently_verified_pit"])
            self.assertFalse(doc["historical_membership_attested"])
            self.assertFalse(doc["price_adjustments_as_of_historical_date_attested"])
            row = doc["sources"][0]
            self.assertEqual(row["sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual(Path(row["raw_path"]).read_bytes(), body)
            self.assertFalse(row["score_eligible"])
            self.assertNotIn("stress_score", row)

    def test_nasdaq_current_history_cannot_be_backdated(self):
        body = bytes_for(MOCK)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                collect(Path(temp), as_of=dt.date(2026, 11, 19),
                        fetcher=lambda _: body, clock=lambda: CLOCK)

    def test_missing_sources_are_blocked_not_filled(self):
        with tempfile.TemporaryDirectory() as temp:
            doc = collect(Path(temp), as_of=ASOF, start=START,
                          symbols=("NVDA", "MSFT"),
                          fetcher=lambda _: b'{"data":null}',
                          clock=lambda: CLOCK)
            self.assertEqual(doc["archive_candidates"], 0)
            self.assertTrue(all(x["status"] == "blocked" for x in doc["sources"]))
            self.assertIsNone(doc["index_aics"])

    def test_reject_untrusted_numeric_and_duplicate_dates(self):
        for close in (None, "nan", "Infinity", "-1", "0", "oops", True):
            corrupt = json.loads(json.dumps(MOCK))
            corrupt["data"]["tradesTable"]["rows"][0]["close"] = close
            with self.subTest(close=close), self.assertRaises(ValueError):
                validate_price_response(bytes_for(corrupt), START, ASOF)
        dup = json.loads(json.dumps(MOCK))
        dup["data"]["tradesTable"]["rows"][1]["date"] = "11/16/2026"
        with self.assertRaises(ValueError):
            validate_price_response(bytes_for(dup), START, ASOF)

    def test_future_or_out_of_window_rows_never_enter_archive(self):
        for date in ("11/19/2026", "10/31/2026"):
            corrupt = json.loads(json.dumps(MOCK))
            corrupt["data"]["tradesTable"]["rows"][0]["date"] = date
            with self.subTest(date=date), self.assertRaises(ValueError):
                validate_price_response(bytes_for(corrupt), START, ASOF)

    def test_reject_untrusted_symbol_list(self):
        with tempfile.TemporaryDirectory() as temp:
            for symbols in (("NVDA", "NVDA"), ("NVDA", "FAKE"), ()):
                with self.subTest(symbols=symbols), self.assertRaises(ValueError):
                    collect(Path(temp), as_of=ASOF, start=START,
                            symbols=symbols, clock=lambda: CLOCK)

    def test_fail_closed_if_archived_source_is_modified(self):
        body = bytes_for(MOCK)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            first = collect(out, as_of=ASOF, start=START,
                            symbols=("NVDA",), fetcher=lambda _: body,
                            clock=lambda: CLOCK)
            Path(first["sources"][0]["raw_path"]).write_bytes(b"tampered")
            again = collect(out, as_of=ASOF, start=START,
                            symbols=("NVDA",), fetcher=lambda _: body,
                            clock=lambda: CLOCK)
            self.assertEqual(again["archive_candidates"], 0)
            self.assertEqual(again["sources"][0]["status"], "blocked")
            self.assertIsNone(again["index_aics"])


if __name__ == "__main__":
    unittest.main()
