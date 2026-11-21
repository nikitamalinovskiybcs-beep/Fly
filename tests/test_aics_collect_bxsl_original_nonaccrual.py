"""HTML fixtures only test exact source wording; no synthetic historic market series."""
import unittest
from decimal import Decimal

from scripts.aics_collect_bxsl_original_nonaccrual import (
    BXSLError, parse, flatten, permitted,
)


def originals():
    index = ("""<html><body><h1>Filing Detail</h1>Form 8-K - Current report
        SEC Accession No. 0001213900-26-115721 Filing Date 2026-11-04
        BXSL Filer CIK 1736035
        1 ea0310494-8k_blackstone.htm 8-K
        2 ea0310494-01_ex991.htm EX-99.1
        </body></html>""").encode()
    form = ("""<html><body><h1>Form 8-K</h1>
        Blackstone Secured Lending Fund
        On November 4, 2026, Blackstone Secured Lending Fund issued a press
        release with detailed presentation of results for the third quarter
        ended September 30, 2026, furnished as Exhibit 99.1.
        </body></html>""").encode()
    exhibit = ("""<html><body><h1>Blackstone Secured Lending Fund
        Third Quarter 2026 Results</h1>
        <div>HIGHLIGHTS. Portfolio has remained well positioned, with
        2.1% of investments on non - accrual (at fair market value) (1)</div>
        <p>Based on non - accrual debt investments as a percentage of
        the fair market value of total investments.
        Based on amortized cost, investments on non - accrual represent
        2 . 8 % of total investments.</p>
        </body></html>""").encode()
    return index, form, exhibit


class TestBXSLOriginalEvidence(unittest.TestCase):
    def test_exact_two_original_source_percentages(self):
        d = parse(*originals())
        self.assertEqual(d["source_cost_nonaccrual_pct"], "2.8")
        self.assertEqual(d["source_fair_nonaccrual_pct"], "2.1")
        self.assertEqual(d["sec_available_at"], "2026-11-18")
        self.assertEqual(d["original_sec_html_count"], 3)
        self.assertEqual(d["synthetic_financial_observations"], 0)
        self.assertIsNone(d["private_credit_node_score"])
        self.assertIsNone(d["aics_index"])
        self.assertEqual(d["promotion"], "BLOCKED")

    def test_original_source_unequal_denominators_are_not_combined(self):
        d = parse(*originals())
        self.assertNotEqual(d["cost_denominator"], d["fair_denominator"])
        self.assertNotIn("averaged_nonaccrual", d)

    def test_changed_source_percentage_requires_review(self):
        a, b, c = originals()
        with self.assertRaisesRegex(BXSLError, "changed"):
            parse(a, b, c.replace(b"2.1%", b"3.1%"))

    def test_missing_original_footnote_blocks(self):
        a, b, c = originals()
        with self.assertRaisesRegex(BXSLError, "ambiguous"):
            parse(a, b, c.replace(b"Based on amortized cost,", b"According to cost,"))

    def test_missing_original_sec_date_or_cik_blocks(self):
        a, b, c = originals()
        with self.assertRaisesRegex(BXSLError, "SEC accession"):
            parse(a.replace(b"2026-11-04", b"2026-09-30"), b, c)
        with self.assertRaisesRegex(BXSLError, "SEC accession"):
            parse(a.replace(b"1736035", b"1111111"), b, c)

    def test_invalid_original_form_issuer_blocks(self):
        a, b, c = originals()
        with self.assertRaisesRegex(BXSLError, "issuer"):
            parse(a, b.replace(b"Blackstone", b"Elsewhere"), c)

    def test_missing_original_fair_denominator_blocks(self):
        a, b, c = originals()
        with self.assertRaisesRegex(BXSLError, "fair-value denominator"):
            parse(a, b, c.replace(b"fair market value of total investments",
                                   b"fantasy portfolio value"))

    def test_duplicate_fair_percentage_blocks(self):
        a, b, c = originals()
        extra = b" 2.1% of investments on non - accrual (at fair market value) "
        with self.assertRaisesRegex(BXSLError, "ambiguous"):
            parse(a, b, c.replace(b"</body>", extra+b"</body>"))

    def test_unsafe_sec_url_blocked(self):
        self.assertTrue(permitted("https://www.sec.gov/Archives/edgar/data/1736035/000121390026115721/ea0310494-01_ex991.htm"))
        for u in (
            "http://www.sec.gov/Archives/edgar/data/1736035/000121390026115721/ea0310494-01_ex991.htm",
            "https://evil.example/Archives/edgar/data/1736035/000121390026115721/ea0310494-01_ex991.htm",
            "https://www.sec.gov.evil.example/Archives/edgar/data/1736035/000121390026115721/a",
            "https://www.sec.gov:8080/Archives/edgar/data/1736035/000121390026115721/a",
        ):
            self.assertFalse(permitted(u))


if __name__ == "__main__":
    unittest.main()
