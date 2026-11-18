"""Source PDF archive tests use fabricated PDF bytes solely as transport fixtures."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from scripts.aics_archive_omi_policy_pdf import SOURCE_URLS, fetch_pdf, capture

RAW=b"%PDF-1.4\n"+b"test transport only - not a market report\n"*5+b"%%EOF\n"
class Fake:
    def __init__(self,url,raw=RAW,final=None):self.url=final or url;self.raw=raw
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def geturl(self):return self.url
    def read(self,n):return self.raw[:n]

def opener(req,timeout):
    assert timeout==50
    return Fake(req.full_url)

class TestOMIPdfSource(unittest.TestCase):
    def test_allowlisted_pdf_source(self):
        got,final=fetch_pdf(SOURCE_URLS[1],opener)
        self.assertEqual(got,RAW)
        self.assertEqual(final,SOURCE_URLS[1])

    def test_disallow_unrelated_pdf_domain(self):
        with self.assertRaises(ValueError):
            fetch_pdf("https://example.com/nominal.pdf",opener)

    def test_reject_redirect_outside_publisher_host(self):
        def bad(req,timeout):return Fake(req.full_url,final="https://attacker.invalid/b.pdf")
        with self.assertRaises(ValueError):
            fetch_pdf(SOURCE_URLS[1],bad)

    def test_reject_nonpdf_error_response(self):
        def bad(req,timeout):return Fake(req.full_url,raw=b"<html>Cloudflare</html>")
        with self.assertRaises(ValueError):
            fetch_pdf(SOURCE_URLS[1],bad)

    def test_reject_missing_trailer(self):
        def bad(req,timeout):return Fake(req.full_url,raw=b"%PDF-1.4\n"+b"A"*128)
        with self.assertRaises(ValueError):
            fetch_pdf(SOURCE_URLS[1],bad)

    def test_archive_fixtures_cannot_create_aics_index(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)
            x=capture(dest,opener)
            self.assertEqual(x["archive_count"],2)
            self.assertTrue(x["same_bytes_across_publisher_hosts"])
            self.assertEqual(x["promotion"],"BLOCKED")
            self.assertIsNone(x["index_aics"])
            self.assertIsNone(x["candidate_node_scores"])
            self.assertFalse(x["historical_pit_independently_verified"])
            self.assertFalse(x["original_primary_financial_claims_verified"])
            for s in x["source_candidates"]:
                self.assertEqual(s["source_sha256"],hashlib.sha256(RAW).hexdigest())
                self.assertEqual(Path(s["raw_path"]).read_bytes(),RAW)
            self.assertEqual(json.loads((dest/"receipt.json").read_text())["index_aics"],None)

if __name__=="__main__":
    unittest.main()
