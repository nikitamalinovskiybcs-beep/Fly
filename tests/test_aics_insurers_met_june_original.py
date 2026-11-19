"""Test-only SEC fixture. None of these fabricated tokens enter market history."""
import copy
import datetime as dt
import unittest
from unittest.mock import patch
from scripts import aics_insurers_met_june_original as audit

def fake():
    head=("<SEC-DOCUMENT>fixture\n<SEC-HEADER>\n"
         "ACCESSION NUMBER: 0001099219-26-000050\n"
         "CONFORMED SUBMISSION TYPE: 10-Q\n"
         "CENTRAL INDEX KEY: 0001099219\n"
         "FILED AS OF DATE: 20260806\n</SEC-HEADER>\n")
    body=("<html><body>Mortgage loans (net of allowance for credit loss of "
          "$1,358 and $1,193, respectively; includes $0 and $35, respectively, "
          "of mortgage loans held-for-sale) $82,856 $84,593 "
          "Rollforward of ACL for Mortgage Loans by Portfolio Segment "
          "Balance, beginning of period $807 $115 $271 $1,193 "
          "Provision (release) 348 1 (33) 316 "
          "Charge-offs, net of recoveries (139) (9) (3) (151) "
          "Balance, end of period $1,016 $107 $235 $1,358 "
          "The gross charge-offs of mortgage loans by origination year</body></html>")
    return (head+"<DOCUMENT>\n<TYPE>10-Q\n<FILENAME>met-20260630.htm\n"
            "<TEXT>\n"+body+"\n</TEXT>\n</DOCUMENT>").encode()

class TestMETQ2CreditOriginal(unittest.TestCase):
    def test_real_source_uri_dates_and_frozen_eligibility(self):
        self.assertEqual(audit.FILED.isoformat(),"2026-08-06")
        self.assertEqual(audit.ACCESSION,"0001099219-26-000050")
        self.assertEqual(audit.URL,
            "https://www.sec.gov/Archives/edgar/data/1099219/000109921926000050/0001099219-26-000050.txt")
        audit.check_cutoff(dt.date(2026,11,19))
        for date in (dt.date(2026,11,18),dt.date(2026,11,20)):
            with self.assertRaisesRegex(ValueError,"Only exact"):
                audit.check_cutoff(date)
    def test_original_fixture_rollforward_arithmetic_and_no_score(self):
        data=audit.build(fake(),allow_synthetic_test_fixture=True)
        f=data["facts"]
        self.assertEqual(f["mortgage_loans_net_change_millions"],-1737)
        self.assertEqual(f["mortgage_acl_change_millions"],165)
        self.assertEqual(f["acl_segment_begin_millions"]["total"],1193)
        self.assertEqual(f["acl_segment_six_month_provision_millions"]["total"],316)
        self.assertEqual(f["net_six_month_chargeoffs_millions"],151)
        self.assertEqual(f["acl_segment_end_millions"]["total"],1358)
        self.assertEqual(f["mortgage_loans_net_millions"]["2026-06-30"],82856)
        self.assertFalse(data["met_september_q3_metrics_used"])
        self.assertIsNone(data["met_september_q3_balance_usd"])
        self.assertFalse(data["independent_historical_pit_attested"])
        self.assertIsNone(data["insurers_node_score"])
        self.assertIsNone(data["index_aics"])
        self.assertEqual(data["promotion"],"BLOCKED")
    def test_forged_sec_issuer_date_form_accession_rejected(self):
        for old,new in (
            (b"0001099219-26-000050",b"0001099219-26-000051"),
            (b"CONFORMED SUBMISSION TYPE: 10-Q",b"CONFORMED SUBMISSION TYPE: 8-K"),
            (b"CENTRAL INDEX KEY: 0001099219",b"CENTRAL INDEX KEY: 0001137774"),
            (b"FILED AS OF DATE: 20260806",b"FILED AS OF DATE: 20260805")):
            with self.subTest(change=new),self.assertRaisesRegex(ValueError,"mismatch"):
                audit.build(fake().replace(old,new),allow_synthetic_test_fixture=True)
    def test_forged_mortgage_loan_and_acl_numbers_fail_closed(self):
        for old,new in ((b"82,856",b"90,856"),(b"1,358",b"1,458"),
                        (b"84,593",b"74,593"),(b"1,193",b"1,293"),
                        (b"316",b"315"),(b"1,016",b"1,017")):
            with self.subTest(change=new),self.assertRaises(ValueError):
                audit.build(fake().replace(old,new),allow_synthetic_test_fixture=True)
    def test_missing_primary_html_and_wrong_document_form_rejected(self):
        for old,new in ((b"<TYPE>10-Q",b"<TYPE>EX-99"),
                        (b"<FILENAME>met-20260630.htm",b"<FILENAME>unrelated.htm"),
                        (b"Rollforward of ACL for Mortgage Loans by Portfolio Segment",
                         b"Unknown credit disclosure")):
            with self.subTest(change=new),self.assertRaises(ValueError):
                audit.build(fake().replace(old,new),allow_synthetic_test_fixture=True)
    def test_exact_primary_original_hash_is_required_in_production(self):
        self.assertEqual(audit.PINNED_FULL_ORIGINAL_BYTES,42939093)
        self.assertEqual(audit.PINNED_FULL_ORIGINAL_SHA256,
                         "a2b5359da635b89ffb3ab39908538328d52d4dac6099073ffcc4b4636fc3209b")
        self.assertEqual(audit.PINNED_PRIMARY_DOCUMENT_SHA256,
                         "363dd1ce87ef01168f4bda0c02c7ad1779f5f3b81d698a3c8e0bb4db6d7638d6")
        with self.assertRaisesRegex(ValueError,"SHA256"):
            audit.build(fake())

    def test_external_rehash_source_receipt_pinned_without_score(self):
        import json
        from pathlib import Path
        r=json.loads(Path(
          "aics_data/research/met_2026q2_original_sec_acl_independent_rehash_2026-11-19.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(r["workflow_run_id"],44579156955)
        self.assertEqual(r["artifact_id"],14557198374)
        self.assertEqual(r["artifact_zip_sha256"],
                         "9dbd375f2d492bf8590cae480cbf6038c97f6f6e68076b6bab0f543a0062a856")
        self.assertTrue(r["artifact_zip_crc_integrity_passed"])
        self.assertEqual(r["original_full_sec_submission_bytes"],
                         audit.PINNED_FULL_ORIGINAL_BYTES)
        self.assertEqual(r["original_full_sec_submission_sha256"],
                         audit.PINNED_FULL_ORIGINAL_SHA256)
        self.assertEqual(r["original_embedded_primary_document_sha256"],
                         audit.PINNED_PRIMARY_DOCUMENT_SHA256)
        self.assertEqual(r["replay_research_json_sha256"],
                         "aabdaa0a249081eca466b402e413065371a803902ceea8d3de69393b1b97ac36")
        self.assertEqual(r["aics_sec_available_at_plus_14_calendar_days"],"2026-08-20")
        f=r["source_derived_observations"]
        self.assertEqual(f["mortgage_loans_net"]["later"],82856)
        self.assertEqual(f["mortgage_loan_acl"]["later"],1358)
        self.assertEqual(f["conservation_check"],"1193+316-151=1358")
        self.assertFalse(r["met_sept_2026_q3_metrics_allowed_on_2026_11_19"])
        self.assertIsNone(r["met_sept_2026_q3_mortgage_loan_amount_usd"])
        self.assertFalse(r["independent_historical_provider_delivery_attested"])
        self.assertFalse(r["24_month_untouched_oos"])
        self.assertFalse(r["cross_issuer_direct_loan_risk_ratio_claim"])
        self.assertEqual(r["milestones_completed"],22)
        self.assertIsNone(r["insurers_node_score"])
        self.assertIsNone(r["index_aics"])
        self.assertEqual(r["promotion"],"BLOCKED")

    def test_unlicensed_capture_agent_is_rejected(self):
        for agent in ("","AICS fake@example.com","AICS"):
            with self.assertRaises(ValueError):
                audit.fetch(agent)

if __name__=="__main__":
    unittest.main()
