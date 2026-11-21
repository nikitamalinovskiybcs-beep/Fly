"""Offline fixtures for authentic ARCC 2025Q4 original SEC exhibit.

No invented market data enter stored AICS research archives. Test values
are asserted against the original expected SEC release, not generated rows.
"""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_collect_arcc_q4_sec_original import (
    EXHIBIT_URL, INDEX_URL, SECOriginalError, AVAILABLE_AT,
    collect, fetch, verify_original,
)

INDEX = b"""<!doctype html><html><body>
ARES CAPITAL CORP
SEC Accession Number 0001287750-26-000004
Filing Date 2026-02-04
EX-99.1 arccq4-2025exhibit991.htm
</body></html>"""
EXHIBIT = b"""<!doctype html><html><body>
ARES CAPITAL CORP February 4, 2026
As of December 31, 2025 and 2024, respectively, loans on non-accrual status represented
1.8% of the total investments at amortized cost (or 1.2% at fair value)
and 1.7% at amortized cost (or 1.0% at fair value), respectively.
</body></html>"""


class FakeReply:
    def __init__(self, url, body, mime="text/html", redirect=None):
        self.body = body
        self.url = redirect or url
        self.headers = {"Content-Type": mime}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self.url

    def read(self, n):
        return self.body[:n]


def fake_transport(req, timeout):
    assert timeout == 40
    return FakeReply(req.full_url, INDEX if req.full_url == INDEX_URL else EXHIBIT)


class TestARCCQ4OriginalSEC(unittest.TestCase):
    def test_verified_sec_original_and_february_14d_gate(self):
        r = verify_original(INDEX, EXHIBIT)
        self.assertEqual(r["filing_date"], "2026-02-04")
        self.assertEqual(r["available_at"], "2026-02-18")
        self.assertEqual(r["nonaccrual_amortized_cost_pct"], "1.8")
        self.assertEqual(r["nonaccrual_fair_value_pct"], "1.2")
        self.assertEqual(r["prior_dec2024_cost_pct"], "1.7")
        self.assertEqual(r["prior_dec2024_fair_value_pct"], "1.0")
        self.assertEqual(r["raw_index_sha256"], hashlib.sha256(INDEX).hexdigest())
        self.assertEqual(r["raw_exhibit_sha256"], hashlib.sha256(EXHIBIT).hexdigest())
        self.assertTrue(r["source_values_verified_against_original_sec"])
        self.assertTrue(r["filed_at_plus_14_date_gate_passed"])
        self.assertFalse(r["independently_attested_contemporaneous_publication"])
        self.assertIsNone(r["index_aics"])
        self.assertIsNone(r["private_credit_node_score"])
        self.assertEqual(r["promotion"], "BLOCKED")
        self.assertEqual(AVAILABLE_AT, dt.date(2026, 2, 18))

    def test_index_date_tamper_fails(self):
        with self.assertRaises(SECOriginalError):
            verify_original(INDEX.replace(b"2026-02-04", b"2026-02-05"), EXHIBIT)

    def test_falsified_issuer_identity_fails(self):
        with self.assertRaises(SECOriginalError):
            verify_original(INDEX.replace(b"ARES CAPITAL CORP", b"WRONG ENTITY"), EXHIBIT)

    def test_misidentified_exhibit_fails(self):
        with self.assertRaises(SECOriginalError):
            verify_original(INDEX.replace(b"EX-99.1", b"EX-99.3"), EXHIBIT)

    def test_changed_nonaccrual_value_fails(self):
        for old, new in ((b"1.8%", b"9.8%"), (b"1.2%", b"9.2%"),
                         (b"1.7%", b"9.7%"), (b"1.0%", b"9.0%")):
            with self.subTest(value=old):
                with self.assertRaises(SECOriginalError):
                    verify_original(INDEX, EXHIBIT.replace(old, new))

    def test_missing_original_release_date_fails(self):
        with self.assertRaises(SECOriginalError):
            verify_original(INDEX, EXHIBIT.replace(b"February 4, 2026", b"February 5, 2026"))

    def test_fetch_url_allowlist_requires_sec_contact(self):
        with self.assertRaises(SECOriginalError):
            fetch("https://attacker.invalid/not-sec", "Research data@example.org", fake_transport)
        with self.assertRaises(SECOriginalError):
            fetch(EXHIBIT_URL, "fake bot", fake_transport)

    def test_malicious_redirect_fails(self):
        def redirect(req, timeout):
            return FakeReply(req.full_url, EXHIBIT, redirect="https://attacker.invalid/")
        with self.assertRaises(SECOriginalError):
            fetch(EXHIBIT_URL, "Research data@example.org", redirect)

    def test_exact_two_original_html_files_only_and_no_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = collect(Path(tmp), "Research data@example.org", transport=fake_transport)
            self.assertEqual((Path(tmp)/"sec_q4_index_original.html").read_bytes(), INDEX)
            self.assertEqual((Path(tmp)/"sec_q4_exhibit99_1_original.html").read_bytes(), EXHIBIT)
            self.assertEqual(json.loads((Path(tmp)/"manifest.json").read_text()), result)
            self.assertIsNone(result["index_aics"])
            self.assertEqual(result["promotion"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
