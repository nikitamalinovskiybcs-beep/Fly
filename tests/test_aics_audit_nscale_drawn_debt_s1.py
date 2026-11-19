"""Parser-only fixtures with invented test strings, NOT financial observations."""
import unittest

from scripts.aics_audit_nscale_drawn_debt_s1 import (
    GPU_START, GPU_CURRENT_DISCLOSURE, MACQUARIE_START,
    MACQUARIE_LIMIT_DISCLOSURE, MACQUARIE_FIRST_DRAW,
    MACQUARIE_SECOND_DRAW, GROUP_CARRYING_DISCLOSURE,
    parse_reporting_facts,
)
from scripts.aics_collect_nscale_ward_sec import SourceError


def sample(*, gpu=GPU_CURRENT_DISCLOSURE, first=MACQUARIE_FIRST_DRAW,
           second=MACQUARIE_SECOND_DRAW, carry=GROUP_CARRYING_DISCLOSURE):
    return ("<!doctype html><html><body>" +
            "Synthetic parser test, not real market history. " +
            carry + " " + GPU_START +
            " (the Initial Borrower) entered into a secured credit agreement. " +
            gpu + " for eligible GPU clusters. " + MACQUARIE_START +
            ", " + MACQUARIE_LIMIT_DISCLOSURE +
            " for a data center in Glomfjord, Norway. " +
            first + " " + second + " </body></html>").encode()


class TestNscaleS1HistoricalDrawnFacts(unittest.TestCase):
    def test_three_distinct_financial_facts_reproduced_not_aggregated(self):
        out = parse_reporting_facts(sample())
        gpu = out["gpu_financing_facility"]
        mac = out["macquarie_senior_facility"]
        group = out["consolidated_nscale_debt"]
        self.assertEqual(gpu["borrower"], "Nscale Services UK Ltd")
        self.assertEqual(gpu["observation_as_of"], "2026-03-31")
        self.assertEqual(gpu["drawn_and_outstanding_term_loans_usd_approx"], 58_900_000)
        self.assertEqual(mac["borrower"], "Nscale Global Holdings Limited")
        self.assertEqual(mac["first_utilization"]["date"], "2025-08-01")
        self.assertEqual(mac["first_utilization"]["usd"], 70_100_000)
        self.assertEqual(mac["second_utilization"]["date"], "2026-01-30")
        self.assertEqual(mac["second_utilization"]["usd"], 34_900_000)
        self.assertEqual(mac["historical_utilizations_sum_usd"],105_000_000)
        self.assertEqual(group["observation_as_of"], "2026-06-30")
        self.assertEqual(group["gaap_total_debt_carrying_value_usd"], 137_400_000)
        self.assertIsNone(gpu["outstanding_on_review_date_usd"])
        self.assertIsNone(mac["outstanding_on_review_date_usd"])
        self.assertIsNone(group["current_2026_11_balance_usd"])

    def test_forged_gpu_drawn_number_or_lending_identity_fail_closed(self):
        for wrong in ("$59.9 million", "$1.5 billion", "have been promised"):
            with self.subTest(value=wrong):
                altered = GPU_CURRENT_DISCLOSURE
                altered = altered.replace("$58.9 million", wrong) if wrong.startswith("$59") else (
                    altered.replace("$1.4 billion", wrong) if wrong.startswith("$1.5")
                    else altered.replace("have been drawn and are outstanding",wrong)
                )
                with self.assertRaisesRegex(SourceError,"GPU initial-borrower"):
                    parse_reporting_facts(sample(gpu=altered))

    def test_macquarie_draw_dates_and_amounts_fail_closed(self):
        for original,replacement in (
            ("$70.1 million","$71.1 million"),
            ("August 1, 2025","September 1, 2025"),
            ("$34.9 million","$35.9 million"),
            ("January 30, 2026","January 29, 2026"),
        ):
            with self.subTest(field=original):
                bad = sample().replace(original.encode(),replacement.encode())
                with self.assertRaisesRegex(SourceError,"Macquarie original"):
                    parse_reporting_facts(bad)

    def test_consolidated_carrying_value_not_conflated_with_utilization(self):
        with self.assertRaisesRegex(SourceError,"Consolidated debt"):
            parse_reporting_facts(sample(carry=GROUP_CARRYING_DISCLOSURE.replace(
                "$137.4 million","$163.9 million")))

    def test_duplicate_borrower_or_borrower_swap_fails_closed(self):
        with self.assertRaisesRegex(SourceError,"Missing or duplicated"):
            parse_reporting_facts(sample().replace(GPU_START.encode(),
                                                   (GPU_START+" "+GPU_START).encode()))
        with self.assertRaisesRegex(SourceError,"Missing or duplicated"):
            parse_reporting_facts(sample().replace(b"Nscale Global Holdings Limited as Borrower",
                                                   b"Nscale Ward County Borrower SPV, LLC as Borrower"))

    def test_no_source_cannot_promote_synthetic_numbers(self):
        with self.assertRaises(SourceError):
            parse_reporting_facts(b"<!doctype html><html><body>Unknown financing data</body></html>")


if __name__ == "__main__":
    unittest.main()
