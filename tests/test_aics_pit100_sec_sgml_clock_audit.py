"""SEC SGML timezone audit: original acceptance vs inconsistent JSON clocks.

Synthetic strings in this unit test exercise parsing only; not historical
trading observations, first-delivery proof, or outputs to a trained model.
"""
from __future__ import annotations
import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from scripts.aics_pit100_sec_sgml_clock_audit import (
    collect,compare_clocks,parse_sgml,header_url,SEC,
)

def records():
    tasks=[]
    for i in range(100):
        acc=f"0000000001-26-{i+1:06d}"
        tasks.append({
            "CIK":"1","accession":acc,"filed_at":"2026-07-01",
            "source_url":SEC+f"1/{acc.replace('-','')}/abc.htm",
            "success":True,"raw_SHA256":"a"*64,
            "compressed_archive_path":"unit_test_original_stub.gz",
            "edgar_acceptance_time_current_registry_field":
                "2026-07-01T13:00:00Z" if i%2==0 else "2026-07-01T09:00:00Z",
        })
    return {
        "schema":"aics-PIT100-distinct-original-SEC-primary-report-downloads-v1",
        "research_as_of":"2026-11-22",
        "unique_distinct_original_filing_documents_requested":100,
        "genuine_original_sec_http_attempts":100,
        "original_public_historical_feed_receipt_attested":False,
        "SEC_14day_wait_policy_active":False,
        "approved_AICS_index":None,
        "tasks":tasks,
    }


def header(acc,time="20260701090000"):
    return (f"<SEC-DOCUMENT>{acc}-index.html : 20260701\n"
            f"<SEC-HEADER>{acc}.hdr.sgml : 20260701\n"
            f"<ACCEPTANCE-DATETIME>{time}\n"
            f"ACCESSION NUMBER: {acc}\n"
            "FILED AS OF DATE: 20260701\n"
            "CENTRAL INDEX KEY: 0000000001\n</SEC-HEADER>").encode()


class SECOriginalHeaderTimezoneTests(unittest.TestCase):
    def test_utc_and_local_json_mixed_formats_detected_and_not_trusted(self):
        local=parse_sgml(header("0000000001-26-000001"),
                         expected_accession="0000000001-26-000001")
        self.assertEqual(local.strftime("%H:%M"),"09:00")
        self.assertEqual(compare_clocks("2026-07-01T09:00:00Z",local),
                         "JSON_EASTERN_WALL_CLOCK_MATCH")
        self.assertEqual(compare_clocks("2026-07-01T13:00:00Z",local),
                         "JSON_UTC_WALL_CLOCK_MATCH")
        self.assertEqual(compare_clocks("2026-07-01T20:00:00Z",local),
                         "JSON_DISAGREES_WITH_ORIGINAL_SGML")
        self.assertEqual(compare_clocks(None,local),"JSON_UNAVAILABLE")

    def test_all_100_issuer_original_headers_archived_and_lossless(self):
        fixtures=records()
        def fetcher(url,identity):
            acc=url.rsplit("/",1)[1].removesuffix("-index-headers.html")
            num=int(acc[-6:])
            return header(acc,"20260701170000" if num%3==0 else "20260701090000")
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            report=collect(fixtures,contact="PIT Audit Team team@example.org",
                           as_of="2026-11-22",out=root/"clock.json",
                           rawdir=root/"raw",fetcher=fetcher,sleeper=lambda:None)
            self.assertEqual(report["original_SEC_header_http_attempts"],100)
            self.assertEqual(report["original_SEC_header_SHA256_archives_successful"],100)
            self.assertEqual(report["original_SEC_header_failures"],0)
            self.assertEqual(report["original_SEC_header_at_or_after16_ET"],33)
            self.assertEqual(report["original_SEC_header_same_day_pre16_ET_candidates"],67)
            diag=report["json_raw_timestamp_against_SGML_diagnostics"]
            self.assertGreater(diag["JSON_EASTERN_WALL_CLOCK_MATCH"],0)
            self.assertGreater(diag["JSON_UTC_WALL_CLOCK_MATCH"],0)
            self.assertIsNone(report["production_11node_AICS"])
            self.assertFalse(report["public_dissemination_PIT_certified"])
            self.assertFalse(report["historical_provider_first_byte_PIT_certified"])
            self.assertTrue(report["accepted_before_16_ET_does_not_prove_public_before_market_close"])
            for row in report["source_headers"]:
                self.assertTrue(row["original_sec_acceptance_clock_verified_from_sgml"])
                archived=gzip.decompress(Path(row["original_header_archive_gz_path"]).read_bytes())
                self.assertEqual(parse_sgml(archived,expected_accession=row["accession"]).strftime("%Y-%m-%d"),
                                 "2026-07-01")

    def test_invalid_or_cross_accession_sec_header_rejected(self):
        original="0000000001-26-000001"
        with self.assertRaises(ValueError):
            parse_sgml(header(original),expected_accession="0000000001-26-000002")
        with self.assertRaises(ValueError):
            parse_sgml(b"<ACCEPTANCE-DATETIME>20260701170000"*4,
                       expected_accession=original)
        bad=records()
        bad["tasks"][0]["source_url"]="https://malicious.example/abc"
        with self.assertRaises(ValueError):
            header_url(bad["tasks"][0])

    def test_failed_header_is_recorded_without_false_publication(self):
        def fetcher(url,identity):
            acc=url.rsplit("/",1)[1].removesuffix("-index-headers.html")
            if acc.endswith("000008"):
                raise ValueError("No SEC header returned")
            return header(acc)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            r=collect(records(),contact="PIT Audit Team team@example.org",
                      as_of="2026-11-22",out=root/"audit.json",rawdir=root/"raw",
                      fetcher=fetcher,sleeper=lambda:None)
            self.assertEqual(r["original_SEC_header_SHA256_archives_successful"],99)
            self.assertEqual(r["original_SEC_header_failures"],1)
            self.assertFalse(r["source_headers"][7]["original_sec_acceptance_clock_verified_from_sgml"])
            self.assertIsNone(r["production_11node_AICS"])
            self.assertEqual(len(r["source_headers"]),100)


if __name__=="__main__":
    unittest.main()
