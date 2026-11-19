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

    def test_durable_original_sec_and_replay_hash_receipt_quarantines_exposure(self):
        import json
        from pathlib import Path
        p=Path("aics_data/research/nscale_dfs_s1_source_replay_rehash_2026-11-19.json")
        r=json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(r["github_workflow_run_id"],44475562317)
        self.assertEqual(r["github_workflow_artifact_id"],14505823806)
        self.assertEqual(r["downloaded_zip_sha256"],
                         "0a6b6c9101a089a2d9ee531f1d363b61302ad4f0b1812206c9719ca524802af0")
        self.assertEqual(r["replayed_dfs_report_sha256"],
                         "fa5b760f582a57d78749fcc7223ff6074b821a36946e70f7f849480234fff264")
        self.assertEqual(len(r["original_source_files_independently_sha_rehashed_outside_actions"]),2)
        self.assertEqual(r["extracted_from_same_original_s1"]["executed_payment_schedules"],40)
        self.assertEqual(r["extracted_from_same_original_s1"]["approximate_initial_term_rent_usd"],
                         2_540_000_000)
        self.assertEqual(r["extracted_from_same_original_s1"]["approximate_included_financing_charges_usd"],
                         34_800_000)
        self.assertFalse(r["rent_obligation_is_drawn_gpu_principal"])
        self.assertFalse(r["gpu_facility_and_dfs_rent_additive"])
        for key in ("paid_rent_usd", "outstanding_lease_liability_usd",
                    "drawn_gpu_principal_usd", "combined_economic_exposure_usd",
                    "legally_enforceable_parent_guarantee_amount_usd", "spv_node_score",
                    "index_aics"):
            self.assertIsNone(r[key],key)
        self.assertFalse(r["independent_historical_provider_pit_attested"])
        self.assertFalse(r["independent_24_month_oos"])
        self.assertEqual(r["synthetic_market_rows"],0)
        self.assertEqual(r["promotion"],"BLOCKED")

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
