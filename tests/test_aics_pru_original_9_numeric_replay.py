"""Synthetic source fixtures for PRU original 9-quarter replay, not market data."""
from __future__ import annotations
import copy
import gzip
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.aics_pru_original_9_numeric_replay import parse_original, replay


def document(period, numerator="610", denominator="58,685"):
    return (
        f"<html><body><h1>Notes to Financial Statements</h1>"
        f"<p>Loans on non-accrual status that did not have a related allowance "
        f"for credit losses were ${numerator} million and $442 million as of "
        f"{period} and December 31, 2025, respectively.</p>"
        f"<table><tr><th>September 30, 2026</th><th>December 31, 2025</th></tr>"
        f"<tr><td>Total commercial mortgage and other loans, net</td>"
        f"<td>$</td><td>{denominator}</td><td>$</td><td>56,195</td>"
        f"</tr></table></body></html>"
    ).encode()


class OriginalPrudentialNineChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)
        self.events=[]
        self.tasks=[]
        self.sources=[]
        for i in range(9):
            period=f"{2017+i}-09-30"
            acc=f"0001137774-26-{i+101:06d}"
            raw=document(f"September 30, {2017+i}")
            fn=self.p/f"source_{i}.gz"
            fn.write_bytes(gzip.compress(raw,mtime=0))
            sha=hashlib.sha256(raw).hexdigest()
            self.events.append({
                "quarter":f"{2017+i}-Q3","period_end":period,
                "cik":"1137774","accession":acc,
                "source_url":"https://www.sec.gov/Archives/edgar/data/mock",
                "nonaccrual_no_related_acl_usd_m":610,
                "commercial_mortgage_and_other_loans_net_usd_m":58685,
                "score_pct":"1.04",
            })
            self.tasks.append({
                "CIK":"1137774","accession":acc,
                "source_node":"Insurers",
                "workstream":"exact_SEC_source_bytes_and_numeric_replay",
                "exact_referenced_document_and_sgml_bytes_rehashed":True,
                "archive_origin":"targeted_exact_original",
            })
            self.sources.append({
                "CIK":"1137774","accession":acc,
                "original_doc_gzip_archived_path":str(fn),
                "original_doc_raw_sha256":sha,
            })
        for j in range(27):
            self.tasks.append({
                "CIK":str(1_000_000+j),
                "accession":f"0000000001-26-{j:06d}",
                "source_node":"Private Credit",
                "workstream":"exact_SEC_source_bytes_and_numeric_replay",
            })
        self.args=(
            {"schema":"aics-pru-insurers-noacl-nonaccrual-quarterly-original-filing-v1",
             "events":self.events},
            {"schema":"aics-priority100-evidence-workbench-v1",
             "priority_queue":self.tasks,"as_of":"2026-11-22",
             "full_11node_AICS":None,"independently_certified_nodes":0},
            {"schema":"aics-PIT100-original-scoring-accession-to-SEC-SGML-crosswalk-v1",
             "source_claims":[{} for _ in range(36)]},
            {"tasks":[]},
            {"targeted_source_results":self.sources},
        )

    def test_original_nine_source_values_and_precise_scores(self):
        result=replay(*self.args)
        self.assertEqual(result["original_source_hashes_reverified"],9)
        self.assertEqual(result["independently_reproduced_scoped_issuer_research_ratios"],9)
        self.assertEqual(result["missing_or_ambiguous_research_ratios"],0)
        self.assertTrue(all(x["state"]=="ORIGINAL_ISSUER_NUMERIC_REPLAY_VERIFIED_NOT_PIT"
                            for x in result["events"]))
        self.assertEqual(result["certified_AICS_nodes"],0)
        self.assertIsNone(result["production_AICS"])

    def test_wrong_numeric_claim_is_not_promoted(self):
        altered=copy.deepcopy(self.args)
        altered[0]["events"][0]["nonaccrual_no_related_acl_usd_m"]=611
        result=replay(*altered)
        self.assertEqual(result["independently_reproduced_scoped_issuer_research_ratios"],8)
        self.assertEqual(result["missing_or_ambiguous_research_ratios"],1)

    def test_corrupted_original_sha_fails_closed(self):
        src=Path(self.sources[0]["original_doc_gzip_archived_path"])
        src.write_bytes(gzip.compress(document("September 30, 2017",numerator="999")))
        result=replay(*self.args)
        self.assertEqual(result["original_source_hashes_reverified"],8)
        self.assertEqual(result["independently_reproduced_scoped_issuer_research_ratios"],8)

    def test_no_first_period_narrative_substitution(self):
        result=parse_original(document("September 30, 2026"),period_end="2025-09-30")
        self.assertIsNone(result["numerator_without_related_acl_usd_m"])
        self.assertIsNone(result["ratio_recomputed_pct_2dp"])

    def test_multiple_distinct_narrow_portfolio_rows_fail_closed(self):
        raw=document("September 30, 2026").replace(
            b"</table>",b"<tr><td>Total commercial mortgage and other loans, net"
            b"</td><td>12,345</td></tr></table>")
        result=parse_original(raw,period_end="2026-09-30")
        self.assertIsNone(result["denominator_narrow_commercial_mortgage_other_loans_net_usd_m"])
        self.assertIsNone(result["ratio_recomputed_pct_2dp"])


if __name__=="__main__":
    unittest.main()
