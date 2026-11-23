"""Tests derive exclusively from pinned real-source SEC receipts; no market fixtures."""
import datetime as dt
import json
import unittest
from pathlib import Path

from scripts.aics_private_credit_cross_issuer_research import (
    ARCC_SOURCE, OBDC_SOURCE, ComparisonError,
)
from scripts.aics_private_credit_three_bdc_asof import BXSL, build


def sources():
    return [
        json.loads(Path(p).read_text(encoding="utf-8"))
        for p in (ARCC_SOURCE, OBDC_SOURCE, BXSL)
    ]


class TestThreeOriginalBDCResearchPanels(unittest.TestCase):
    def test_eighteen_real_observed_values_three_issuers(self):
        out = build(*sources(), dt.date(2026, 11, 19))
        self.assertEqual(out["source_filing_periods_across_issuers"], 9)
        self.assertEqual(out["genuine_source_nonaccrual_values_across_issuers"], 18)
        self.assertEqual(out["source_values_visible_by_asof"], 18)
        self.assertEqual(out["source_values_visible_per_issuer"],
                         {"ARCC": 10, "OBDC": 6, "BXSL": 2})
        self.assertEqual(len(out["2026Q3_nonaccrual_source_matrix"]), 3)
        vals = {r["issuer"]: (r["nonaccrual_cost_pct"], r["nonaccrual_fair_pct"])
                for r in out["2026Q3_nonaccrual_source_matrix"]}
        self.assertEqual(vals, {
            "ARCC": ("2.4", "1.4"), "OBDC": ("2.9", "0.8"), "BXSL": ("2.8", "2.1")
        })
        self.assertFalse(out["issuer_percentages_aggregated"])
        self.assertFalse(out["independent_contemporaneous_feed_PIT"])
        self.assertFalse(out["untouched_24_month_predictive_oos"])
        self.assertEqual(out["synthetic_observations_created"], 0)
        self.assertIsNone(out["private_credit_node_score"])
        self.assertIsNone(out["aics_index"])
        self.assertEqual(out["promotion"], "BLOCKED")

    def test_exact_sec_filing_plus_fourteen_threshold(self):
        a = sources()
        self.assertEqual(build(*a, dt.date(2026, 11, 17))["source_values_visible_by_asof"], 14)
        self.assertEqual(build(*a, dt.date(2026, 11, 18))["source_values_visible_by_asof"], 18)
        self.assertEqual(build(*a, dt.date(2026, 11, 17))["source_values_visible_per_issuer"]["BXSL"], 0)

    def test_past_2024_comparative_not_backdated(self):
        self.assertEqual(build(*sources(), dt.date(2024, 12, 31))["source_values_visible_by_asof"], 0)

    def test_bxsl_cost_fair_change_invalidates_source(self):
        inputs = sources()
        inputs[2]["nonaccrual_amortized_cost_pct"] = "2.1"
        with self.assertRaises(ComparisonError):
            build(*inputs, dt.date(2026, 11, 19))

    def test_bxsl_source_sha_invalid_fails(self):
        inputs = sources()
        inputs[2]["source_exhibit_html_sha256"] = "missing"
        with self.assertRaises(ComparisonError):
            build(*inputs, dt.date(2026, 11, 19))

    def test_forged_bxsl_model_stress_score_fails(self):
        inputs = sources()
        inputs[2]["node_score"] = 70
        with self.assertRaises(ComparisonError):
            build(*inputs, dt.date(2026, 11, 19))

    def test_refuses_backdated_bxsl_filing(self):
        inputs = sources()
        inputs[2]["source_available_at"] = "2026-09-30"
        with self.assertRaises(ComparisonError):
            build(*inputs, dt.date(2026, 11, 19))


if __name__ == "__main__":
    unittest.main()
