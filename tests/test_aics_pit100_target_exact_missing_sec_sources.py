"""PIT100 targeted missing original SEC submissions; no 100 random substitutes."""
from __future__ import annotations
import copy
import gzip
import re
import tempfile
import unittest
from pathlib import Path
from scripts.aics_pit100_target_exact_missing_sec_sources import (
    collect,canonical_original_urls,
)


def source_claims():
    rows=[]
    for i in range(36):
        acc=f"0000000001-25-{i+1:06d}"
        rows.append({
            "node":"Private Credit" if i>=9 else "Insurers",
            "cohort":f"SOURCE:{i:02d}","issuer":"TestIssuer",
            "CIK":"1","accession":acc,
            "source_original_doc_url":
                f"https://www.sec.gov/Archives/edgar/data/1/{acc.replace('-','')}/test-{i}.htm",
            "source_original_filed_day":"2025-01-01",
            "same_exact_CIK_accession_header_clock_verified":i<9,
        })
    return {
        "schema":"aics-PIT100-original-scoring-accession-to-SEC-SGML-crosswalk-v1",
        "research_underlying_original_filing_references":36,
        "research_source_cohorts":19,
        "source_bytes_today_not_historical_first_delivery":True,
        "underlying_accounting_metric_independently_parsed_from_exact_bytes":0,
        "exact_original_filing_accession_in_100_primary_archive_and_header":9,
        "complete_11node_AICS":None,
        "source_claims":rows,
    }


def fake_fetch(url,contact,max_bytes):
    split=url.split("/")
    flat=split[-2]
    acc=f"{flat[:10]}-{flat[10:12]}-{flat[12:]}"
    if url.endswith("-index-headers.html"):
        return (f"<SEC-HEADER>{acc}.hdr.sgml : 20250101\n"
                "<ACCEPTANCE-DATETIME>20250101150000\n"
                f"ACCESSION NUMBER: {acc}\n"
                "FILED AS OF DATE: 20250101\n</SEC-HEADER>\n").encode()
    return ("<html><body>Original issued SEC report "+acc+" source financial statements "
            +("X"*150)+"</body></html>").encode()


class TargetedSourceAccessionTests(unittest.TestCase):
    def test_exact_27_targeted_original_sec_reports_complete_36_of_36(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            r=collect(source_claims(),as_of="2026-11-22",
                      contact="Auditor Team auditor@example.com",
                      out=root/"report.json",rawdir=root/"raw",
                      fetcher=fake_fetch,sleeper=lambda:None)
            self.assertEqual(r["targeted_missing_exact_original_accession_attempts"],27)
            self.assertEqual(r["targeted_original_primary_and_SGML_both_sha_archived"],27)
            self.assertEqual(r["combined_original_score_source_accessions_now_hashed_and_clock_matched"],36)
            self.assertEqual(r["still_missing_original_exact_source_accessions_after_targeted_fetch"],0)
            self.assertEqual(r["original_accounting_values_automatically_verified_from_source_bytes"],0)
            self.assertEqual(r["historically_PIT_certified_11node_scores"],0)
            self.assertIsNone(r["full_11node_AICS"])
            self.assertFalse(r["trades_created"])
            for row in r["targeted_source_results"]:
                self.assertTrue(row["success_exact_original_scoring_document_and_sgml"])
                self.assertEqual(len(row["original_doc_raw_sha256"]),64)
                self.assertGreater(len(gzip.decompress(Path(row["original_doc_gzip_archived_path"]).read_bytes())),100)
                self.assertTrue(row["historical_first_data_feed_receipt_attested"] is False)

    def test_failed_exact_doc_is_not_backfilled_with_unrelated_sec_doc(self):
        def fail(url,contact,max_bytes):
            if "/000000000125000010/" in url:
                raise ValueError("Not available")
            return fake_fetch(url,contact,max_bytes)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            r=collect(source_claims(),as_of="2026-11-22",
                      contact="Auditor Team auditor@example.com",
                      out=root/"report.json",rawdir=root/"raw",
                      fetcher=fail,sleeper=lambda:None)
            self.assertEqual(r["targeted_original_primary_and_SGML_both_sha_archived"],26)
            self.assertEqual(r["combined_original_score_source_accessions_now_hashed_and_clock_matched"],35)
            self.assertEqual(r["still_missing_original_exact_source_accessions_after_targeted_fetch"],1)
            self.assertIsNone(r["full_11node_AICS"])

    def test_after_close_sec_acceptance_precedes_official_next_day_filing(self):
        claims=source_claims()
        target=claims["source_claims"][9]
        target["source_original_filed_day"]="2025-01-02"
        def after_close(url,contact,max_bytes):
            if ("/000000000125000010/" in url
                and url.endswith("-index-headers.html")):
                return (
                    "<SEC-DOCUMENT>0000000001-25-000010-index.html : 20250102\\n"
                    "<SEC-HEADER>0000000001-25-000010.hdr.sgml : 20250102\\n"
                    "<ACCEPTANCE-DATETIME>20250101181848\\n"
                    "ACCESSION NUMBER: 0000000001-25-000010\\n"
                    "FILED AS OF DATE: 20250102\\n"
                    "</SEC-HEADER>\\n").encode()
            return fake_fetch(url,contact,max_bytes)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            r=collect(claims,as_of="2026-11-22",
                      contact="Auditor Team auditor@example.com",
                      out=root/"report.json",rawdir=root/"raw",
                      fetcher=after_close,sleeper=lambda:None)
            self.assertEqual(r["targeted_original_primary_and_SGML_both_sha_archived"],27)
            self.assertEqual(r["exact_sources_with_SECGML_acceptance_day_different_from_filed_day"],1)
            row=next(x for x in r["targeted_source_results"]
                     if x["accession"]=="0000000001-25-000010")
            self.assertEqual(row["original_sgml_official_FILED_AS_OF_DATE"],"2025-01-02")
            self.assertTrue(row["acceptance_ET_calendar_day_differs_from_official_FILED_AS_OF_DATE"])
            self.assertEqual(row["official_filing_date_lag_after_acceptance_calendar_days"],1)
            self.assertFalse(row["accepted_before_16_ET_not_public_delivery_evidence"])
            self.assertFalse(row["historical_first_public_dissemination_attested"])

    def test_invalid_source_identity_and_forged_prior_match_count_fail(self):
        claim=source_claims()
        claim["source_claims"][10]["source_original_doc_url"]="https://evil.example/invalid.htm"
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaises(ValueError):
                collect(claim,as_of="2026-11-22",
                        contact="Auditor Team auditor@example.com",
                        out=root/"report.json",rawdir=root/"raw",
                        fetcher=fake_fetch,sleeper=lambda:None)
        claim=source_claims()
        claim["exact_original_filing_accession_in_100_primary_archive_and_header"]=8
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaises(ValueError):
                collect(claim,as_of="2026-11-22",
                        contact="Auditor Team auditor@example.com",
                        out=root/"report.json",rawdir=root/"raw",
                        fetcher=fake_fetch,sleeper=lambda:None)
        claim=source_claims()["source_claims"][0]
        u,h=canonical_original_urls(claim)
        self.assertIn(claim["accession"].replace("-",""),u)
        self.assertIn("-index-headers.html",h)

if __name__=="__main__":
    unittest.main()
