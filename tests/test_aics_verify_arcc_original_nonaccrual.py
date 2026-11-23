"""Purely artificial HTML fixtures and fail-closed ARCC original source checks."""
import tempfile
import unittest
from pathlib import Path

from scripts.aics_verify_arcc_original_nonaccrual import (
    OriginalEvidenceError, parse_reported_nonaccrual, verify,
)


def exhibit(
    period="March 31, 2026",
    filing="April 28, 2026",
    now_cost="2.1", now_fair="1.2", old_cost="1.8", old_fair="1.2"
):
    return (f"<html><body>As of {period} and December 31, 2025, "
            "the weighted average grade of the portfolio at fair value was 3.1 and 3.1, "
            f"respectively, and loans on non-accrual status represented {now_cost}% "
            f"of the total investments at amortized cost (or {now_fair}% at fair value) "
            f"and {old_cost}% at amortized cost (or {old_fair}% at fair value), respectively. "
            "For more information, see the Quarterly Report on Form 10-Q "
            "filed with the Securities and Exchange Commission (SEC) on "
            f"{filing}.</body></html>").encode()


class TestOriginalARCCVerification(unittest.TestCase):
    def test_exact_denominators_and_two_reference_periods(self):
        result = parse_reported_nonaccrual(exhibit(), "2026-03-31")
        self.assertEqual(result["current_cost_pct"], "2.1")
        self.assertEqual(result["current_fair_value_pct"], "1.2")
        self.assertEqual(result["dec_2025_cost_pct"], "1.8")
        self.assertEqual(result["dec_2025_fair_value_pct"], "1.2")

    def test_missing_period_or_original_sec_date_fails(self):
        with self.assertRaises(OriginalEvidenceError):
            parse_reported_nonaccrual(exhibit(), "2026-06-30")
        with self.assertRaises(OriginalEvidenceError):
            parse_reported_nonaccrual(exhibit(filing="May 8, 2026"), "2026-03-31")

    def test_duplicate_paragraph_ambiguous_fails(self):
        body = exhibit()
        with self.assertRaises(OriginalEvidenceError):
            parse_reported_nonaccrual(
                body.replace(b"</body>", body[12:-14] + b"</body>"),
                "2026-03-31",
            )

    def test_future_issuer_month_not_accepted(self):
        with self.assertRaises(OriginalEvidenceError):
            parse_reported_nonaccrual(exhibit(period="June 30, 2026"), "2026-03-31")

    def test_original_bytes_zip_digest_always_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "shell.zip"
            f.write_bytes(b"not a trusted archive")
            with self.assertRaisesRegex(OriginalEvidenceError, "SHA mismatch"):
                verify(f)


if __name__ == "__main__":
    unittest.main()
