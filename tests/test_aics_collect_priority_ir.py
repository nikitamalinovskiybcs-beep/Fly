"""IR capture tests use fake HTML only: not financial observations or timestamps."""
import copy
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_collect_priority_ir import (
    DEFAULT_REGISTRY, check_url, discover_links, load_registry,
    retrieve, run, MAX_BYTES, IR_INDEX, IR_NODE_MAP,
)

class FakeHTTP:
    def __init__(self, url, raw, ctype="text/html", final=None):
        self.url = final or url
        self.raw = raw
        self.headers = {"Content-Type": ctype}
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def geturl(self):
        return self.url
    def read(self, n):
        return self.raw[:n]


FAKE_HTML = b'<!DOCTYPE html><html><body><h1>Unit test fixture - not financial data</h1></body></html>'


def fake_open(req, timeout):
    assert timeout == 35
    return FakeHTTP(req.full_url, FAKE_HTML)


class TestAICSOfficialIR(unittest.TestCase):
    def setUp(self):
        self.as_of = dt.date(2026, 11, 18)

    def test_seven_discoverable_official_releases(self):
        reg = load_registry(DEFAULT_REGISTRY, self.as_of)
        rows = reg["source_entries"]
        self.assertEqual(len(rows), 7)
        self.assertEqual(set(e["candidate_node"] for e in rows),
                         {"Insurers", "Neoclouds", "SPV"})
        self.assertEqual(sum(e["candidate_node"] == "Insurers" for e in rows), 2)
        self.assertEqual(sum(e["candidate_node"] == "Neoclouds" for e in rows), 3)
        self.assertEqual(sum(e["candidate_node"] == "SPV" for e in rows), 2)

    def test_all_sites_https_and_allowlisted(self):
        for e in load_registry(DEFAULT_REGISTRY, self.as_of)["source_entries"]:
            self.assertTrue(check_url(e["url"]))
        for url in ("http://nebius.com/a", "https://phishing.nebius.com/a",
                    "https://user@nebius.com/a", "https://nebius.com:8000/a",
                    "https://www.sec.gov/Archives/x"):
            self.assertFalse(check_url(url))

    def test_archive_and_zero_certified_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            r = run(DEFAULT_REGISTRY, Path(directory), self.as_of, opener=fake_open,
                    landing_pages={"CoreWeave": "https://investors.coreweave.com/news/default.aspx"})
            self.assertEqual(r["archived_candidates"], 7)
            self.assertEqual(r["landing_pages_archived"], 1)
            self.assertEqual(r["candidate_count"], 7)
            self.assertEqual(r["independently_certified_nodes"], 0)
            self.assertEqual(r["node_scores"], {"Insurers": None, "Neoclouds": None, "SPV": None})
            self.assertIsNone(r["index_aics"])
            self.assertIsNone(r["predictive_skill_score"])
            self.assertFalse(r["all_reports_historically_pit_verified"])
            self.assertEqual(r["promotion"], "BLOCKED")
            for e in r["candidates"]:
                self.assertEqual(e["sha256"], hashlib.sha256(FAKE_HTML).hexdigest())
                self.assertFalse(e["pit_verified"])
                self.assertFalse(e["score_eligible"])
                self.assertEqual(Path(e["raw_path"]).read_bytes(), FAKE_HTML)
            self.assertEqual(json.loads((Path(directory)/"manifest.json").read_text())["promotion"], "BLOCKED")

    def test_reject_future_release(self):
        reg = load_registry(DEFAULT_REGISTRY, self.as_of)
        reg["source_entries"][0]["publication_date_claim"] = "2026-12-10"
        with tempfile.TemporaryDirectory() as d:
            registry = Path(d)/"sources.json"
            registry.write_text(json.dumps(reg))
            result = run(registry, Path(d)/"raw", self.as_of,
                         opener=fake_open, landing_pages={})
            self.assertEqual(result["archived_candidates"], 6)
            self.assertEqual(result["candidates"][0]["status"], "future_publication_excluded")
            self.assertIsNone(result["index_aics"])

    def test_reject_registry_promoted_metrics(self):
        reg = load_registry(DEFAULT_REGISTRY, self.as_of)
        reg["source_entries"][0]["certified_metrics"] = ["fake_metric"]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"registry.json"
            path.write_text(json.dumps(reg))
            with self.assertRaises(ValueError):
                load_registry(path, self.as_of)

    def test_reject_registry_duplicate_id(self):
        reg = load_registry(DEFAULT_REGISTRY, self.as_of)
        reg["source_entries"][1]["source_id"] = reg["source_entries"][0]["source_id"]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"registry.json"
            path.write_text(json.dumps(reg))
            with self.assertRaises(ValueError):
                load_registry(path, self.as_of)

    def test_reject_unsafe_http_redirect(self):
        def phishing(req, timeout):
            return FakeHTTP(req.full_url, FAKE_HTML, final="https://attacker.example/steal")
        with self.assertRaises(ValueError):
            retrieve("https://nebius.com/investor-hub", "", opener=phishing)

    def test_reject_unexpected_content_type(self):
        def wrong(req, timeout):
            return FakeHTTP(req.full_url, b'{"not":"html"}', ctype="application/json")
        with self.assertRaises(ValueError):
            retrieve("https://nebius.com/investor-hub", "", opener=wrong)

    def test_reject_oversized_source(self):
        def big(req, timeout):
            return FakeHTTP(req.full_url, b"<html>" + b"z" * MAX_BYTES)
        with self.assertRaises(ValueError):
            retrieve("https://nebius.com/investor-hub", "", opener=big)

    def test_index_discovery_not_dated_as_historical_pit(self):
        body = (b'<html><a href="/news/new-earnings">Quarterly earnings 2026</a>'
                b'<a href="https://malicious.example/x">Results 2026</a>'
                b'<a href="/news/new-earnings">Quarterly earnings 2026</a></html>')
        links = discover_links(body, "https://nebius.com/investor-hub")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["url"], "https://nebius.com/news/new-earnings")
        self.assertFalse(links[0]["release_date_verified"])
        self.assertFalse(links[0]["score_eligible"])

    def test_fail_closed_on_tampered_archive(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            run(DEFAULT_REGISTRY, out, self.as_of, opener=fake_open, landing_pages={})
            digest = hashlib.sha256(FAKE_HTML).hexdigest()
            (out/"raw"/(digest+".html")).write_bytes(b"tampered")
            data = run(DEFAULT_REGISTRY, out, self.as_of, opener=fake_open, landing_pages={})
            self.assertEqual(data["archived_candidates"], 0)
            self.assertEqual(sum(e["status"] == "fetch_failed" for e in data["candidates"]), 7)

    def test_ir_catalog_covers_nine_corporate_linked_nodes(self):
        self.assertEqual(len(IR_INDEX), 15)
        self.assertEqual(set(IR_INDEX), set(IR_NODE_MAP))
        expected = {
            "Private Credit", "Insurers", "Neoclouds", "AI Equities",
            "Hyperscalers", "SPV", "Power/Data Centers",
            "Semiconductors Supply", "AI Demand",
        }
        actual = {node for nodes in IR_NODE_MAP.values() for node in nodes}
        self.assertEqual(actual, expected)
        self.assertNotIn("UST 30Y", actual)
        self.assertNotIn("Repo", actual)

    def test_all_ir_landing_pages_are_official_allowlisted_https(self):
        self.assertTrue(all(check_url(url) for url in IR_INDEX.values()))

if __name__ == "__main__":
    unittest.main()
