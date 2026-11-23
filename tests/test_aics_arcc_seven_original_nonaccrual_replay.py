"""Synthetic text fixtures for source-parser tests; no invented market history."""
from __future__ import annotations

import copy
import gzip
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.aics_arcc_seven_original_nonaccrual_replay import build,extract_pair,PERIODS


class ARCCSevenPrimarySourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.rows=[]
        self.tasks=[]
        self.archives=[]
        for i,quarter in enumerate(PERIODS):
            acc=f"0001287750-26-{i+101:06d}"
            raw=(
                "<html><body><p>As of the original reporting period, "
                "loans on non-accrual status represented 1.3% of the total "
                "investments at amortized cost (or 0.6% at fair value) "
                "and 1.5% at amortized cost (or 0.7% at fair value), respectively."
                "</p></body></html>"
            ).encode()
            f=self.root/f"{i}.doc.gz"
            f.write_bytes(gzip.compress(raw,mtime=0))
            sha=hashlib.sha256(raw).hexdigest()
            self.rows.append({
                "issuer":"ARCC", "quarter":quarter, "cik":"1287750",
                "nonaccrual_amortized_cost_pct":"1.3",
                "nonaccrual_fair_value_pct":"0.6",
                "original_numeric_source_url":(
                    "https://www.sec.gov/Archives/edgar/data/1287750/"
                    f"{acc.replace('-', '')}/arcc-original.htm"
                ),
            })
            self.tasks.append({
                "CIK":"1287750","accession":acc,
                "workstream":"exact_SEC_source_bytes_and_numeric_replay",
                "cohort":f"PRIVATE_CREDIT:{quarter}","issuer":"ARCC",
                "archive_origin":"targeted_exact_original",
                "exact_referenced_document_and_sgml_bytes_rehashed":True,
            })
            self.archives.append({
                "CIK":"1287750","accession":acc,
                "original_doc_gzip_archived_path":str(f),
                "original_doc_raw_sha256":sha,
            })
        for i in range(17):
            self.rows.append({"issuer":"BXSL","quarter":f"TEST-{i}"})
        for i in range(93):
            self.tasks.append({"workstream":"forecast_governance_negative_controls"})
        self.arguments=(
            {
                "schema":"aics-private-credit-2024q2-2026q1-8quarter-original-sec-cost-breadth-expost-v1",
                "weight":150,"weight_total":1050,
                "original_issuer_quarter_observations":self.rows,
            },
            {
                "schema":"aics-priority100-evidence-workbench-v1",
                "full_11node_AICS":None,"independently_certified_nodes":0,
                "as_of":"2026-11-22","priority_queue":self.tasks,
            },
            {"schema":"aics-PIT100-distinct-original-SEC-primary-report-downloads-v1",
             "tasks":[]},
            {"schema":"aics-PIT100-targeted-original-scoring-accession-SGML-fill-v1",
             "targeted_source_results":self.archives},
        )

    def test_seven_distinct_original_cost_fair_pairs_without_pit_promotion(self):
        result=build(*self.arguments)
        self.assertEqual(result["original_ARCC_quarter_tasks_executed"],7)
        self.assertEqual(result["exact_original_hashes_reverified"],7)
        self.assertEqual(result["original_source_cost_and_fair_pairs_reproduced"],7)
        self.assertEqual(result["certified_AICS_nodes"],0)
        self.assertIsNone(result["production_AICS"])

    def test_ambiguous_original_percentages_blocked(self):
        raw=b"<p>Loans on non-accrual status represented 2.0% of the total investments at amortized cost (or 1.2% at fair value).</p>"
        ambiguous=extract_pair(raw+b"<p>Loans on non-accrual status represented 1.3% of the total investments at amortized cost (or 0.6% at fair value).</p>")
        self.assertIsNone(ambiguous["amortized_cost_nonaccrual_pct"])
        self.assertEqual(ambiguous["different_candidate_pairs"],2)

    def test_wrong_cost_or_fair_value_blocks_research_claim(self):
        data=copy.deepcopy(self.arguments)
        data[0]["original_issuer_quarter_observations"][0]["nonaccrual_fair_value_pct"]="2.1"
        result=build(*data)
        self.assertEqual(result["original_source_cost_and_fair_pairs_reproduced"],6)
        self.assertEqual(result["blocked_original_numeric_pairs"],1)

    def test_tampered_original_doc_hash_blocks_instead_of_filling(self):
        self.root.joinpath("0.doc.gz").write_bytes(gzip.compress(b"<p>wrong payload</p>"))
        result=build(*self.arguments)
        self.assertEqual(result["exact_original_hashes_reverified"],6)
        self.assertEqual(result["original_source_cost_and_fair_pairs_reproduced"],6)

    def test_mismatched_original_accession_or_source_document_rejected(self):
        data=copy.deepcopy(self.arguments)
        data[0]["original_issuer_quarter_observations"][0]["original_numeric_source_url"]=(
            data[0]["original_issuer_quarter_observations"][0]["original_numeric_source_url"]
            .replace("1287750","9999999")
        )
        with self.assertRaises(ValueError):
            build(*data)


if __name__=="__main__":
    unittest.main()
