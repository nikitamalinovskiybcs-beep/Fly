"""Artificial HTML fixtures only. Do not use these test values as historical data."""
import datetime as dt
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.aics_collect_bxsl_q1_q2_sec_nonaccrual import (
    SOURCE, Q1Q2EvidenceError, collect, parse, permitted,
)


def fixture(period: str):
    meta = SOURCE[period]
    index = f"""<html><body>Filing Detail Form 8-K - Current report
      SEC Accession No. {meta['accession']} Filing Date {meta['filed_at']}
      Blackstone Secured Lending Fund Filer 1736035
      2 EXHIBIT 99.1 {meta['files']['exhibit']}</body></html>""".encode()
    filing = f"""<html><body>Form 8-K Blackstone Secured Lending Fund
      On {meta['press_date']} Blackstone Secured Lending Fund issued a press
      release reporting results for 2026, furnished as Exhibit 99.1.</body></html>""".encode()
    exhibit = f"""<html><body><h1>Blackstone Secured Lending Fund
      {meta['quarter']} Quarter 2026 Results</h1><p>HIGHLIGHTS: {meta['fair']}%
      of investments on non - accrual (at fair market value).
      Based on non - accrual debt investments as a percentage the fair
      market value of total investments. Based on amortized cost,
      investments on non - accrual represent {meta['cost']}% of total
      investments.</p></body></html>""".encode()
    # Original SEC pages are larger than 250 bytes; pad fixtures only.
    return {"index": index + b" " * 300, "filing": filing + b" " * 300,
            "exhibit": exhibit + b" " * 300}


class TestBXSLQ1Q2OriginalSEC(unittest.TestCase):
    def test_both_quarters_source_percentage_and_embargo(self):
        for period in SOURCE:
            with self.subTest(period=period):
                data = parse(period, fixture(period))
                self.assertEqual(data["nonaccrual_amortized_cost_pct"], SOURCE[period]["cost"])
                self.assertEqual(data["nonaccrual_fair_value_pct"], SOURCE[period]["fair"])
                self.assertEqual(data["candidate_available_at"], SOURCE[period]["available_at"])
                self.assertNotEqual(data["cost_denominator"], data["fair_denominator"])
                self.assertFalse(data["historical_release_feed_pit_attested"])
                self.assertFalse(data["source_to_score_eligible"])

    def test_rejects_incorrect_source_numeric_value(self):
        original = fixture("2026-03-31")
        original["exhibit"] = original["exhibit"].replace(b"4.7%", b"5.7%")
        with self.assertRaisesRegex(Q1Q2EvidenceError, "changed"):
            parse("2026-03-31", original)

    def test_rejects_incorrect_sec_filing_date(self):
        original = fixture("2026-06-30")
        original["index"] = original["index"].replace(b"2026-08-06", b"2026-08-05")
        with self.assertRaisesRegex(Q1Q2EvidenceError, "index"):
            parse("2026-06-30", original)

    def test_rejects_fair_denominator_not_proven(self):
        original = fixture("2026-03-31")
        original["exhibit"] = original["exhibit"].replace(
            b"fair\n      market value of total investments", b"guessed valuation"
        )
        with self.assertRaisesRegex(Q1Q2EvidenceError, "denominator"):
            parse("2026-03-31", original)

    def test_rejects_duplicate_inconsistent_cost_note(self):
        original = fixture("2026-06-30")
        original["exhibit"] += (b" Based on amortized cost, investments on"
                                b" non - accrual represent 9.0% of total investments.")
        with self.assertRaisesRegex(Q1Q2EvidenceError, "ambiguous"):
            parse("2026-06-30", original)

    def test_only_predeclared_original_sec_files_permitted(self):
        for meta in SOURCE.values():
            for filename in meta["files"].values():
                self.assertTrue(permitted(meta["base"] + filename))
        for url in (
            "http://www.sec.gov/Archives/",
            "https://www.sec.gov.evil.example/a",
            "https://www.sec.gov/Archives/edgar/data/1736035/000121390026115721/ea0310494-01_ex991.htm",
            "https://www.sec.gov/Archives/edgar/data/1736035/000121390026053022/other.htm",
            "https://user@www.sec.gov/Archives/edgar/data/1736035/000121390026053022/ea0289403-01_ex991.htm",
        ):
            self.assertFalse(permitted(url))

    def test_no_output_created_if_one_original_fails(self):
        import unittest.mock
        with tempfile.TemporaryDirectory() as tmp:
            def fake_fetch(url, agent):
                for period, meta in SOURCE.items():
                    for kind, filename in meta["files"].items():
                        if url == meta["base"] + filename:
                            if kind == "exhibit" and period == "2026-06-30":
                                return b"not a source"
                            return fixture(period)[kind]
                raise ValueError("fixture URL missing")
            with unittest.mock.patch(
                "scripts.aics_collect_bxsl_q1_q2_sec_nonaccrual.fetch", fake_fetch
            ):
                with self.assertRaises(ValueError):
                    collect(Path(tmp) / "out", "real-authorized-contact@example.org", dt.date(2026, 11, 19))
            self.assertFalse((Path(tmp) / "out").exists())

    def test_future_frozen_date_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Q1Q2EvidenceError):
                collect(Path(tmp) / "out", "user@example.com", dt.date(2026, 11, 20))


if __name__ == "__main__":
    unittest.main()
