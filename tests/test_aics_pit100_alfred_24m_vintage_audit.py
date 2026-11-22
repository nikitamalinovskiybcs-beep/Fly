"""ALFRED 24 historic as-of daily vintages: strictly dated original API results.

Unit fake bytes below test chronology and source validation only. They are not
market data, real ALFRED downloads, or historical AICS scores.
"""
from __future__ import annotations
import copy
import datetime as dt
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from scripts.aics_pit100_alfred_24m_vintage_audit import (
    collect,parse,query,no_secret_url,read_bytes,OVERLAY,
)

def fake(url):
    q=parse_qs(urlparse(url).query)
    day=q["realtime_start"][0]
    observed=(dt.date.fromisoformat(day)-dt.timedelta(days=1)).isoformat()
    return json.dumps({
        "observations":[
            {"date":observed,"value":"3.91",
             "realtime_start":day,"realtime_end":day},
            {"date":day,"value":"4.12",
             "realtime_start":day,"realtime_end":day}
        ],
    }).encode()

class ALFREDVintageMonthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overlay=read_bytes(OVERLAY)

    def test_historic_query_uses_strict_asof_not_current_revised(self):
        url=query("DGS30","2025-10-31","api-test-key-abcdefgh")
        x=parse_qs(urlparse(url).query)
        self.assertEqual(x["realtime_start"],["2025-10-31"])
        self.assertEqual(x["realtime_end"],["2025-10-31"])
        self.assertEqual(x["observation_end"],["2025-10-31"])
        self.assertNotIn("api-test-key",no_secret_url(url))
        with self.assertRaises(ValueError):
            query("FAKE_SERIES","2025-10-31","api-test-key-abcdefgh")

    def test_48_distinct_monthly_source_vintage_fetches_with_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            x=collect(self.overlay,key="api-test-key-abcdefgh",
                      as_of="2026-11-22",out=root/"result.json",rawdir=root/"raw",
                      fetcher=fake,sleeper=lambda:None)
            self.assertEqual(x["official_historical_vintage_requests_attempted"],48)
            self.assertEqual(x["official_historical_vintage_original_responses_archived"],48)
            self.assertEqual(x["official_historical_vintage_failed_or_missing"],0)
            self.assertEqual(len({(r["month"],r["series"]) for r in x["monthly_observations"]}),48)
            self.assertTrue(x["current_retrieval_does_not_prove_historical_first_receipt_time"])
            self.assertTrue(x["ALFRED_snapshot_query_does_not_certify_intraday_preclose_availability"])
            self.assertEqual(x["historical_pit_certified_index_nodes"],0)
            self.assertIsNone(x["complete_11node_AICS"])
            for r in x["monthly_observations"]:
                self.assertEqual(len(r["source_original_sha256"]),64)
                payload=gzip.decompress(Path(r["source_raw_archive_gz_path"]).read_bytes())
                self.assertEqual(parse(payload,series=r["series"],cutoff=r["market_cutoff_day"])
                                 ["latest_before_market_cutoff_dateonly"]["rate_pct_original_asof"],"3.91")
                self.assertEqual(r["asof_selection"]["latest_on_cutoff_day_unverified_intraday_only"]
                                 ["rate_pct_original_asof"],"4.12")

    def test_future_and_mixed_realtime_vintages_rejected(self):
        t=fake(query("IORB","2025-08-29","api-test-key-abcdefgh"))
        j=json.loads(t)
        j["observations"][0]["realtime_start"]="2026-01-01"
        with self.assertRaises(ValueError):
            parse(json.dumps(j).encode(),series="IORB",cutoff="2025-08-29")
        j=json.loads(t)
        j["observations"][0]["date"]="2025-08-30"
        with self.assertRaises(ValueError):
            parse(json.dumps(j).encode(),series="IORB",cutoff="2025-08-29")
        j=json.loads(t)
        j["observations"][0]["value"]="BAD"
        with self.assertRaises(ValueError):
            parse(json.dumps(j).encode(),series="IORB",cutoff="2025-08-29")

    def test_failed_official_alfred_returns_null_not_imputation(self):
        def failer(url):
            if "series_id=IORB" in url:
                raise ValueError("No authenticated historical vintage")
            return fake(url)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            x=collect(self.overlay,key="api-test-key-abcdefgh",
                      as_of="2026-11-22",out=root/"output.json",rawdir=root/"raw",
                      fetcher=failer,sleeper=lambda:None)
            self.assertEqual(x["official_historical_vintage_original_responses_archived"],24)
            self.assertEqual(x["official_historical_vintage_failed_or_missing"],24)
            self.assertTrue(all(r["source_original_sha256"] is None for r in x["monthly_observations"]
                                if r["series"]=="IORB"))
            self.assertIsNone(x["complete_11node_AICS"])
            self.assertFalse(x["trades_created"])

if __name__=="__main__":
    unittest.main()
