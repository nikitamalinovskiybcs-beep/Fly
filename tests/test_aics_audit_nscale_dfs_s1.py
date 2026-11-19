"""Synthetic parser fixtures, never financial-data observations or historic PIT."""
import datetime as dt
import unittest

from scripts.aics_audit_nscale_dfs_s1 import (
    SECTION_START, SECTION_END, REQUIRED_PHRASES, extract_terms,
)
from scripts.aics_collect_nscale_ward_sec import SourceError

BODY = (
    "<!DOCTYPE html><html><body><p>"
    + SECTION_START + " (each, a “Customer”) "
    + ". ".join(REQUIRED_PHRASES)
    + SECTION_END + " Initial Borrower."
    + "</p></body></html>"
).encode("utf-8")


class TestDFSAgreementEvidence(unittest.TestCase):
    def test_only_rent_schedules_and_distinct_parent_guaranty_extracted(self):
        x = extract_terms(BODY)
        self.assertEqual(x["borrower_legal_entities"], [
            "Nscale Ward County Borrower SPV, LLC",
            "Nscale NC Borrower SPV, LLC",
        ])
        self.assertEqual(x["guarantor"], "Nscale Global Holdings Ltd")
        self.assertEqual(x["funder"], "Dell Financial Services L.L.C.")
        self.assertEqual(x["framework_agreements"], 2)
        self.assertEqual(x["payment_schedules_executed"], 40)
        self.assertEqual(x["aggregate_initial_term_rent_usd_approx"], 2_540_000_000)
        self.assertEqual(x["included_financing_charges_usd_approx"], 34_800_000)
        self.assertEqual(x["as_reported_at"], "2026-09-04")

    def test_each_legal_and_financial_clause_required(self):
        for item in REQUIRED_PHRASES:
            with self.subTest(phrase=item[:35]):
                forged = BODY.replace(item.encode(), b"unverified")
                with self.assertRaisesRegex(SourceError, "original guarantee"):
                    extract_terms(forged)

    def test_changed_schedule_count_cannot_become_research_fact(self):
        with self.assertRaises(SourceError):
            extract_terms(BODY.replace(b"40 have been fully executed",
                                       b"39 have been fully executed"))

    def test_replacing_lease_rent_with_loan_drawing_fails(self):
        forged = BODY.replace(b"aggregate initial-term rent",
                              b"actual drawn GPU principal")
        with self.assertRaises(SourceError):
            extract_terms(forged)

    def test_duplicate_disclosure_section_fails_closed(self):
        with self.assertRaisesRegex(SourceError, "ambiguous"):
            extract_terms(BODY.replace(b"</body>", BODY.decode().split("<p>")[1].split("</p>")[0].encode() + b"</body>"))

    def test_missing_source_does_not_report_lease_obligations(self):
        with self.assertRaisesRegex(SourceError, "Missing"):
            extract_terms(b"<!DOCTYPE html><html><body>no SEC source</body></html>")


if __name__ == "__main__":
    unittest.main()
