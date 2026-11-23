"""Durable SEC original-backed ARCC source receipt tests; research, not score."""
import datetime as dt
import json
import unittest
from decimal import Decimal
from pathlib import Path

FILE = Path("aics_data/research/arcc_conservative_observed_nonaccrual_2026-11-18.json")


class TestPinnedARCCOriginals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FILE.read_text(encoding="utf-8"))

    def test_original_receipt_no_source_to_score_promotion(self):
        x = self.data
        self.assertEqual(x["node"], "Private Credit")
        self.assertEqual(x["node_weight"], 150)
        self.assertEqual(x["original_sec_value_confirmations"], 8)
        self.assertFalse(x["baseline_earlier_issuer_release_original_confirmed"])
        self.assertFalse(x["source_to_model_pit_independently_attested"])
        self.assertFalse(x["historical_24_month_pit_complete"])
        self.assertFalse(x["independent_24_month_oos"])
        self.assertFalse(x["private_credit_market_representative"])
        self.assertIsNone(x["node_score"])
        self.assertIsNone(x["index_aics"])
        self.assertEqual(x["promotion"], "BLOCKED")

    def test_exact_14_day_embargo_and_earliest_baseline_source(self):
        rows = self.data["observations"]
        self.assertEqual(len(rows), 4)
        self.assertEqual(len({r["period_end"] for r in rows}), 4)
        self.assertEqual(rows[0]["period_end"], "2025-12-31")
        self.assertFalse(rows[0]["source_current_quarter"])
        self.assertEqual(rows[0]["conservative_available_at"], "2026-05-12")
        self.assertEqual(rows[0]["original_html_sha256"], rows[1]["original_html_sha256"])
        for row in rows:
            self.assertEqual(
                dt.date.fromisoformat(row["conservative_available_at"]),
                dt.date.fromisoformat(row["first_verified_sec_filed_at"])
                + dt.timedelta(days=14),
            )
            self.assertTrue(row["source_sec_exhibit_url"].startswith(
                "https://www.sec.gov/Archives/edgar/data/1287750/"))
            self.assertEqual(len(row["original_html_sha256"]), 64)

    def test_cumulative_8_visibility_scenarios_never_backfill(self):
        x = self.data["as_of_cumulative_visibility"]
        self.assertEqual(len(x), 8)
        self.assertEqual(
            [(r["as_of"], r["verified_candidate_values_visible"]) for r in x],
            [("2026-02-18", 0), ("2026-05-11", 0), ("2026-05-12", 4),
             ("2026-08-11", 4), ("2026-08-12", 6),
             ("2026-11-09", 6), ("2026-11-10", 8), ("2026-11-18", 8)],
        )
        for scenario in x:
            eligible = sum(
                dt.date.fromisoformat(r["conservative_available_at"])
                <= dt.date.fromisoformat(scenario["as_of"])
                for r in self.data["observations"]
            )
            self.assertEqual(eligible * 2, scenario["verified_candidate_values_visible"])

    def test_research_metrics_cost_and_fair_change(self):
        rows = self.data["observations"]
        self.assertEqual(
            Decimal(rows[-1]["nonaccrual_cost_pct"])
            - Decimal(rows[0]["nonaccrual_cost_pct"]),
            Decimal(self.data["cost_change_dec2025_to_sep2026_percentage_points"]),
        )
        self.assertEqual(
            Decimal(rows[-1]["nonaccrual_fair_value_pct"])
            - Decimal(rows[0]["nonaccrual_fair_value_pct"]),
            Decimal(self.data["fair_change_dec2025_to_sep2026_percentage_points"]),
        )
        self.assertEqual(rows[-1]["nonaccrual_cost_pct"], "2.4")
        self.assertEqual(rows[-1]["nonaccrual_fair_value_pct"], "1.4")

    def test_distinct_source_sha256_and_original_archive_binding(self):
        x = self.data
        self.assertEqual(len({r["original_html_sha256"] for r in x["observations"]}), 3)
        for field in ("verification_artifact_zip_sha256", "generated_timeline_sha256",
                      "original_verified_report_sha256", "original_sec_html_archive_sha256"):
            self.assertEqual(len(x[field]), 64)


if __name__ == "__main__":
    unittest.main()
