"""Tests operate on genuine pinned issuer receipt metadata; never forge financial series."""
import copy
import datetime as dt
import json
import unittest
from pathlib import Path
from decimal import Decimal

from scripts.aics_private_credit_cross_issuer_research import (
    ARCC_SOURCE, OBDC_SOURCE, ComparisonError, compare
)


def original_receipts():
    return (
        json.loads(Path(ARCC_SOURCE).read_text(encoding="utf-8")),
        json.loads(Path(OBDC_SOURCE).read_text(encoding="utf-8")),
    )


class TestTwoRealBDCSourcePanels(unittest.TestCase):
    def test_true_originals_two_issuers_sixteen_source_values(self):
        a, b = original_receipts()
        out = compare(a, b, dt.date(2026, 11, 19))
        self.assertEqual(out["verified_original_sec_issuers"], ["ARCC", "OBDC"])
        self.assertEqual(out["total_source_periods_original"], 8)
        self.assertEqual(out["asof_visible_original_values"], 16)
        self.assertEqual(out["asof_visible_by_issuer"], {"ARCC": 10, "OBDC": 6})
        self.assertEqual(len(out["same_quarter_comparisons"]), 3)
        self.assertEqual(out["latest_comparable_period"], "2026-09-30")
        q3 = out["latest_comparison"]
        self.assertEqual(Decimal(q3["ARCC_minus_OBDC_cost_percentage_points"]),
                         Decimal("-0.5"))
        self.assertEqual(Decimal(q3["ARCC_minus_OBDC_fair_percentage_points"]),
                         Decimal("0.6"))
        self.assertFalse(out["cross_issuer_aggregation_or_average_performed"])
        self.assertFalse(out["market_sector_representativeness_verified"])
        self.assertFalse(out["historical_pit_release_attested"])
        self.assertEqual(out["synthetic_observations_created"], 0)
        self.assertIsNone(out["private_credit_node_score"])
        self.assertIsNone(out["index_aics"])
        self.assertEqual(out["promotion"], "BLOCKED")

    def test_frozen_filing_gates_prevent_quarter_lookahead(self):
        a, b = original_receipts()
        thresholds = [
            ("2025-12-31", 0),
            ("2026-02-17", 0),
            ("2026-02-18", 4),
            ("2026-05-11", 4),
            ("2026-05-12", 6),
            ("2026-05-19", 6),
            ("2026-05-20", 8),
            ("2026-08-11", 8),
            ("2026-08-12", 10),
            ("2026-08-18", 10),
            ("2026-08-19", 12),
            ("2026-11-09", 12),
            ("2026-11-10", 14),
            ("2026-11-17", 14),
            ("2026-11-18", 16),
        ]
        for date, n in thresholds:
            with self.subTest(date=date):
                report = compare(a, b, dt.date.fromisoformat(date))
                self.assertEqual(report["asof_visible_original_values"], n)

    def test_refuse_2024_comparative_backdating(self):
        a, b = original_receipts()
        a["observed_source_periods"][0]["available_at"] = "2024-12-31"
        with self.assertRaises(ComparisonError):
            compare(a, b, dt.date(2026, 11, 19))

    def test_refuse_future_source_date_backfill(self):
        a, b = original_receipts()
        b["original_periods"][2]["available_at"] = "2026-11-04"
        with self.assertRaises(ComparisonError):
            compare(a, b, dt.date(2026, 11, 19))

    def test_refuse_forged_private_credit_stress_score(self):
        a, b = original_receipts()
        a["private_credit_node_stress_score"] = 74
        with self.assertRaises(ComparisonError):
            compare(a, b, dt.date(2026, 11, 19))

    def test_source_original_hash_mismatch_rejected(self):
        a, b = original_receipts()
        b["original_periods"][1]["exhibit_sha256"] = "missing"
        with self.assertRaises(ComparisonError):
            compare(a, b, dt.date(2026, 11, 19))

    def test_source_value_nan_rejected(self):
        a, b = original_receipts()
        b["original_periods"][1]["cost_pct"] = "NaN"
        with self.assertRaises(ComparisonError):
            compare(a, b, dt.date(2026, 11, 19))

    def test_unmatched_denominators_not_aggregated(self):
        a, b = original_receipts()
        p = compare(a, b, dt.date(2026, 11, 19))
        self.assertTrue(all({"ARCC_cost_pct", "ARCC_fair_pct", "OBDC_cost_pct", "OBDC_fair_pct"} <= set(row)
                            for row in p["same_quarter_comparisons"]))
        self.assertNotIn("combined_private_credit_nonaccrual_rate", p)
        self.assertNotIn("issuer_weighted_rate", p)


if __name__ == "__main__":
    unittest.main()
