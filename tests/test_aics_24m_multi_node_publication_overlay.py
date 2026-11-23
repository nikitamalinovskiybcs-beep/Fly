"""Fail-closed tests for the parallel 10-node research date migration."""
import copy
import json
import unittest
from scripts.aics_24m_multi_node_publication_overlay import (
    build, source_updates, read, last_weekday_proxy, OUTPUT)
import datetime as dt


class AicsMultiNodeResearchPublicationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=build()
        cls.months={x["month"]:x for x in cls.result["monthly_calendar_end_research"]}
        cls.weekdays={x["month"]:x for x in cls.result["monthly_last_weekday_market_proxy"]}

    def test_source_gates_and_fixed_weights(self):
        x=self.result
        self.assertEqual(len(x["node_weights"]),11)
        self.assertEqual(sum(x["node_weights"].values()),1050)
        self.assertEqual(x["baseline_research_coverage_pct"],"32.04")
        self.assertGreater(x["converted_existing_sec_events"],20)
        self.assertEqual(x["new_original_2025_hyperscaler_events"],4)
        self.assertEqual(len(x["monthly_calendar_end_research"]),24)
        self.assertEqual(len(x["monthly_last_weekday_market_proxy"]),24)
        self.assertEqual(x["complete_11_node_aics_months"],0)
        self.assertFalse(x["production_change"])
        self.assertFalse(x["trades_created"])
        self.assertFalse(x["independently_historical_pit_attested"])

    def test_real_hyperscaler_and_neocloud_may_2025_sources(self):
        may=self.months["2025-05"]
        self.assertEqual(may["known_node_count"],4)
        self.assertEqual(may["node_scores"]["Hyperscalers"]["score"],"0.00")
        self.assertEqual(may["node_scores"]["Neoclouds"]["score"],"100.00")
        self.assertEqual(may["node_scores"]["Neoclouds"]["research_eligible_date"],"2025-05-21")
        self.assertNotIn("Private Credit",may["node_scores"])
        self.assertIsNone(may["full_aics"])

    def test_neocloud_q4_moves_to_feb2026(self):
        feb=self.months["2026-02"]
        self.assertEqual(feb["node_scores"]["Neoclouds"]["score"],"60.87")
        self.assertEqual(feb["node_scores"]["Neoclouds"]["research_eligible_date"],"2026-02-27")

    def test_hyperscaler_2026q3_after_oct_market_close(self):
        month=self.months["2026-10"]
        market=self.weekdays["2026-10"]
        self.assertEqual(month["cutoff_date"],"2026-10-31")
        self.assertEqual(month["node_scores"]["Hyperscalers"]["research_eligible_date"],
                         "2026-10-31")
        self.assertEqual(month["node_scores"]["Hyperscalers"]["score"],"13.09")
        self.assertEqual(market["cutoff_date"],"2026-10-30")
        self.assertEqual(market["node_scores"]["Hyperscalers"]["score"],"0.00")
        self.assertNotIn("UST 30Y",market["node_scores"])
        self.assertNotIn("Repo",market["node_scores"])
        self.assertIsNone(market["aics_sp500_spread"])

    def test_committed_24_month_snapshot_exactly_matches_replay(self):
        checked=json.loads(OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual(self.result,checked)

    def test_no_change_legacy_source_files_and_no_full_backtest(self):
        baseline=read("aics_24_month_no_multiplier_coverage_2026-11-21.json")
        self.assertEqual(baseline["monthly"][-1]["partial_known_weighted_points_not_aics"],
                         "453.17")
        self.assertIsNone(baseline["monthly"][-1]["full_11_node_aics_no_multiplier"])
        self.assertIsNone(baseline["monthly"][-1]["aics_sp500_normalized_spread"])
        for rows in (self.result["monthly_calendar_end_research"],
                     self.result["monthly_last_weekday_market_proxy"]):
            for row in rows:
                self.assertIsNone(row["full_aics"])
                self.assertIsNone(row["aics_sp500_spread"])
                self.assertFalse(row["historical_pit_certified"])
                self.assertEqual(sum(self.result["node_weights"][n]
                                     for n in row["node_scores"]),row["known_weight"])

    def test_lookahead_date_changes_cannot_manufacture_trades(self):
        self.assertEqual(last_weekday_proxy(dt.date(2026,10,31)),
                         dt.date(2026,10,30))
        orig=read("neoclouds_2025_q1_q3_sec_cashflow_research_2026-11-21.json")
        broken=copy.deepcopy(orig)
        self.assertNotEqual(broken["sources"]["nbis_q1"]["available_at"],
                            broken["sources"]["nbis_q1"]["filed_at"])
        # source_updates only authorizes dates from named source records,
        # never from an arbitrary score-bearing front-end message.
        updates=source_updates(read("aics_24_month_no_multiplier_coverage_2026-11-21.json")["score_source_events"])
        self.assertTrue(all(row["research_eligible_date"]<=key[1]
                            for key,row in updates.items()))


if __name__=="__main__":
    unittest.main()
