"""Tests of ARCC SEC Q4 original chronology correction using *fixtures only*.

Historical market data must always come from real original ZIP bytes in CI.
"""
import copy
import tempfile
import unittest
from pathlib import Path
from scripts.aics_reconcile_arcc_q4_source_pit import (
    Q4_ZIP_SHA256, ReconciliationError, build, derive, original_q4_report,
)


def fixture():
    q4 = {
        "schema_version": "aics-arcc-q4-2025-sec-exhibit-original-v1",
        "filing_accession": "0001287750-26-000004",
        "filing_date": "2026-02-04", "available_at": "2026-02-18",
        "source_values_verified_against_original_sec": True,
        "filed_at_plus_14_date_gate_passed": True,
        "independently_attested_contemporaneous_publication": False,
        "index_aics": None, "promotion": "BLOCKED",
        "nonaccrual_amortized_cost_pct": "1.8",
        "nonaccrual_fair_value_pct": "1.2",
        "prior_dec2024_cost_pct": "1.7",
        "prior_dec2024_fair_value_pct": "1.0",
        "exhibit_url": "https://www.sec.gov/Archives/edgar/data/1287750/000128775026000004/arccq4-2025exhibit991.htm",
        "raw_exhibit_sha256": "a" * 64,
    }
    prev = {
        "schema_version": "aics-arcc-sec-primary-nonaccrual-independent-raw-verification-v1",
        "verified_sec_exhibit_originals": 3,
        "original_source_html_rehashed": 4,
        "independently_verified_source_transcription_values": 8,
        "historical_24mo_PIT_complete": False,
        "index_aics": None,
        "promotion": "BLOCKED",
        "source_values": [
            {"period_end": "2025-12-31",
             "nonaccrual_amortized_cost_percent": "1.8",
             "nonaccrual_fair_value_percent": "1.2",
             "earliest_verified_sec_available_at": "2026-05-12",
             "earlier_issuer_release_original_bytes_confirmed": False},
        ],
    }
    for period, filed, available, cost, fair in (
        ("2026-03-31", "2026-04-28", "2026-05-12", "2.1", "1.2"),
        ("2026-06-30", "2026-07-29", "2026-08-12", "2.4", "1.4"),
        ("2026-09-30", "2026-10-27", "2026-11-10", "2.4", "1.4"),
    ):
        prev["source_values"].append({
            "period_end": period, "SEC_filed_at": filed,
            "SEC_available_at": available,
            "nonaccrual_amortized_cost_percent": cost,
            "nonaccrual_fair_value_percent": fair,
            "SEC_exhibit_url": "https://www.sec.gov/Archives/edgar/data/1287750/example.html",
            "SEC_source_sha256": "f" * 64,
        })
    return q4, prev


class TestARCCQ4CorrectedAsOf(unittest.TestCase):
    def test_five_source_periods_are_visible_at_exact_original_date_plus14(self):
        q4, old = fixture()
        report = build(q4, old)
        self.assertEqual(report["distinct_observation_periods"], 5)
        self.assertEqual(report["source_verified_nonaccrual_values"], 10)
        self.assertEqual(report["new_verified_sec_8k_available_at"], "2026-02-18")
        self.assertEqual(report["2025_december_to_2026_september_cost_change_pp"], "0.6")
        self.assertEqual(report["2025_december_to_2026_september_fair_value_change_pp"], "0.2")
        self.assertFalse(report["retrospective_2024_value_visible_in_2024"])
        self.assertEqual(report["synthetic_rows_created"], 0)
        self.assertFalse(report["historical_24m_pit_attested"])
        self.assertFalse(report["independent_24m_oos"])
        self.assertIsNone(report["private_credit_node_score"])
        self.assertIsNone(report["index_aics"])
        self.assertEqual(report["promotion"], "BLOCKED")

    def test_release_eve_does_not_leak_december_results(self):
        report = build(*fixture())
        values = {s["evaluation_as_of"]: s["visible_source_verified_values"]
                  for s in report["historical_as_of_scenarios"]}
        self.assertEqual(values, {
            "2026-02-17": 0, "2026-02-18": 4,
            "2026-05-11": 4, "2026-05-12": 6,
            "2026-08-11": 6, "2026-08-12": 8,
            "2026-11-09": 8, "2026-11-10": 10,
            "2026-11-18": 10,
        })

    def test_2024_comparative_not_retroactively_published_in_2024(self):
        report = build(*fixture())
        two = report["source_verified_disclosed_periods"][:2]
        self.assertEqual(two[0]["period_end"], "2024-12-31")
        self.assertEqual(two[0]["aics_eligible_date_after_sec_14d"], "2026-02-18")
        self.assertEqual(two[0]["evidence_kind"],
                         "RETROSPECTIVE_PRIOR_YEAR_COMPARATIVE_IN_2025Q4_8K")
        self.assertEqual(two[1]["period_end"], "2025-12-31")
        self.assertFalse(two[0]["independent_historical_publication_time_attested"])
        self.assertFalse(two[0]["model_eligible"])

    def test_altered_q4_original_value_disagrees_with_three_prior_sec_exhibits(self):
        q4, old = fixture()
        q4["nonaccrual_amortized_cost_pct"] = "9.1"
        with self.assertRaises(ReconciliationError):
            build(q4, old)

    def test_original_q4_file_or_date_tamper_blocks(self):
        for field, val in (("filing_date", "2026-02-03"), ("available_at", "2026-02-17"),
                           ("filing_accession", "0001287750-26-000003"),
                           ("independently_attested_contemporaneous_publication", True)):
            with self.subTest(field=field):
                q4, old = fixture()
                q4[field] = val
                with self.assertRaises(ReconciliationError):
                    build(q4, old)

    def test_prior_sec_release_gate_cannot_be_shortened(self):
        q4, old = fixture()
        old["source_values"][2]["SEC_available_at"] = "2026-08-11"
        with self.assertRaises(ReconciliationError):
            build(q4, old)

    def test_older_receiver_pit_flags_do_not_mint_24_month_certification(self):
        q4, old = fixture()
        old["historical_24mo_PIT_complete"] = True
        with self.assertRaises(ReconciliationError):
            build(q4, old)
        q4, old = fixture()
        q4["index_aics"] = 470
        with self.assertRaises(ReconciliationError):
            build(q4, old)

    def test_original_source_zip_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises((FileNotFoundError, OSError)):
                original_q4_report(Path(tmp) / "no_original.zip")
            self.assertEqual(len(Q4_ZIP_SHA256), 64)


if __name__ == "__main__":
    unittest.main()
