"""Synthetic parser fixtures; not a source of market observations."""
from __future__ import annotations

import copy
import gzip
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.aics_bxsl_obdc_fourteen_original_nonaccrual_replay import (
    extract_cost,build,PERIODS
)


def html(issuer,*,bad_cost=False):
    if issuer=="BXSL":
        value="2.7" if bad_cost else "1.8"
        return (f"<html><body>Percentage of assets on non-accrual, "
                f"at amortized cost (4)(5) {value} % 0.3 % "
                f"Original statement disclosure fixture for exact-source archival verification."
                f"</body></html>").encode()
    amount="1,900" if bad_cost else "1,800"
    return (
        "<html><body>The table below presents the amortized cost and fair value "
        "of our performing and non-accrual investments as of the following periods: "
        "As of June 30, 2025 As of December 31, 2024 "
        "($ in thousands) Amortized Cost Percentage Fair value Percentage "
        "Performing $ 98,200 98.2 % $ 97,000 99.0 % "
        f"Non-accrual {amount} 1.8 180 0.1 200 0.2 "
        "Total $ 100,000 100.0 % $ 97,180 100.0 %"
        "</body></html>"
    ).encode()


class FourteenOriginalBDCTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        directory=Path(self.tmp.name)
        self.rows=[]
        self.tasks=[]
        self.archives=[]
        for issuer in ("BXSL","OBDC"):
            cik="1736035" if issuer=="BXSL" else "1655888"
            for i,quarter in enumerate(PERIODS):
                acc=f"0000000000-26-{i+1+(0 if issuer=='BXSL' else 8):06d}"
                raw=html(issuer)
                stored=directory/f"{issuer}_{i}.gz"
                stored.write_bytes(gzip.compress(raw,mtime=0))
                self.rows.append({
                    "issuer":issuer,"cik":cik,"quarter":quarter,
                    "nonaccrual_amortized_cost_pct":"1.8",
                    "original_numeric_source_url":(
                        f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                        f"{acc.replace('-', '')}/{issuer.lower()}-original.htm"
                    ),
                })
                self.tasks.append({
                    "workstream":"exact_SEC_source_bytes_and_numeric_replay",
                    "CIK":cik,"accession":acc,"issuer":issuer,
                    "cohort":f"PRIVATE_CREDIT:{quarter}",
                    "archive_origin":"targeted_exact_original",
                    "exact_referenced_document_and_sgml_bytes_rehashed":True,
                })
                self.archives.append({
                    "CIK":cik,"accession":acc,
                    "original_doc_gzip_archived_path":str(stored),
                    "original_doc_raw_sha256":hashlib.sha256(raw).hexdigest(),
                })
        self.rows += [{"issuer":"ARCC","quarter":f"TEST-{i}"} for i in range(10)]
        self.tasks += [{"workstream":"forecast_governance_negative_controls"} for _ in range(86)]
        self.data=(
            {"schema":"aics-private-credit-2024q2-2026q1-8quarter-original-sec-cost-breadth-expost-v1",
             "weight":150,"weight_total":1050,
             "original_issuer_quarter_observations":self.rows},
            {"schema":"aics-priority100-evidence-workbench-v1",
             "as_of":"2026-11-22","full_11node_AICS":None,
             "independently_certified_nodes":0,"priority_queue":self.tasks},
            {"schema":"aics-PIT100-distinct-original-SEC-primary-report-downloads-v1","tasks":[]},
            {"schema":"aics-PIT100-targeted-original-scoring-accession-SGML-fill-v1",
             "targeted_source_results":self.archives},
        )

    def test_bxsl_table_extracts_first_cost_not_comparative_column(self):
        parsed=extract_cost(html("BXSL"),"BXSL")
        self.assertTrue(parsed["source_values_unique"])
        self.assertEqual(parsed["original_first_period_amortized_cost_nonaccrual_pct"],"1.8")

    def test_obdc_reconciles_cost_amounts_not_fair_value(self):
        parsed=extract_cost(html("OBDC"),"OBDC")
        self.assertEqual(parsed["original_first_period_amortized_cost_nonaccrual_pct"],"1.8")
        self.assertTrue(parsed["reported_percent_matches_independent_amount_fraction"])
        self.assertEqual(parsed["original_source_numeric_dollars_thousands"]["nonaccrual_amortized_cost"],1800)

    def test_all_14_original_tasks_replayed_with_no_pit_promotion(self):
        report=build(*self.data)
        self.assertEqual(report["original_BXSL_OBDC_issuer_periods_attempted"],14)
        self.assertEqual(report["original_file_sha256_reverified"],14)
        self.assertEqual(report["original_nonaccrual_cost_percentages_reproduced"],14)
        self.assertIsNone(report["full_11node_AICS"])
        self.assertEqual(report["certified_AICS_nodes"],0)

    def test_invalid_original_cost_percentage_detected(self):
        altered=copy.deepcopy(self.data)
        altered[0]["original_issuer_quarter_observations"][0]["nonaccrual_amortized_cost_pct"]="4.0"
        report=build(*altered)
        self.assertEqual(report["original_nonaccrual_cost_percentages_reproduced"],13)
        self.assertEqual(report["blocked_original_cost_percentages"],1)

    def test_mismatched_source_ratio_blocks(self):
        parsed=extract_cost(html("OBDC",bad_cost=True),"OBDC")
        self.assertFalse(parsed["reported_percent_matches_independent_amount_fraction"])

    def test_unexpected_source_issuer_rejected(self):
        with self.assertRaises(ValueError):
            extract_cost(html("BXSL"),"ARCC")


if __name__=="__main__":
    unittest.main()
