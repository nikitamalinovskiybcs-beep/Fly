"""Offline source-archiver safety tests (fake HTTP documents, not market data)."""
import csv
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_archive_arcc_primary_sources import (
    DEFAULT_INPUT, allowed_url, fetch_source, run,
)

CONTACT = "AICS Research contact research@example.org"
DUMMY_HTML = b"<!DOCTYPE html><html><body>fixture only</body></html>"

class Response:
    def __init__(self, url, body=DUMMY_HTML, mime="text/html", redirect=None):
        self.url = redirect or url
        self.body = body
        self.headers = {"Content-Type": mime}
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def geturl(self): return self.url
    def read(self, size): return self.body[:size]


def opener(req, timeout):
    assert timeout == 35
    return Response(req.full_url)


class ArchiveTests(unittest.TestCase):
    def test_sec_url_allowlist(self):
        self.assertTrue(allowed_url("https://www.sec.gov/Archives/edgar/data/test.htm"))
        self.assertTrue(allowed_url("https://arcc.ares.com/news/123"))
        for url in ("http://www.sec.gov/test", "https://attacker.invalid/", 
                    "https://www.sec.gov.attacker.invalid/a", 
                    "https://x@www.sec.gov/a", "https://www.sec.gov:8080/a"):
            self.assertFalse(allowed_url(url))

    def test_success_archives_exact_source_bytes_but_never_certifies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run(DEFAULT_INPUT, root, CONTACT, as_of=dt.date(2026,11,18),
                         opener=opener)
            self.assertEqual(result["input_observation_count"],8)
            self.assertEqual(result["unique_primary_sources"],4)
            self.assertEqual(result["archived_sources"],4)
            self.assertFalse(result["numeric_values_verified_against_raw"])
            self.assertFalse(result["independently_verified_pit"])
            self.assertIsNone(result["index_aics"])
            self.assertIsNone(result["private_credit_node_score"])
            for entry in result["sources"]:
                self.assertEqual(entry["status"],"archived_raw_unverified")
                self.assertEqual(entry["sha256"],hashlib.sha256(DUMMY_HTML).hexdigest())
                self.assertEqual(Path(entry["raw_path"]).read_bytes(),DUMMY_HTML)
                self.assertFalse(entry["score_eligible"])
            self.assertEqual(json.loads((root/"manifest.json").read_text())["promotion"],"BLOCKED")

    def test_missing_real_sec_contact_blocks_sec_not_issuer(self):
        with tempfile.TemporaryDirectory() as directory:
            result=run(DEFAULT_INPUT,Path(directory),"",as_of=dt.date(2026,11,18),
                       opener=opener)
            self.assertEqual(result["archived_sources"],1)
            self.assertEqual(sum(e["status"]=="blocked_missing_real_sec_user_agent" 
                                 for e in result["sources"]),3)
            self.assertIsNone(result["index_aics"])

    def test_reject_unsafe_redirect(self):
        def redirect(req, timeout):
            return Response(req.full_url,redirect="https://attacker.invalid/stolen")
        with self.assertRaises(ValueError):
            fetch_source("https://www.sec.gov/Archives/hello",CONTACT,opener=redirect)

    def test_reject_non_html(self):
        def body(req, timeout):
            return Response(req.full_url,body=b'{"error":"rate limited"}',mime="application/json")
        with self.assertRaises(ValueError):
            fetch_source("https://www.sec.gov/Archives/hello",CONTACT,opener=body)

    def test_reject_empty(self):
        def empty(req, timeout):return Response(req.full_url,body=b"")
        with self.assertRaises(ValueError):
            fetch_source("https://www.sec.gov/Archives/hello",CONTACT,opener=empty)

    def test_reject_payload_without_html(self):
        def malformed(req, timeout):return Response(req.full_url,body=b"not a document")
        with self.assertRaises(ValueError):
            fetch_source("https://www.sec.gov/Archives/hello",CONTACT,opener=malformed)

    def test_fail_closed_if_archived_byte_digest_disagrees(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            run(DEFAULT_INPUT,root,CONTACT,as_of=dt.date(2026,11,18),opener=opener)
            digest=hashlib.sha256(DUMMY_HTML).hexdigest()
            (root/(digest+".html")).write_bytes(b"tampered")
            result=run(DEFAULT_INPUT,root,CONTACT,as_of=dt.date(2026,11,18),
                       opener=opener)
            self.assertEqual(result["archived_sources"],0)
            self.assertTrue(all(e["status"]=="fetch_failed" for e in result["sources"]))

    def test_invalid_sec_available_at_blocks_entire_batch(self):
        with DEFAULT_INPUT.open(newline='',encoding="utf-8") as f:
            dr=csv.DictReader(f);data=list(dr);fields=dr.fieldnames
        data[0]["available_at"]="2026-02-05"
        with tempfile.TemporaryDirectory() as directory:
            altered=Path(directory)/"bad.csv"
            with altered.open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
            with self.assertRaises(ValueError):
                run(altered,Path(directory)/"raw",CONTACT,as_of=dt.date(2026,11,18),
                    opener=opener)

if __name__=="__main__":
    unittest.main()
