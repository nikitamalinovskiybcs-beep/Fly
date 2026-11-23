"""Fixture-only tests: none of the test numbers are economic observations."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scripts.aics_ten_source_collection_rounds import (
    OUT, ROUNDS, TAGS, collect_ten, parse_companyfacts
)

NOW=dt.datetime(2026,11,22,12,tzinfo=dt.timezone.utc)


def fake_transport(url, useragent):
    if "/api/xbrl/companyfacts/CIK" in url:
        cik=int(url.split("CIK")[-1].split(".json")[0])
        a = {
            "NetCashProvidedByUsedInOperatingActivities": 219_000_000,
            "PaymentsToAcquirePropertyPlantAndEquipment": 56_000_000,
        }
        facts={}
        for tag, amount in a.items():
            facts[tag]={"units":{"USD":[{
                "val":amount, "form":"10-Q", "filed":"2026-11-20",
                "start":"2026-07-01","end":"2026-09-30",
                "accn":"0001234567-26-000001","frame":"CY2026Q3"
            }]}}
        return json.dumps({"cik":cik,"facts":{"us-gaap":facts}}).encode()
    if "/submissions/CIK" in url:
        cik=int(url.split("CIK")[-1].split(".json")[0])
        return json.dumps({"cik":cik,"filings":{"recent":{
            "form":["10-Q"],"filingDate":["2026-11-20"],
            "accessionNumber":["0001234567-26-000001"]}}}).encode()
    if "stlouisfed.org" in url:
        return json.dumps({"observations":[{"date":"2026-11-20",
                    "realtime_start":"2026-11-22", "value":"3.15"}]}).encode()
    if "markets.newyorkfed.org" in url:
        return json.dumps({"refRates":[{"effectiveDate":"2026-11-20",
                                         "type":"SOFR","percentRate":3.15}]}).encode()
    if "api.eia.gov" in url:
        return json.dumps({"response":{"data":[{"period":"2026-11-20T10",
                     "type":"D","value":"21000","respondent":"CISO"}]}}).encode()
    if "federalreserve.gov" in url:
        return b"<!DOCTYPE html><html><body>Unit testing only</body></html>"
    raise AssertionError("Unexpected remote endpoint")


class TenRealDataAcquisitionTest(unittest.TestCase):
    def test_ten_true_acquisition_rounds_produce_numeric_companyfacts(self):
        calls=[]
        def f(url,agent):
            calls.append(url)
            return fake_transport(url,agent)
        with tempfile.TemporaryDirectory() as tmp:
            d=collect_ten(out=Path(tmp), now=NOW,
                          sec_contact="AICS team team@institution.org",
                          fred_api_key="TEST_FRED",eia_api_key="TEST_EIA",
                          fetcher=f,pause=lambda:None)
            self.assertEqual(d["rounds"],10)
            self.assertEqual(d["source_agents"],10)
            self.assertEqual(len(d["rounds_report"]),10)
            self.assertEqual([r["round"] for r in d["rounds_report"]],
                             list(range(1,11)))
            self.assertEqual(d["total_http_attempts"],37)
            self.assertEqual(len(calls),37)
            self.assertEqual(d["successful_http_archives"],37)
            self.assertEqual(d["unique_original_source_ids_archived"],20)
            self.assertEqual(d["sec_companyfacts_original_snapshots_archived"],15)
            self.assertEqual(d["actual_numeric_facts_extracted_current_sec_snapshots"],30)
            self.assertEqual(d["unavailable_source_keys"],[])
            self.assertEqual(len(list((Path(tmp)/"raw").iterdir())),35)
            counts=Counter(calls)
            self.assertEqual(counts[
                "https://data.sec.gov/submissions/CIK0001769628.json"],2)
            self.assertEqual(counts[
                "https://data.sec.gov/submissions/CIK0001513845.json"],2)
            self.assertEqual(d["rounds_report"][5]["agent"],"SPV")
            self.assertEqual(d["rounds_report"][5]["real_http_attempts"],2)
            self.assertFalse(any(x["changed_since_prior_wave"]
                for x in d["rounds_report"][5]["operations"]))
            self.assertTrue(all(a["node_score_eligible"] is False
                for w in d["rounds_report"] for a in w["operations"]))
            self.assertIsNone(d["complete_index"])
            self.assertFalse(d["production_weights_changed"])
            self.assertFalse(d["trades_created"])
            root=(Path(tmp)/"ten_rounds_manifest.json").read_text()
            self.assertNotIn("TEST_FRED",root)
            self.assertNotIn("TEST_EIA",root)
            facts=json.loads((Path(tmp)/"actual_sec_xbrl_facts_unverified.json").read_text())
            self.assertEqual(len(facts),30)
            self.assertTrue(all(x["retrospective_provider_pit_certified"] is False
                                for x in facts))
            self.assertTrue(all(x["research_eligible_date_only_proxy"]=="2026-11-21"
                                for x in facts))
            for w in d["rounds_report"]:
                for operation in w["operations"]:
                    if operation["status"] in ("original_archived_no_pit",
                                               "numeric_source_archived_no_historical_pit"):
                        self.assertEqual(hashlib.sha256(
                            Path(operation["raw_path"]).read_bytes()).hexdigest(),
                            operation["raw_sha256"])

    def test_actual_blocked_eia_and_no_key_no_fake_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=collect_ten(out=Path(tmp),now=NOW,
                          sec_contact="AICS team team@institution.org",
                          fred_api_key="TEST_FRED",eia_api_key="",
                          fetcher=fake_transport,pause=lambda:None)
            self.assertEqual(d["rounds"],10)
            self.assertEqual(d["total_http_attempts"],36)
            self.assertEqual(d["successful_http_archives"],36)
            self.assertEqual(d["unavailable_source_keys"],["EIA_RTO_DEMAND"])
            self.assertEqual(d["rounds_report"][7]["agent"],"Power/Data Centers")
            self.assertIn("EIA_RTO_DEMAND", d["rounds_report"][7]["failures"])
            self.assertTrue(all("EIA_RTO_DEMAND" not in x["source_id"] or
                                x["status"]=="blocked_eia_key_missing"
                                for w in d["rounds_report"] for x in w["operations"]))

    def test_no_sec_key_prohibits_xbrl_fetch_and_claim(self):
        urls=[]
        def f(url, ua):
            urls.append(url)
            return fake_transport(url,ua)
        with tempfile.TemporaryDirectory() as tmp:
            d=collect_ten(out=Path(tmp),now=NOW,
                          sec_contact="",fred_api_key="TEST_FRED",eia_api_key="",
                          fetcher=f,pause=lambda:None)
            self.assertEqual(d["sec_companyfacts_original_snapshots_archived"],0)
            self.assertEqual(d["actual_numeric_facts_extracted_current_sec_snapshots"],0)
            self.assertFalse(any("sec.gov" in url for url in urls))
            self.assertIsNone(d["complete_index"])

    def test_real_time_asof_prevents_future_source_promotion(self):
        payload=json.loads(fake_transport(
            "https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json","ua"))
        c=payload["facts"]["us-gaap"]["NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"]
        c.append({"val":9999999,"form":"10-Q","filed":"2026-11-22",
                  "end":"2026-09-30","accn":"0001234567-26-000002"})
        out=parse_companyfacts(json.dumps(payload).encode(),
             cik="0000789019",at=NOW,sha="d"*64)
        self.assertEqual(len(out),2)
        self.assertTrue(all(x["filed_at"]!="2026-11-22" for x in out))
        with self.assertRaises(ValueError):
            parse_companyfacts(json.dumps(payload).encode(),
                               cik="0000789020",at=NOW,sha="d"*64)

    def test_spv_second_capture_can_detect_changed_official_original(self):
        seen={}
        def fetched(url,ua):
            if "/submissions/CIK0001769628" in url:
                seen[url]=seen.get(url,0)+1
                p=json.loads(fake_transport(url,ua))
                p["filings"]["recent"]["accessionNumber"][0]=(
                    "0001234567-26-000002" if seen[url]>1 else "0001234567-26-000001")
                return json.dumps(p).encode()
            return fake_transport(url,ua)
        with tempfile.TemporaryDirectory() as tmp:
            d=collect_ten(out=Path(tmp),now=NOW,
                          sec_contact="AICS team team@institution.org",
                          fred_api_key="TEST_FRED",eia_api_key="TEST_EIA",
                          fetcher=fetched,pause=lambda:None)
            changes=[a["source_id"] for w in d["rounds_report"]
                     for a in w["operations"] if a.get("changed_since_prior_wave")]
            self.assertEqual(changes,["SEC_CRWV"])
            self.assertEqual(len(list((Path(tmp)/"raw").iterdir())),36)


if __name__=="__main__":
    unittest.main()
