"""Fixture-only SEC PIT tests. Original source bytes are verified in separate Actions."""
import copy
import datetime as dt
import unittest

from scripts.aics_arcc_verified_asof_panel import build, PanelError, SOURCE_PERIODS

DATES = [
    ("2024-12-31", "1.7", "1.0"),
    ("2025-12-31", "1.8", "1.2"),
    ("2026-03-31", "2.1", "1.2"),
    ("2026-06-30", "2.4", "1.4"),
    ("2026-09-30", "2.4", "1.4"),
]


def fixtures():
    a = {
        "schema_version": "aics-arcc-q4-exhibit-corrected-sec-asof-source-research-v1",
        "raw_original_html_documents_rehashed": 6,
        "distinct_observation_periods": 5,
        "source_verified_nonaccrual_values": 10,
        "retrospective_2024_value_visible_in_2024": False,
        "SEC_14_calendar_day_rule_enforced": True,
        "synthetic_rows_created": 0,
        "historical_24m_pit_attested": False,
        "independent_24m_oos": False,
        "one_issuer_not_entire_private_credit_node": True,
        "private_credit_node_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
        "source_artifact_provenance": {
            "q4_zip_id": 14476018751, "q1q3_zip_id": 14474764347,
            "q4_zip_sha256": "a" * 64, "q1q3_zip_sha256": "b" * 64,
        },
        "source_verified_disclosed_periods": [],
    }
    b = {
        "schema_version": "aics-arcc-q4-sec-corrected-durable-source-panel-v1",
        "confirmed_source_values": 10, "synthetic_market_rows": 0,
        "promotion": "BLOCKED", "index_aics": None,
        "new_verified_2025q4_model_available_at": "2026-02-18",
        "complete_24_month_market_pit": False,
        "independent_24_month_predictive_oos": False,
        "reverified_timeline_report_sha256": "38e6c0bb5ba64ed2edb1a76728cca3e74c455dfc1104e5b66cce2f9def79a5d1",
        "source_archives": {
            "q4": {"archive_sha256": "a" * 64},
            "q1q3": {"archive_sha256": "b" * 64},
        },
        "observed_source_periods": [],
    }
    for period, cost, fair in DATES:
        filed, available, kind = SOURCE_PERIODS[period]
        url = "https://www.sec.gov/Archives/edgar/data/1287750/EXHIBIT-" + period
        a["source_verified_disclosed_periods"].append({
            "period_end": period, "source_filed_at": filed,
            "aics_eligible_date_after_sec_14d": available,
            "nonaccrual_amortized_cost_pct": cost,
            "nonaccrual_fair_value_pct": fair,
            "source_html_sha256": "e" * 64,
            "source_url": url,
            "evidence_kind": kind,
            "independent_original_sec_value_verified": True,
            "independent_historical_publication_time_attested": False,
            "model_eligible": False,
        })
        b["observed_source_periods"].append({
            "period_end": period, "source_filed_at": filed,
            "available_at": available,
            "cost_pct": cost, "fair_value_pct": fair,
            "source_sha256": "e" * 64, "source_url": url,
            "evidence_kind": kind, "model_eligible": False,
        })
    return a, b


class TestCorrectedARCCSECPanel(unittest.TestCase):
    def report(self, date):
        a, b = fixtures()
        return build(a, dt.date.fromisoformat(date), b)

    def test_before_original_february_8k_plus_14_no_value(self):
        p = self.report("2026-02-17")
        self.assertEqual(p["verified_values_available_by_cutoff"], 0)
        self.assertIsNone(p["latest_known_nonaccrual_cost_pct"])

    def test_february_eighteenth_exposes_dec2025_not_in_2024(self):
        p = self.report("2026-02-18")
        self.assertEqual(p["verified_values_available_by_cutoff"], 4)
        self.assertEqual(p["source_observations"][0]["period_end"], "2024-12-31")
        self.assertEqual(p["source_observations"][0]["available_at"], "2026-02-18")
        self.assertFalse(p["retrospective_2024_values_visible_in_2024"])
        self.assertEqual(p["latest_known_original_sec_period"], "2025-12-31")
        self.assertEqual(p["latest_known_nonaccrual_cost_pct"], "1.8")
        self.assertEqual(self.report("2024-12-31")["verified_values_available_by_cutoff"], 0)

    def test_each_new_quarter_visible_only_after_sec_14_day_lag(self):
        checks = {
            "2026-05-11": 4, "2026-05-12": 6,
            "2026-08-11": 6, "2026-08-12": 8,
            "2026-11-09": 8, "2026-11-10": 10,
        }
        for day, expected in checks.items():
            with self.subTest(day=day):
                self.assertEqual(self.report(day)["verified_values_available_by_cutoff"], expected)

    def test_five_periods_and_no_model_promotion(self):
        p = self.report("2026-11-18")
        self.assertEqual(p["verified_observations_available_by_cutoff"], 5)
        self.assertEqual(p["verified_values_available_by_cutoff"], 10)
        self.assertEqual(p["latest_known_original_sec_period"], "2026-09-30")
        self.assertEqual(p["latest_known_nonaccrual_cost_pct"], "2.4")
        self.assertEqual(p["latest_known_nonaccrual_fair_value_pct"], "1.4")
        self.assertEqual(p["synthetic_financial_observations"], 0)
        self.assertFalse(p["full_historical_pit_attested"])
        self.assertFalse(p["independent_24m_oos"])
        self.assertIsNone(p["private_credit_node_score"])
        self.assertIsNone(p["index_aics"])
        self.assertEqual(p["promotion"], "BLOCKED")

    def test_wrong_february_legacy_may_baseline_fails(self):
        a, b = fixtures()
        a["source_verified_disclosed_periods"][1]["aics_eligible_date_after_sec_14d"] = "2026-05-12"
        with self.assertRaisesRegex(PanelError, "look-ahead"):
            build(a, dt.date(2026, 11, 18), b)

    def test_durable_and_original_mismatch_fails(self):
        a, b = fixtures()
        b["observed_source_periods"][2]["cost_pct"] = "9.9"
        with self.assertRaisesRegex(PanelError, "disagree"):
            build(a, dt.date(2026, 11, 18), b)

    def test_forged_2024_backdating_fails(self):
        a, b = fixtures()
        b["observed_source_periods"][0]["available_at"] = "2024-12-31"
        with self.assertRaises(PanelError):
            build(a, dt.date(2026, 11, 18), b)

    def test_forged_aics_score_fails(self):
        a, b = fixtures()
        a["private_credit_node_score"] = 69
        with self.assertRaises(PanelError):
            build(a, dt.date(2026, 11, 18), b)

    def test_source_receipt_sha_identity_mismatch_fails(self):
        a, b = fixtures()
        b["source_archives"]["q4"]["archive_sha256"] = "f" * 64
        with self.assertRaises(PanelError):
            build(a, dt.date(2026, 11, 18), b)


if __name__ == "__main__":
    unittest.main()
