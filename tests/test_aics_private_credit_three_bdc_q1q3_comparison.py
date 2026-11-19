"""Tests compare only real permanent SEC source receipts. No fake market series."""
import copy
import datetime as dt
import json
import unittest
from decimal import Decimal
from pathlib import Path

from scripts.aics_private_credit_three_bdc_q1q3_comparison import (
    build, ComparisonError, ARCC_SOURCE, OBDC_SOURCE, BXSL, Q1Q2,
)


def receipts():
    return [json.loads(Path(x).read_text(encoding="utf-8"))
            for x in (ARCC_SOURCE, OBDC_SOURCE, BXSL, Q1Q2)]


class TestThreeBDCGenuineQuarterPanel(unittest.TestCase):
    def test_eleven_issuer_periods_twenty_two_source_values(self):
        x = build(*receipts(), dt.date(2026, 11, 19))
        self.assertEqual(x["issuer_universe"], ["ARCC", "BXSL", "OBDC"])
        self.assertEqual(x["original_issuer_periods_all_sources"], 11)
        self.assertEqual(x["original_separately_reported_numeric_values_all_sources"], 22)
        self.assertEqual(x["asof_visible_quarter_values"], 18)
        self.assertEqual(x["three_way_comparison_quarters_available"], 3)
        self.assertEqual(len(x["three_quarter_issuer_panel"]), 3)
        self.assertEqual([r["visible_issuer_count"] for r in x["three_quarter_issuer_panel"]],
                         [3,3,3])
        self.assertEqual(x["cross_issuer_rate_averages"], None)
        self.assertEqual(x["issuer_exposure_weights"], None)
        self.assertEqual(x["synthetic_rows"], 0)
        self.assertIsNone(x["private_credit_node_stress_score"])
        self.assertIsNone(x["index_aics"])
        self.assertEqual(x["promotion"], "BLOCKED")

    def test_same_quarter_original_rates_each_issuer_no_pooling(self):
        x = build(*receipts(), dt.date(2026, 11, 19))
        target = {
            "2026-03-31": {"ARCC": ("2.1","1.2"), "OBDC": ("2.0","1.0"), "BXSL": ("4.7","3.1")},
            "2026-06-30": {"ARCC": ("2.4","1.4"), "OBDC": ("2.8","0.8"), "BXSL": ("3.6","1.8")},
            "2026-09-30": {"ARCC": ("2.4","1.4"), "OBDC": ("2.9","0.8"), "BXSL": ("2.8","2.1")},
        }
        for quarter in x["three_quarter_issuer_panel"]:
            observed = {d["issuer"]: (d["cost_pct"],d["fair_pct"])
                        for d in quarter["source_observations"]}
            self.assertEqual(observed,target[quarter["quarter_end"]])
            self.assertIsNone(quarter["issuer_averaged_nonaccrual"])
            self.assertIsNone(quarter["posthoc_market_weighted_score"])

    def test_bxsl_first_two_quarters_exact_sec_plus_fourteen_cutoff(self):
        checks = [
            ("2026-05-20", 0, [2,0,0]),
            ("2026-05-21", 1, [3,0,0]),
            ("2026-08-19", 1, [3,2,0]),
            ("2026-08-20", 2, [3,3,0]),
            ("2026-11-17", 2, [3,3,1]),
            ("2026-11-18", 3, [3,3,3]),
        ]
        for date, ready, counts in checks:
            with self.subTest(date=date):
                x = build(*receipts(), dt.date.fromisoformat(date))
                self.assertEqual(x["three_way_comparison_quarters_available"], ready)
                self.assertEqual([r["visible_issuer_count"] for r in x["three_quarter_issuer_panel"]], counts)

    def test_before_first_original_sources_no_quarter_available(self):
        x = build(*receipts(), dt.date(2024,12,31))
        self.assertEqual(x["asof_visible_quarter_values"],0)
        self.assertEqual(x["three_way_comparison_quarters_available"],0)
        self.assertTrue(all(not r["source_observations"] for r in x["three_quarter_issuer_panel"]))

    def test_source_q1_numeric_tampering_blocks(self):
        vals = receipts()
        vals[3]["source_periods"][0]["cost_pct"]="9.9"
        with self.assertRaises(ComparisonError):
            build(*vals,dt.date(2026,11,19))

    def test_source_q2_original_html_hash_tampering_blocks(self):
        vals = receipts()
        vals[3]["source_periods"][1]["original_file_sha256"]["exhibit"]="x"
        with self.assertRaises(ComparisonError):
            build(*vals,dt.date(2026,11,19))

    def test_valid_looking_q1_exhibit_digest_swap_blocks(self):
        vals = receipts()
        vals[3]["source_periods"][0]["original_file_sha256"]["exhibit"] = "0" * 64
        with self.assertRaisesRegex(ComparisonError, "pinned"):
            build(*vals, dt.date(2026, 11, 19))

    def test_q2_document_length_swap_blocks(self):
        vals = receipts()
        vals[3]["source_periods"][1]["original_file_bytes"]["exhibit"] += 1
        with self.assertRaisesRegex(ComparisonError, "pinned"):
            build(*vals, dt.date(2026, 11, 19))

    def test_q1_sec_exhibit_url_substitution_blocks(self):
        vals = receipts()
        vals[3]["source_periods"][0]["exhibit_url"] = (
            "https://www.sec.gov/Archives/edgar/data/1736035/"
            "000121390026000000/another-exhibit.htm"
        )
        with self.assertRaisesRegex(ComparisonError, "pinned"):
            build(*vals, dt.date(2026, 11, 19))

    def test_valid_looking_source_zip_digest_swap_blocks(self):
        vals = receipts()
        vals[3]["source_archive_zip_sha256"] = "1" * 64
        with self.assertRaisesRegex(ComparisonError, "unsafe"):
            build(*vals, dt.date(2026, 11, 19))

    def test_sec_embargo_tampering_blocks(self):
        vals = receipts()
        vals[3]["source_periods"][1]["available_at"]="2026-08-06"
        with self.assertRaises(ComparisonError):
            build(*vals,dt.date(2026,11,19))

    def test_independent_pit_claim_without_original_archive_blocks(self):
        vals = receipts()
        vals[3]["live_historical_release_feed_independently_attested"]=True
        with self.assertRaises(ComparisonError):
            build(*vals,dt.date(2026,11,19))

    def test_forged_index_or_node_score_blocks(self):
        vals=receipts()
        vals[3]["private_credit_node_stress_score"]=64
        with self.assertRaises(ComparisonError):
            build(*vals,dt.date(2026,11,19))
        vals=receipts()
        vals[2]["node_score"]=73
        with self.assertRaises(ComparisonError):
            build(*vals,dt.date(2026,11,19))


if __name__ == "__main__":
    unittest.main()
