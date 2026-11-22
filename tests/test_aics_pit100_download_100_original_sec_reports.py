"""AICS PIT100: 100 unique real SEC request assignments and strict receipts."""
from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError

from scripts.aics_pit100_download_100_original_sec_reports import (
    parse_submissions,submissions_from_archived_waves,select_targets,collect,
    is_valid_doc,
)
from scripts.aics_ten_node_agents import SEC_CIK


class HundredActualEDGARFirstFiledReportsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        sources=list(SEC_CIK.items())[:15]
        self.manifest={
            "schema":"aics-ten-real-source-acquisition-waves-with-companyfacts-v1",
            "captured_at_utc":"2026-11-22T08:00:00+00:00",
            "source_agents":10,"fixed_weights_total":1050,
            "complete_index":None,"independently_pit_verified_node_count":0,
            "rounds_report":[{"round":1,"operations":[]}],
        }
        for ident,cik in sources:
            entries=[]
            for i in range(12):
                entries.append({
                    "accessionNumber":f"{int(cik):010d}-26-{i+1:06d}",
                    "primaryDocument":f"original-report-{i+1}.htm",
                    "filingDate":"2026-11-11",
                    "acceptanceDateTime":"2026-11-11T18:22:07.000Z",
                    "form":"10-Q" if i%2 else "8-K",
                })
            record={
                "cik":int(cik),
                "filings":{"recent":{
                    k:[p[k] for p in entries] for k in entries[0]
                }},
            }
            raw=json.dumps(record).encode("utf-8")
            p=self.root/(ident+".json")
            p.write_bytes(raw)
            self.manifest["rounds_report"][0]["operations"].append({
                "source_id":ident,"status":"original_archived_no_pit",
                "raw_path":str(p),"raw_sha256":hashlib.sha256(raw).hexdigest(),
                "original_bytes":len(raw),
            })

    def test_100_genuine_distinct_public_document_http_tasks_and_lossless_sha(self):
        collected=collect(
            waves=self.manifest,as_of="2026-11-22",
            contact="AICS research investor@example.com",
            out=self.root/"report.json",
            rawdir=self.root/"reports",
            fetcher=lambda url,contact:
                (f"<html><body>SEC original public filing {url}</body></html>"
                 .encode("utf-8")*6),
            sleeper=lambda:None,
        )
        self.assertEqual(collected["genuine_original_sec_http_attempts"],100)
        self.assertEqual(collected["source_document_bytes_archived_successfully"],100)
        self.assertEqual(collected["source_document_failures_recorded_without_fabrication"],0)
        self.assertEqual(len(collected["tasks"]),100)
        self.assertEqual(len({r["source_url"] for r in collected["tasks"]}),100)
        self.assertEqual(len({r["download_worker_id"] for r in collected["tasks"]}),100)
        self.assertEqual(collected["dated_EDGAR_acceptance_metadata_records"],100)
        self.assertFalse(collected["SEC_14day_wait_policy_active"])
        self.assertFalse(collected["original_public_historical_feed_receipt_attested"])
        self.assertIsNone(collected["approved_AICS_index"])
        self.assertFalse(collected["trades_created"])
        for item in collected["tasks"]:
            self.assertTrue(item["success"])
            path=Path(item["compressed_archive_path"])
            decoded=gzip.decompress(path.read_bytes())
            self.assertEqual(hashlib.sha256(decoded).hexdigest(),item["raw_SHA256"])
            self.assertTrue(item["source_url"].startswith("https://www.sec.gov/Archives/"))
            self.assertFalse(item["historical_actual_first_provider_receipt_certified"])
        self.assertEqual(
            json.loads((self.root/"report.json").read_text())["source_document_bytes_archived_successfully"],100)

    def test_100_failed_real_original_requests_are_not_falsely_archived(self):
        def fail(url,contact):raise URLError("SEC temporarily blocked")
        r=collect(waves=self.manifest,as_of="2026-11-22",
                  contact="AICS research investor@example.com",
                  out=self.root/"failures.json",rawdir=self.root/"empty",
                  fetcher=fail,sleeper=lambda:None)
        self.assertEqual(r["genuine_original_sec_http_attempts"],100)
        self.assertEqual(r["source_document_bytes_archived_successfully"],0)
        self.assertEqual(r["source_document_failures_recorded_without_fabrication"],100)
        self.assertTrue(all(not x["success"] and x["raw_SHA256"] is None
                            for x in r["tasks"]))

    def test_source_archives_are_sha_checked_and_doc_path_is_restricted(self):
        self.assertTrue(is_valid_doc("original-report-1.htm"))
        self.assertFalse(is_valid_doc("../secret.txt"))
        self.assertFalse(is_valid_doc("a\\unsafe.html"))
        self.assertFalse(is_valid_doc("wrong.pdf"))
        bad=json.loads(json.dumps(self.manifest))
        bad["rounds_report"][0]["operations"][0]["raw_sha256"]="0"*64
        with self.assertRaises(ValueError):
            submissions_from_archived_waves(bad)
        first_id,first_cik=list(SEC_CIK.items())[0]
        targets=submissions_from_archived_waves(self.manifest)
        self.assertEqual(len(select_targets(targets)),100)
        b=json.loads((self.root/(first_id+".json")).read_text())
        b["filings"]["recent"]["primaryDocument"][0]="../bad.html"
        bad_raw=json.dumps(b).encode("utf-8")
        self.assertFalse(any("../" in x["source_url"]
                             for x in parse_submissions(
                                 bad_raw,source_id=first_id,cik=first_cik,
                                 as_of="2026-11-22")))


if __name__=="__main__":
    unittest.main()
