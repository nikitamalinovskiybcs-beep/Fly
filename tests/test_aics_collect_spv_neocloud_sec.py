"""SEC SPV/Neocloud source checks: fake HTML is a network unit test fixture."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_collect_spv_neocloud_sec import (
    DEFAULT_REGISTRY, ISSUER_CIKS, archive, fetch_html,
    load_registry, run, sec_url_check
)

ASOF = dt.date(2026, 11, 18)
CONTACT = "AICS Research accountable_contact@research-institute.org"
FIXTURE_HTML = b"<!DOCTYPE html><html><body>Network test fixture only</body></html>"


class FakeResponse:
    def __init__(self, url, body=FIXTURE_HTML, mime="text/html", redirect=None):
        self.final_url = redirect or url
        self.body = body
        self.headers = {"Content-Type": mime}
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def geturl(self): return self.final_url
    def read(self, size): return self.body[:size]


def fake_open(req, timeout):
    assert timeout == 45
    return FakeResponse(req.full_url)


class SECNeocloudSPVTests(unittest.TestCase):
    def registry(self):
        return load_registry(DEFAULT_REGISTRY)

    def test_four_fixed_issuer_ciks(self):
        self.assertEqual(ISSUER_CIKS["CoreWeave"], "0001769628")
        self.assertEqual(ISSUER_CIKS["Nebius Group"], "0001513845")
        self.assertEqual(ISSUER_CIKS["Equinix"], "0001101239")
        self.assertEqual(ISSUER_CIKS["Applied Digital"], "0001144879")

    def test_five_real_filing_links_and_dates(self):
        records = self.registry()["documents"]
        self.assertEqual(len(records), 5)
        self.assertEqual(sum(r["available_at"] > ASOF.isoformat() for r in records), 1)
        for doc in records:
            sec_url_check(doc)
            self.assertEqual(
                dt.date.fromisoformat(doc["available_at"]),
                dt.date.fromisoformat(doc["filed_at"]) + dt.timedelta(days=14)
            )

    def test_coreweave_q3_not_eligible_before_nov26(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run(DEFAULT_REGISTRY, Path(directory), ASOF,
                         contact=CONTACT, opener=fake_open)
        self.assertEqual(result["date_eligible_documents"], 4)
        self.assertEqual(result["date_excluded_documents"], 1)
        self.assertEqual(result["raw_documents_archived"], 4)
        coreweave = next(r for r in result["documents"] if r["issuer"] == "CoreWeave")
        self.assertEqual(coreweave["available_at"], "2026-11-26")
        self.assertEqual(coreweave["status"], "excluded_14_day_sec_lag")
        self.assertFalse(coreweave["score_eligible"])

    def test_scientific_gates_stay_blocked_after_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            report = run(DEFAULT_REGISTRY, out, ASOF,
                         contact=CONTACT, opener=fake_open)
            self.assertFalse(report["independently_verified_pit"])
            self.assertFalse(report["all_11_nodes_certified"])
            self.assertIsNone(report["spv_node_score"])
            self.assertIsNone(report["neoclouds_node_score"])
            self.assertIsNone(report["index_aics"])
            self.assertIsNone(report["predictive_skill_score"])
            self.assertEqual(report["promotion"], "BLOCKED")
            loaded = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["raw_documents_archived"], 4)
            for item in loaded["documents"]:
                self.assertFalse(item["filing_content_numeric_metrics_certified"])
                if item["status"] == "archived_raw_unverified":
                    self.assertEqual(item["sha256"], hashlib.sha256(FIXTURE_HTML).hexdigest())
                    self.assertEqual(Path(item["raw_path"]).read_bytes(), FIXTURE_HTML)

    def test_missing_contact_blocks_without_fake_retrieval(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run(DEFAULT_REGISTRY, Path(directory), ASOF, opener=fake_open)
        self.assertEqual(result["raw_documents_archived"], 0)
        self.assertEqual(
            sum(x["status"] == "blocked_missing_sec_user_agent"
                for x in result["documents"]), 4
        )
        self.assertIsNone(result["index_aics"])

    def test_eligible_future_filings_only_appear_on_or_after_date(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run(DEFAULT_REGISTRY, Path(directory),
                         dt.date(2026, 11, 26), CONTACT, opener=fake_open)
        self.assertEqual(result["raw_documents_archived"], 5)
        self.assertEqual(result["date_excluded_documents"], 0)

    def test_registry_blocks_early_availability(self):
        obj = self.registry()
        obj["documents"][0]["available_at"] = obj["documents"][0]["filed_at"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(obj))
            with self.assertRaises(ValueError):
                load_registry(path)

    def test_registry_blocks_cross_issuer_or_untrusted_sec_path(self):
        obj = self.registry()
        obj["documents"][0]["document_url"] = "https://attacker.invalid/a.htm"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(obj))
            with self.assertRaises(ValueError):
                load_registry(path)

    def test_registry_blocks_false_proven_spv(self):
        obj = self.registry()
        obj["policy"]["spv_candidate_is_proven_spv"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(obj))
            with self.assertRaises(ValueError):
                load_registry(path)

    def test_reject_sec_redirect_to_other_filing(self):
        url = self.registry()["documents"][0]["document_url"]
        def redirected(req, timeout):
            return FakeResponse(req.full_url, redirect="https://www.sec.gov/Archives/changed.htm")
        with self.assertRaises(ValueError):
            fetch_html(url, CONTACT, opener=redirected)

    def test_reject_non_html_error_response(self):
        url = self.registry()["documents"][0]["document_url"]
        def wrong(req, timeout):
            return FakeResponse(req.full_url, body=b'{"error":"blocked"}', mime="application/json")
        with self.assertRaises(ValueError):
            fetch_html(url, CONTACT, opener=wrong)

    def test_sha256_detects_modified_local_original(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            sha, path = archive(out, "SEC_TEST", FIXTURE_HTML)
            self.assertEqual(sha, hashlib.sha256(FIXTURE_HTML).hexdigest())
            Path(path).write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                archive(out, "SEC_TEST", FIXTURE_HTML)


if __name__ == "__main__":
    unittest.main()
