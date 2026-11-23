"""Synthetic HTML fixtures for SEC parsers, not synthetic historical data inputs."""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_neocloud_six_original_cashflows_replay import (
    build,parse_coreweave,parse_nebius,LEDGER,
)


def text_for_source(key):
    if key=="crwv_q1":
        return ("Net cash provided by (used in) operating activities $ 61,168 $ 2,039,038 "
                "Purchase of property and equipment, including capitalized internal-use "
                "software $ ( 1,407,359 ) $ ( 1,741,935 )")
    if key=="crwv_h1":
        return ("Net cash provided by (used in) operating activities $ ( 190,083 ) $ 1,921,214 "
                "Purchase of property and equipment, including capitalized internal-use "
                "software $ ( 3,860,351 ) $ ( 3,989,096 )")
    if key=="crwv_9m":
        return ("Net cash provided by operating activities $ 1,499,051 $ 2,562,436 "
                "Purchase of property and equipment, including capitalized internal-use "
                "software $ ( 6,249,239 ) $ ( 5,204,251 )")
    if key=="nbis_q1":
        return ("Cash used in operating activities (69.8 ) (197.8 ) 183 % "
                "Puchases of property, plant and equipment (58.9 ) (544.0 )")
    if key=="nbis_q2":
        return ("Cash used in operating activities – continuing operations "
                "(99.0 ) (167.7 ) 69 % (162.0 ) (352.0 ) 117 % "
                "Purchases of property, plant and equipment "
                "(159.0 ) (510.6 ) 221 % (217.9 ) (1,054.5 ) 384 %")
    if key=="nbis_9m":
        return ("Net cash used in operating activities (196.8 ) (432.4 ) "
                "Capital expenditures (390.0 ) (2,010.0 )")
    raise ValueError(key)


class SixOriginalSourceCashflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name)
        self.ledger=json.loads(LEDGER.read_text(encoding="utf-8"))
        self.tasks=[]
        self.archived=[]
        for key,source in self.ledger["sources"].items():
            raw=("<html><body><p>"+text_for_source(key)+
                 "</p><p>Not a historical first feed receipt. Original issuer numerical "
                 "test fixture only.</p></body></html>").encode()
            file=self.directory/(key+".gz")
            file.write_bytes(gzip.compress(raw,mtime=0))
            self.tasks.append({
                "CIK":self.ledger["sources"][key]["source_page"].split("/")[6],
                "accession":source["accession"],
                "workstream":"exact_SEC_source_bytes_and_numeric_replay",
                "cohort":next("NEOCLOUDS:"+period for period, pair in {
                    "2025-Q1":("crwv_q1","nbis_q1"),
                    "2025-Q2":("crwv_h1","nbis_q2"),
                    "2025-Q3":("crwv_9m","nbis_9m"),
                }.items() if key in pair),
                "issuer":source["issuer"],
                "archive_origin":"targeted_exact_original",
                "exact_referenced_document_and_sgml_bytes_rehashed":True,
            })
            self.archived.append({
                "CIK":self.tasks[-1]["CIK"],
                "accession":source["accession"],
                "original_doc_gzip_archived_path":str(file),
                "original_doc_raw_sha256":hashlib.sha256(raw).hexdigest(),
            })
        self.tasks += [{"workstream":"forecast_governance_negative_controls"} for _ in range(94)]
        self.args=(
            self.ledger,
            {"schema":"aics-priority100-evidence-workbench-v1",
             "full_11node_AICS":None,
             "independently_certified_nodes":0,
             "as_of":"2026-11-22",
             "priority_queue":self.tasks},
            {"schema":"aics-PIT100-distinct-original-SEC-primary-report-downloads-v1","tasks":[]},
            {"schema":"aics-PIT100-targeted-original-scoring-accession-SGML-fill-v1",
             "targeted_source_results":self.archived},
        )

    def test_coreweave_usd_thousand_vs_million_period_separation(self):
        h=("<html>"+text_for_source("crwv_h1")+"</html>").encode()
        parsed=parse_coreweave(h)
        self.assertEqual(parsed["cfo_ytd_usd_m"],"-190.083")
        self.assertEqual(parsed["cash_purchases_ytd_usd_m"],"3860.351")

    def test_nebius_quarter_vs_h1_different_scope(self):
        parsed=parse_nebius(("<html>"+text_for_source("nbis_q2")+"</html>").encode(),"2025-Q2")
        self.assertEqual(parsed["cfo_quarter_usd_m"],"-167.7")
        self.assertEqual(parsed["cfo_h1_usd_m"],"-352.0")
        self.assertEqual(parsed["cash_purchases_quarter_usd_m"],"510.6")
        self.assertEqual(parsed["cash_purchases_h1_usd_m"],"1054.5")

    def test_six_replayed_original_inputs_three_research_cohorts(self):
        result=build(*self.args)
        self.assertEqual(result["six_exact_original_source_tasks"],6)
        self.assertEqual(result["original_raw_sha_reverified"],6)
        self.assertEqual(result["issuer_source_numeric_claims_reproduced"],6)
        self.assertEqual(result["research_period_scores_reproduced_from_all_original_source_bytes"],3)
        self.assertIsNone(result["certified_11node_AICS"])
        self.assertFalse(result["trades_created"])

    def test_tampered_original_source_blocks_entire_three_cohort_replay(self):
        self.directory.joinpath("crwv_q1.gz").write_bytes(gzip.compress(
            b"<html>modified evidence does not contain CFO source facts</html>"))
        result=build(*self.args)
        self.assertEqual(result["issuer_source_numeric_claims_reproduced"],5)
        self.assertEqual(result["research_period_scores_reproduced_from_all_original_source_bytes"],0)

    def test_original_reporting_scope_mismatch_fails(self):
        changed=copy.deepcopy(self.args)
        changed[0]["sources"]["nbis_q2"]["cfo_quarter"]="-166.0"
        result=build(*changed)
        self.assertEqual(result["issuer_source_numeric_claims_reproduced"],5)
        self.assertEqual(result["research_period_scores_reproduced_from_all_original_source_bytes"],0)


if __name__=="__main__":
    unittest.main()
