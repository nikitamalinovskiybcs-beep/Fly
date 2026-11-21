"""Historical no-multiplier coverage stays fail-closed without manufactured months."""
import json
import unittest
from datetime import date

from scripts.aics_24m_no_multiplier_coverage import (
    SP500, build, candidates, percentile_last_24, gap
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
        self.assertEqual(by["Neoclouds","2026-05-27"],"48.45")
        self.assertEqual(by["Neoclouds","2026-08-26"],"75.78")
        self.assertEqual(by["Private Credit","2026-08-20"],"66.67")
        self.assertEqual(by["Private Credit","2026-11-18"],"33.33")
        self.assertEqual(by["Hyperscalers","2026-08-14"],"0.00")
        self.assertEqual(by["Hyperscalers","2026-11-13"],"13.09")
        self.assertEqual(by["UST 30Y","2026-10-31"],"78.26")
        self.assertEqual(by["Repo","2026-10-31"],"86.96")

    def test_month_end_gates_prevent_lookahead_and_backfill(self):
        by={row["month"]:row for row in self.panel["monthly"]}
        self.assertEqual(by["2026-04"]["known_node_count_research_only"],0)
        self.assertEqual(by["2026-05"]["known_node_count_research_only"],1)
        self.assertEqual(by["2026-07"]["known_node_count_research_only"],1)
        self.assertEqual(by["2026-08"]["known_node_count_research_only"],4)
        self.assertEqual(by["2026-09"]["known_node_count_research_only"],5)
        self.assertEqual(by["2026-10"]["known_node_count_research_only"],8)
        self.assertEqual(by["2026-10"]["missing_nodes"],
                         ["AI Equities","Insurers","Semiconductors Supply"])
        self.assertEqual(by["2026-10"]["partial_known_weighted_points_not_aics"],"413.27")
        self.assertEqual(by["2026-08"]["latest_eligible_research_scores"]["Private Credit"]["source_available_at"],"2026-08-20")
        self.assertTrue(by["2026-09"]["latest_eligible_research_scores"]["Neoclouds"]["carried_from_prior_month"])
        self.assertEqual(by["2026-05"]["latest_eligible_research_scores"]["Neoclouds"]["source_available_at"],"2026-05-27")

    def test_no_retrospective_rank_in_fewer_than_24_observations(self):
        with self.assertRaisesRegex(ValueError,"23 antecedent"):
            percentile_last_24([1,2,3])
        with self.assertRaisesRegex(ValueError,"Positive|Non-positive"):
            gap(0,0)


if __name__=="__main__":
    unittest.main()
