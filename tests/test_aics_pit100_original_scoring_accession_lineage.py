"""No inferred PIT from 100 unrelated SEC submissions; exact accession only."""
from __future__ import annotations
import copy
import unittest
from scripts.aics_pit100_original_scoring_accession_lineage import (
    extract,build,read_bytes,OVERLAY,CREDIT,PRU,NEO,
)

def fixtures(source_rows):
    tasks=[]
    for i in range(100):
        acc=f"0000000001-26-{i+1:06d}"
        tasks.append({
            "CIK":"1","accession":acc,
            "source_url":f"https://www.sec.gov/Archives/edgar/data/1/{acc.replace('-','')}/x.htm",
            "success":True,"raw_SHA256":"a"*64,"filed_at":"2026-05-01",
        })
    for j,row in enumerate(source_rows[:2]):
        tasks[j].update({
            "CIK":row["CIK"],"accession":row["accession"],
            "source_url":row["source_original_doc_url"],
            "filed_at":row["source_original_filed_day"] or "2026-05-01",
            "raw_SHA256":str(j+1)*64,
        })
    heads=[{
        "CIK":t["CIK"],"accession":t["accession"],
        "original_sec_acceptance_clock_verified_from_sgml":i<2,
        "original_filing_date":t["filed_at"],
        "acceptance_et_wall_clock":t["filed_at"]+" 10:00:00",
        "original_sec_header_raw_SHA256":"b"*64,
        "accepted_before_16_et":True,
    } for i,t in enumerate(tasks)]
    reports={
        "schema":"aics-PIT100-distinct-original-SEC-primary-report-downloads-v1",
        "original_public_historical_feed_receipt_attested":False,
        "tasks":tasks,
    }
    headers={
        "schema":"aics-PIT100-first-original-SEC-SGML-timezone-clocks-audit-v1",
        "public_dissemination_PIT_certified":False,
        "source_headers":heads,
    }
    return reports,headers


class OriginalSECScoringAccessionCrosswalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=[read_bytes(p) for p in (OVERLAY,CREDIT,PRU,NEO)]
        cls.rows,cls.cohorts=extract(*cls.data)

    def test_36_genuine_issuer_doc_references_and_19_node_cohorts(self):
        self.assertEqual(len(self.rows),36)
        self.assertEqual(len(self.cohorts),19)
        self.assertEqual({x["node"] for x in self.rows},
                         {"Insurers","Private Credit","Neoclouds"})
        self.assertEqual(sum(x["node"]=="Insurers" for x in self.rows),9)
        self.assertEqual(sum(x["node"]=="Private Credit" for x in self.rows),21)
        self.assertEqual(sum(x["node"]=="Neoclouds" for x in self.rows),6)
        self.assertEqual(len({(x["CIK"],x["accession"]) for x in self.rows}),36)
        self.assertTrue(all(x["metric_original_bytes_independently_parsed"] is False for x in self.rows))

    def test_only_two_same_accession_source_headers_verified_in_fixture(self):
        manifest,headers=fixtures(self.rows)
        r=build(*self.data,manifest,headers)
        self.assertEqual(r["research_underlying_original_filing_references"],36)
        self.assertEqual(r["research_source_cohorts"],19)
        self.assertEqual(r["exact_original_filing_accession_in_100_primary_archive_and_header"],2)
        self.assertEqual(r["source_event_cohorts_with_all_header_accessions"],2)
        self.assertEqual(r["original_source_filing_claims_not_in_100_sample"],34)
        self.assertEqual(r["underlying_accounting_metric_independently_parsed_from_exact_bytes"],0)
        self.assertEqual(r["historically_pit_certified_node_count"],0)
        self.assertIsNone(r["complete_11node_AICS"])
        self.assertFalse(r["trades_created"])
        self.assertEqual(sum(x["same_exact_CIK_accession_header_clock_verified"] for x in r["source_claims"]),2)
        self.assertTrue(all(x["historical_public_dissemination_before_market_close_attested"] is False
                            for x in r["source_claims"]))

    def test_unrelated_100_filing_headers_do_not_certify_scoring_inputs(self):
        manifest,headers=fixtures(self.rows)
        for i in range(2):
            manifest["tasks"][i]["accession"]=f"0000000001-26-{i+90:06d}"
            headers["source_headers"][i]["accession"]=manifest["tasks"][i]["accession"]
        r=build(*self.data,manifest,headers)
        self.assertEqual(r["exact_original_filing_accession_in_100_primary_archive_and_header"],0)
        self.assertEqual(r["source_event_cohorts_with_all_header_accessions"],0)
        self.assertIsNone(r["complete_11node_AICS"])

    def test_unsafe_pru_amount_or_filing_date_and_header_mismatch_blocked(self):
        manifest,headers=fixtures(self.rows)
        bad=copy.deepcopy(self.data)
        bad[2]["events"][0]["score_pct"]="999"
        with self.assertRaises(ValueError):
            extract(*bad)
        bad=copy.deepcopy(self.data)
        bad[1]["source_events"][0]["issuer_source_provenance"]["ARCC"]="https://evil.example/exhibit"
        with self.assertRaises(ValueError):
            extract(*bad)
        headers=copy.deepcopy(headers)
        headers["source_headers"][0]["original_filing_date"]="2000-01-01"
        with self.assertRaises(ValueError):
            build(*self.data,manifest,headers)

if __name__=="__main__":
    unittest.main()
