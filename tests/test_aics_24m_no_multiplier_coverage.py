"""Historical no-multiplier coverage stays fail-closed without manufactured months."""
import json
import unittest
from datetime import date

from scripts.aics_24m_no_multiplier_coverage import (
    SP500, OUTPUT, build, candidates, percentile_last_24, gap
)


class NoMultiplier24mCoverageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = build()

    def test_all_24_months_have_real_market_observations(self):
        panel=self.panel
        self.assertEqual(panel["month_count"],24)
        self.assertEqual(panel["node_weights_total"],1050)
        self.assertEqual(panel["original_observation_months"],{"sp500":24,"ust30":24,"repo":24})
        self.assertEqual(panel["monthly"][0]["month"],"2024-11")
        self.assertEqual(panel["monthly"][-1]["month"],"2026-10")
        self.assertEqual(panel["monthly"][0]["sp500_last_session_close"],"6032.38")
        self.assertEqual(panel["monthly"][-1]["sp500_last_session_close"],"7580.08")
        self.assertFalse(panel["production_formula_changed"])

    def test_no_11_node_history_spread_or_fake_zeros(self):
        for row in self.panel["monthly"]:
            self.assertIsNone(row["full_11_node_aics_no_multiplier"])
            self.assertIsNone(row["aics_sp500_normalized_spread"])
            self.assertFalse(row["independent_historical_pit_confirmed"])
            if row["known_node_count_research_only"] == 0:
                self.assertIsNone(row["partial_known_weighted_points_not_aics"])
        self.assertEqual(self.panel["new_11_node_full_aics_months"],0)
        self.assertEqual(self.panel["new_11_node_sp500_spread_months"],0)
        self.assertIsNone(self.panel["certified_aics"])

    def test_new_dated_event_scores(self):
        by={(r["node"],r["available_at"]):r["score"] for r in candidates()}
        self.assertEqual(by["Neoclouds","2025-06-03"],"100.00")
        self.assertEqual(by["Neoclouds","2025-08-27"],"100.00")
        self.assertEqual(by["Neoclouds","2025-11-27"],"51.90")
        self.assertEqual(by["Neoclouds","2026-03-12"],"60.87")
        self.assertEqual(by["Neoclouds","2026-05-27"],"48.45")
        self.assertEqual(by["Neoclouds","2026-08-26"],"75.78")
        self.assertEqual(by["Private Credit","2026-08-20"],"66.67")
        self.assertEqual(by["Private Credit","2026-11-18"],"33.33")
        self.assertEqual(by["Hyperscalers","2026-08-14"],"0.00")
        self.assertEqual(by["Hyperscalers","2026-11-13"],"13.09")
        self.assertEqual(by["UST 30Y","2026-10-31"],"78.26")
        self.assertEqual(by["Repo","2026-10-31"],"86.96")
        self.assertEqual(by["Insurers","2025-05-15"],"0.51")
        self.assertEqual(by["Insurers","2025-08-14"],"0.77")
        self.assertEqual(by["Insurers","2025-11-13"],"0.74")
        self.assertEqual(by["Insurers","2026-02-26"],"0.79")
        self.assertEqual(by["Insurers","2026-05-20"],"0.44")
        self.assertEqual(by["Insurers","2026-08-19"],"1.32")
        self.assertEqual(by["Insurers","2026-11-18"],"1.04")
        self.assertEqual(by["Semiconductors Supply","2024-11-15"],"78.70")
        self.assertEqual(by["Semiconductors Supply","2024-12-17"],"78.80")
        self.assertEqual(by["Semiconductors Supply","2025-12-03"],"75.50")
        self.assertEqual(by["Semiconductors Supply","2026-10-16"],"76.50")
        self.assertEqual(by["Semiconductors Supply","2026-11-17"],"74.40")

    def test_month_end_gates_prevent_lookahead_and_backfill(self):
        by={row["month"]:row for row in self.panel["monthly"]}
        self.assertEqual(by["2024-11"]["known_node_count_research_only"],1)
        self.assertEqual(by["2024-11"]["partial_known_weighted_points_not_aics"],"39.35")
        self.assertEqual(by["2024-11"]["latest_eligible_research_scores"]["Semiconductors Supply"]["source_available_at"],"2024-11-15")
        self.assertEqual(by["2024-12"]["known_node_count_research_only"],1)
        self.assertEqual(by["2025-05"]["known_node_count_research_only"],2)
        self.assertEqual(by["2025-06"]["known_node_count_research_only"],3)
        self.assertEqual(by["2025-06"]["partial_known_weighted_points_not_aics"],"141.04")
        self.assertEqual(by["2025-11"]["known_node_count_research_only"],3)
        self.assertEqual(by["2025-11"]["partial_known_weighted_points_not_aics"],"94.63")
        self.assertEqual(by["2025-11"]["latest_eligible_research_scores"]["Semiconductors Supply"]["score"],"83.60")
        self.assertEqual(by["2025-12"]["latest_eligible_research_scores"]["Semiconductors Supply"]["source_available_at"],"2025-12-23")
        self.assertEqual(by["2026-01"]["latest_eligible_research_scores"]["Insurers"]["score"],"0.74")
        self.assertEqual(by["2026-02"]["latest_eligible_research_scores"]["Insurers"]["score"],"0.79")
        self.assertEqual(by["2026-02"]["latest_eligible_research_scores"]["Insurers"]["source_available_at"],"2026-02-26")
        self.assertEqual(by["2026-02"]["latest_eligible_research_scores"]["Neoclouds"]["score"],"51.90")
        self.assertEqual(by["2026-03"]["latest_eligible_research_scores"]["Neoclouds"]["score"],"60.87")
        self.assertEqual(by["2026-03"]["latest_eligible_research_scores"]["Neoclouds"]["source_available_at"],"2026-03-12")
        self.assertEqual(by["2026-03"]["partial_known_weighted_points_not_aics"],"98.30")
        self.assertEqual(by["2026-04"]["partial_known_weighted_points_not_aics"],"96.90")
        self.assertEqual(by["2026-04"]["known_node_count_research_only"],3)
        self.assertEqual(by["2026-05"]["known_node_count_research_only"],3)
        self.assertEqual(by["2026-07"]["known_node_count_research_only"],3)
        self.assertEqual(by["2026-08"]["known_node_count_research_only"],6)
        self.assertEqual(by["2026-09"]["known_node_count_research_only"],7)
        self.assertEqual(by["2026-10"]["known_node_count_research_only"],10)
        self.assertEqual(by["2026-10"]["missing_nodes"],
                         ["AI Equities"])
        self.assertEqual(by["2026-10"]["partial_known_weighted_points_not_aics"],"453.17")
        self.assertEqual(by["2026-10"]["latest_eligible_research_scores"]["Semiconductors Supply"]["source_available_at"],"2026-10-16")
        self.assertEqual(by["2026-08"]["latest_eligible_research_scores"]["Private Credit"]["source_available_at"],"2026-08-20")
        self.assertTrue(by["2026-09"]["latest_eligible_research_scores"]["Neoclouds"]["carried_from_prior_month"])
        self.assertEqual(by["2026-05"]["latest_eligible_research_scores"]["Neoclouds"]["source_available_at"],"2026-05-27")

    def test_checked_in_monthly_snapshot_matches_builder(self):
        checked = json.loads(OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual(checked["month_count"], 24)
        self.assertEqual(checked["new_11_node_full_aics_months"], 0)
        self.assertEqual(checked["new_11_node_sp500_spread_months"], 0)
        for actual, expected in zip(self.panel["monthly"], checked["monthly"]):
            for key in ("month", "as_of", "known_node_count_research_only",
                        "partial_known_weighted_points_not_aics",
                        "full_11_node_aics_no_multiplier", "aics_sp500_normalized_spread",
                        "missing_nodes", "sp500_last_session_close"):
                self.assertEqual(actual[key], expected[key], (actual["month"], key))
        self.assertEqual(
            [(x["node"], x["available_at"], x["score"]) for x in self.panel["score_source_events"]],
            [(x["node"], x["available_at"], x["score"]) for x in checked["score_source_events"]]
        )

    def test_no_retrospective_rank_in_fewer_than_24_observations(self):
        with self.assertRaisesRegex(ValueError,"23 antecedent"):
            percentile_last_24([1,2,3])
        with self.assertRaisesRegex(ValueError,"Positive|Non-positive"):
            gap(0,0)


if __name__=="__main__":
    unittest.main()
