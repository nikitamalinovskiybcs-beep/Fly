"""Synthetic HTML fixtures ONLY test parsing, not historical market observations."""
import datetime as dt
import unittest

from scripts.aics_collect_obdc_original_nonaccrual import (
    BASE, SOURCES, OriginalSourceError, build, validate_pair,
)


def fixture(index=0):
    period, filed, path, acc, doc, month, day = SOURCES[index]
    cost, fair = [("2.0", "1.0"), ("2.8", "0.8"), ("2.9", "0.8")][index]
    original_index = (
        f"<html><body>Filing Detail Form 8-K - Current report "
        f"SEC Accession No. {acc} Filing Date {filed} Accepted "
        f"Blue Owl Capital Corp Filer CIK 0001655888 Document EX-99.1 {doc}"
        f"</body></html>"
    ).encode()
    original_exhibit = (
        f"<html><body>Blue Owl Capital Corporation Announces {month} {day}, 2026 "
        f"Financial Results. Investments on non-accrual represented {cost}% "
        f"and {fair}% of the portfolio at cost and fair value, respectively, "
        f"as compared to the prior period.</body></html>"
    ).encode()
    return original_index, original_exhibit


def complete():
    source = {}
    for index, (_, _, path, accession, document, _, _) in enumerate(SOURCES):
        index_url = f"{BASE}{path}/{accession}-index.htm"
        exhibit_url = f"{BASE}{path}/{document}"
        a, b = fixture(index)
        source[index_url] = (a, b"")
        source[exhibit_url] = (b, b"")
    return source


class TestOBDCOriginalResearch(unittest.TestCase):
    def test_three_issuer_quarters_are_separate_and_no_score(self):
        report = build(complete(), dt.date(2026, 11, 19))
        self.assertEqual(report["original_sec_html_files_sha256_verified"], 6)
        self.assertEqual(report["visible_numeric_values"], 6)
        self.assertEqual([r["nonaccrual_amortized_cost_percent"]
                          for r in report["visible_periods_after_sec_14_days"]],
                         ["2.0", "2.8", "2.9"])
        self.assertEqual([r["nonaccrual_fair_value_percent"]
                          for r in report["visible_periods_after_sec_14_days"]],
                         ["1.0", "0.8", "0.8"])
        self.assertEqual(report["synthetic_financial_observations"], 0)
        self.assertEqual(report["private_credit_stress_score"], None)
        self.assertEqual(report["index_aics"], None)
        self.assertEqual(report["promotion"], "BLOCKED")

    def test_filing_plus_fourteen_calendar_days(self):
        for cutoff, count in [
            ("2026-05-19", 0), ("2026-05-20", 2),
            ("2026-08-18", 2), ("2026-08-19", 4),
            ("2026-11-17", 4), ("2026-11-18", 6),
        ]:
            with self.subTest(as_of=cutoff):
                report = build(complete(), dt.date.fromisoformat(cutoff))
                self.assertEqual(report["visible_numeric_values"], count)

    def test_change_in_source_figures_blocks_publication(self):
        a, b = fixture(2)
        with self.assertRaisesRegex(OriginalSourceError, "changed original source"):
            validate_pair(a, b.replace(b"2.9%", b"6.9%"), SOURCES[2])

    def test_sec_filing_date_tampering_cannot_backdate_q3(self):
        a, b = fixture(2)
        with self.assertRaisesRegex(OriginalSourceError, "original SEC accession"):
            validate_pair(a.replace(b"2026-11-04", b"2026-09-30"), b, SOURCES[2])

    def test_wrong_issuer_or_quarter_blocks(self):
        a, b = fixture(0)
        with self.assertRaisesRegex(OriginalSourceError, "wrong issuer"):
            validate_pair(a, b.replace(b"Blue Owl", b"Blue Whale"), SOURCES[0])
        with self.assertRaisesRegex(OriginalSourceError, "wrong issuer"):
            validate_pair(a, b.replace(b"March 31", b"April 30"), SOURCES[0])

    def test_ambiguous_duplicate_paragraph_blocks(self):
        a, b = fixture(0)
        extra = (b" Investments on non-accrual represented 2.0% and 1.0%"
                 b" of the portfolio at cost and fair value, respectively.")
        with self.assertRaisesRegex(OriginalSourceError, "ambiguous"):
            validate_pair(a, b.replace(b"</body>", extra + b"</body>"), SOURCES[0])

    def test_missing_official_document_blocks_entire_batch(self):
        items = complete()
        items.pop(next(k for k in items if "000165588826000070" in k and "index" in k))
        with self.assertRaisesRegex(OriginalSourceError, "absent"):
            build(items, dt.date(2026, 11, 19))

    def test_cik_and_accession_required(self):
        a, b = fixture(0)
        with self.assertRaisesRegex(OriginalSourceError, "original SEC accession"):
            validate_pair(a.replace(b"0001655888", b"0001736035"), b, SOURCES[0])

    def test_frozen_original_filing_dates(self):
        self.assertEqual([x[1] for x in SOURCES],
                         ["2026-05-06", "2026-08-05", "2026-11-04"])
        for item in SOURCES:
            self.assertLess(dt.date.fromisoformat(item[0]), dt.date.fromisoformat(item[1]))


if __name__ == "__main__":
    unittest.main()
