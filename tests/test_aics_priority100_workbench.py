"""Priority100 synthetic fixture tests; never used as historical market facts."""
from __future__ import annotations

import copy
import gzip
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.aics_priority100_workbench import build, verify_gzip_original
from scripts.aics_score_reproducibility_gate import WEIGHTS


class PriorityHundredTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raw = b"<SEC-DOCUMENT>TEST SOURCE ONLY " + b"x" * 250
        self.original = Path(self.tmp.name) / "original.gz"
        self.original.write_bytes(gzip.compress(raw, mtime=0))
        self.digest = hashlib.sha256(raw).hexdigest()
        self.args = self.fixture()

    def fixture(self):
        claims = []
        groups = []
        original = 0
        for prefix, node, ncohorts, docs_per in [
            ("INSURERS", "Insurers", 9, 1),
            ("PRIVATE_CREDIT", "Private Credit", 7, 3),
            ("NEOCLOUDS", "Neoclouds", 3, 2),
        ]:
            for j in range(ncohorts):
                cohort = f"{prefix}:TEST{j+1:02d}"
                groups.append({"cohort_id": cohort, "source_node": node,
                               "original_underlying_issuer_reports_needed": docs_per})
                for k in range(docs_per):
                    original += 1
                    claims.append({
                        "node": node, "cohort": cohort, "issuer": f"TEST{k+1}",
                        "CIK": str(1_000_000 + original),
                        "accession": f"0000001000-26-{original:06d}",
                        "source_original_doc_url": "https://www.sec.gov/Archives/edgar/data/test",
                        "same_exact_CIK_accession_header_clock_verified": False,
                        "same_exact_primary_document_url_matched_to_source": False,
                    })
        self.assertEqual((original, len(groups)), (36, 19))
        xw = {
            "schema": "aics-PIT100-original-scoring-accession-to-SEC-SGML-crosswalk-v1",
            "source_claims": claims, "source_cohorts": groups,
            "research_underlying_original_filing_references": 36,
        }
        targeted = {
            "schema": "aics-PIT100-targeted-original-scoring-accession-SGML-fill-v1",
            "original_research_filing_claims": 36,
            "targeted_source_results": [
                {
                    "CIK": x["CIK"], "accession": x["accession"],
                    "success_exact_original_scoring_document_and_sgml": True,
                    "original_doc_gzip_archived_path": str(self.original),
                    "original_header_gzip_archived_path": str(self.original),
                    "original_doc_raw_sha256": self.digest,
                    "original_header_raw_sha256": self.digest,
                } for x in claims
            ],
            "trades_created": False,
        }
        reports = {
            "schema": "aics-PIT100-distinct-original-SEC-primary-report-downloads-v1",
            "tasks": [{"CIK": str(8_000_000+i),
                       "accession": f"0000008000-26-{i:06d}"} for i in range(100)],
        }
        headers = {
            "schema": "aics-PIT100-first-original-SEC-SGML-timezone-clocks-audit-v1",
            "source_headers": [
                {"CIK": str(8_000_000+i),
                 "accession": f"0000008000-26-{i:06d}"} for i in range(100)],
        }
        months = []
        diags = []
        listed = ["Insurers", "Private Credit"]
        for i in range(24):
            y = 2024 + (10+i)//12
            m = (10+i)%12+1
            month = f"{y:04d}-{m:02d}"
            cutoff = f"{month}-28"
            months.append({
                "month": month, "market_cutoff_date": cutoff,
                "market_source_nodes_research_only": len(listed),
                "calendar_source_nodes_research_only": len(listed),
                "market_missing_nodes": sorted(set(WEIGHTS)-set(listed)),
                "calendar_missing_nodes": sorted(set(WEIGHTS)-set(listed)),
                "market_known_weight_research_only": 275,
                "calendar_known_weight_research_only": 275,
                "market_partial_weighted_points_NOT_AICS": "50.00",
                "sp500_close_retrieved_expost": "5000.00",
                "full_11node_AICS": None, "AICS_SP500_spread": None,
            })
            diags.append({"month": month, "market_cutoff_date": cutoff})
        reconciled = {
            "schema": "aics-pit100-two-independent-24month-replays-reconciled-v1",
            "monthly_aligned_research_panel": months,
            "independent_replay_methods_compared": 2,
            "month_node_disagreements_remaining": 0,
            "full_11node_AICS": None, "as_of": "2026-11-22",
        }
        lead = {
            "schema": "aics-PIT100-24m-EXPOST-fixed-first-month-cohort-leadlag-v1",
            "monthly_diagnostics": diags,
            "descriptive_correlation_risk_vs_following_month_SP500_return_pearson": -0.135,
            "SP500_following_month_returns_used_only_as_targets": True,
            "cohort_selected_in_2024_11_then_preserved_without_future_selection": True,
            "independent_24m_out_of_sample_forecast_labels": 0,
            "2000_2008_crisis_onset_lead_time_certified": False,
            "production_trades_created": False,
        }
        status = {
            "independently_certified_nodes": 0, "index_aics": None,
            "node_progress": [
                {"node": n, "weight": w, "independently_certified": False,
                 "node_stress_score": None, "completed_milestones": 2}
                for n, w in WEIGHTS.items()
            ],
        }
        return xw, targeted, reports, headers, reconciled, lead, status

    def test_100_distinct_prioritized_evidence_tasks_no_false_certification(self):
        out = build(*self.args)
        self.assertEqual(out["deterministic_specialized_audit_tasks_executed"], 100)
        self.assertEqual(out["exact_referenced_SEC_source_and_SGML_bytes_currently_verified"], 36)
        self.assertEqual(len({x["task_id"] for x in out["priority_queue"]}), 100)
        self.assertEqual([out[k] for k in (
            "priority_0_original_document_tasks", "priority_0_original_event_cohort_tasks",
            "priority_1_monthly_source_tasks", "priority_1_node_score_tasks",
            "priority_2_safety_control_tasks")], [36, 19, 24, 11, 10])
        self.assertIsNone(out["full_11node_AICS"])
        self.assertEqual(out["original_accounting_values_independently_recomputed"], 0)
        self.assertEqual(out["independently_certified_nodes"], 0)
        self.assertFalse(out["trades_created"])

    def test_corrupted_original_is_blocked_not_falsely_verified(self):
        raw = b"<SEC-DOCUMENT>CHANGED " + b"x" * 250
        self.original.write_bytes(gzip.compress(raw, mtime=0))
        self.assertFalse(verify_gzip_original(self.original, self.digest))
        out = build(*self.args)
        self.assertEqual(out["exact_referenced_SEC_source_and_SGML_bytes_currently_verified"], 0)
        self.assertTrue(all(x["state"] == "BLOCKED_ORIGINAL_SOURCE"
                            for x in out["priority_queue"][:36]))

    def test_duplicate_accession_fails(self):
        wrong = copy.deepcopy(self.args)
        wrong[0]["source_claims"][1]["accession"] = wrong[0]["source_claims"][0]["accession"]
        wrong[0]["source_claims"][1]["CIK"] = wrong[0]["source_claims"][0]["CIK"]
        with self.assertRaises(ValueError):
            build(*wrong)

    def test_synthetic_prediction_promoted_fails(self):
        wrong = copy.deepcopy(self.args)
        wrong[5]["independent_24m_out_of_sample_forecast_labels"] = 24
        with self.assertRaises(ValueError):
            build(*wrong)

    def test_real_reconciler_count_schema_rejects_list_as_count(self):
        wrong = copy.deepcopy(self.args)
        wrong[4]["monthly_aligned_research_panel"][0]["market_source_nodes_research_only"] = [
            "Insurers", "Private Credit"
        ]
        with self.assertRaises(ValueError):
            build(*wrong)

    def test_month_missing_node_partition_rejects_duplicate(self):
        wrong = copy.deepcopy(self.args)
        wrong[4]["monthly_aligned_research_panel"][0]["market_missing_nodes"].append("AI Equities")
        with self.assertRaises(ValueError):
            build(*wrong)

    def test_reconciled_count_mismatch_rejects(self):
        wrong = copy.deepcopy(self.args)
        wrong[4]["monthly_aligned_research_panel"][0]["market_source_nodes_research_only"] = 11
        with self.assertRaises(ValueError):
            build(*wrong)

    def test_reconstructed_month_weight_tamper_fails(self):
        wrong = copy.deepcopy(self.args)
        wrong[4]["monthly_aligned_research_panel"][0]["market_known_weight_research_only"] = 1050
        with self.assertRaises(ValueError):
            build(*wrong)


if __name__ == "__main__":
    unittest.main()
