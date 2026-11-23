"""Ten AICS-specific research agents, using source-ledger realities only."""
from __future__ import annotations

import copy
import datetime as dt
import unittest
from pathlib import Path

from scripts.aics_ten_analysis_agents import (
    AGENT_NAMES, SPX, V17, V18, agent_10_governance,
    read, run_agents,
)


class TenAnalysisAgentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v17 = read(V17)
        cls.v18 = read(V18)
        cls.spx = read(SPX)
        cls.report = run_agents(v17=cls.v17, v18=cls.v18,
                                sp500=cls.spx)

    def test_all_ten_agents_have_distinct_meaningful_outputs(self):
        x = self.report
        self.assertEqual(len(x["results"]), 10)
        self.assertEqual(x["agents_count"], 10)
        self.assertEqual([a["name"] for a in x["results"]], list(AGENT_NAMES))
        self.assertTrue(all(a["status"] == "research_pass" and a["result"]
                            for a in x["results"]))
        self.assertTrue(all(not a["trades_created"] and not a["model_weight_change"]
                            for a in x["results"]))
        self.assertIsNone(x["complete_aics_index"])
        self.assertIsNone(x["aics_sp500_spread"])
        self.assertFalse(x["production_model_updated"])
        self.assertFalse(x["certified_pit"])

    def test_exact_24m_lineage_and_source_bounds(self):
        lineage = self.report["results"][0]["result"]
        self.assertEqual(lineage["node_count"], 11)
        self.assertEqual(lineage["node_weights_total"], 1050)
        self.assertEqual(lineage["months_per_panel"], 24)
        self.assertEqual(lineage["new_private_credit_issuer_quarters"], 24)
        self.assertEqual(lineage["new_private_credit_breadth_events"], 7)
        self.assertFalse(lineage["historical_pit_certified"])

    def test_eligibility_never_peeks_after_asof(self):
        chrono = self.report["results"][1]["result"]
        self.assertGreater(chrono["source_date_checks"], 150)
        self.assertFalse(chrono["future_source_accepted"])
        self.assertEqual(chrono["market_cutoff"],
                         "last_weekday_proxy_not_exchange_calendar")
        bad = copy.deepcopy(self.v18)
        bad["monthly_last_weekday_market_proxy"][-1]["node_scores"]["Hyperscalers"][
            "research_eligible_date"] = "2026-11-01"
        with self.assertRaises(ValueError):
            run_agents(v17=self.v17, v18=bad, sp500=self.spx)

    def test_coverage_is_observability_not_full_index(self):
        coverage = self.report["results"][2]["result"]
        self.assertEqual(coverage["calendar"]["research_observability_pct"], "50.89")
        self.assertEqual(coverage["calendar"]["observed_weight_months"], 12825)
        self.assertEqual(coverage["market"]["research_observability_pct"], "50.00")
        self.assertEqual(coverage["market"]["observed_weight_months"], 12600)
        self.assertEqual(coverage["calendar"]["latest_known_nodes"], 10)
        self.assertEqual(coverage["market"]["latest_known_nodes"], 8)
        self.assertEqual(coverage["calendar"]["latest_missing_nodes"], ["AI Equities"])
        self.assertEqual(coverage["market"]["latest_missing_nodes"],
                         ["AI Equities", "Repo", "UST 30Y"])

    def test_freshness_reports_incomplete_90_day_coverage(self):
        freshness = self.report["results"][3]["result"]
        self.assertEqual(freshness["calendar"]["90"]["research_fresh_coverage_pct"], "47.72")
        self.assertEqual(freshness["calendar"]["90"]["valid_weight_months"], 12025)
        self.assertEqual(freshness["market"]["90"]["research_fresh_coverage_pct"], "46.83")
        self.assertEqual(freshness["market"]["90"]["valid_weight_months"], 11800)
        self.assertEqual(freshness["calendar"]["90"]["months_with_any_stale"], 7)

    def test_weighted_partial_verified_but_never_promoted(self):
        math = self.report["results"][4]["result"]
        self.assertEqual(math["calendar"]["reconciled_months"], 24)
        self.assertEqual(math["market"]["reconciled_months"], 24)
        self.assertIsNone(math["calendar"]["full_aics"])
        bad = copy.deepcopy(self.v18)
        bad["monthly_calendar_end_research"][-1][
            "partial_weighted_points_not_full_aics"] = "999.99"
        with self.assertRaises(ValueError):
            run_agents(v17=self.v17, v18=bad, sp500=self.spx)
        invalid = copy.deepcopy(self.v18)
        invalid["monthly_calendar_end_research"][-1][
            "node_scores"]["Insurers"]["score"] = "102"
        with self.assertRaises(ValueError):
            run_agents(v17=self.v17, v18=invalid, sp500=self.spx)

    def test_attribution_and_bounds_never_invent_missing_ai_equities(self):
        attribution = self.report["results"][5]["result"]
        stress = self.report["results"][6]["result"]
        self.assertEqual(attribution["calendar"]["partial_research_sum"], "466.26")
        self.assertEqual(attribution["market"]["partial_research_sum"], "268.39")
        self.assertEqual(
            stress["calendar"]["latest_math_bounds"][
                "upper_arithmetic_if_missing_100_NOT_OBSERVED"], "566.26")
        self.assertEqual(
            stress["market"]["latest_math_bounds"][
                "upper_arithmetic_if_missing_100_NOT_OBSERVED"], "593.39")
        self.assertEqual(
            stress["calendar"]["latest_math_bounds"]["missing_node_weight"], 100)
        self.assertEqual(
            stress["market"]["latest_math_bounds"]["missing_node_weight"], 325)
        self.assertFalse(stress["market"]["scenario_is_actual_prediction"])

    def test_market_prices_real_observed_no_fake_spread(self):
        spx = self.report["results"][7]["result"]
        self.assertEqual(spx["source_observations"], 24)
        self.assertEqual(spx["market_return_observations"], 23)
        self.assertEqual(spx["first_close"], "6032.38")
        self.assertEqual(spx["last_close"], "7580.08")
        self.assertEqual(spx["cumulative_market_return_pct"], "25.66")
        self.assertIsNone(spx["aics_sp500_normalized_spread"])
        self.assertIsNone(spx["forecasting_skill"])
        bad = copy.deepcopy(self.spx)
        bad["points"][0]["month"] = "2026-10"
        with self.assertRaises(ValueError):
            run_agents(v17=self.v17, v18=self.v18, sp500=bad)

    def test_ml_causal_attention_not_market_predictions(self):
        ml = self.report["results"][8]["result"]
        self.assertEqual(ml["source_eligible_events"], 64)
        self.assertEqual(ml["research_attention_flags"], 0)
        self.assertIsNone(ml["supervised_market_prediction"])
        self.assertIsNone(ml["historical_oos_performance"])

    def test_governance_rejects_missing_agents(self):
        gov = self.report["results"][9]["result"]
        self.assertEqual(gov["analyst_agents_prior_passed"], 9)
        self.assertEqual(gov["production_promotion"], "BLOCKED")
        self.assertEqual(gov["certified_historical_pit_node_count"], 0)
        self.assertEqual(gov["full_11node_index_months"], 0)
        self.assertFalse(gov["trades_created"])
        with self.assertRaises(ValueError):
            agent_10_governance(None, [], dt.date.today())

    def test_ten_source_collectors_are_linked_and_no_fake_certification(self):
        source_ids = [
            "SEC_ARCC","SEC_BXSL","SEC_OBDC","SEC_PRU","SEC_MET",
            "ALFRED_DGS30","SEC_CRWV","SEC_NBIS","SEC_MSFT","SEC_AMZN",
            "SEC_GOOG","SEC_META","NYFED_SOFR","ALFRED_IORB","SEC_APLD",
            "EIA_RTO_DEMAND","FED_G17","SEC_NVDA","SEC_MU","SEC_AVGO",
        ]
        manifest = {
            "schema":"aics-ten-agents-current-source-collector-v1",
            "agent_count":10,"unique_publisher_sources":20,
            "original_sources_archived":19,
            "sources":[{"source_id":sid,
                        "status":"blocked_eia_api_key_missing" if sid=="EIA_RTO_DEMAND"
                        else "archived_current_original_not_pit"}
                       for sid in source_ids],
            "current_download_not_historical_pit":True,
            "index_aics":None,
            "independently_verified_node_scores":0,
            "trades_created":False,
        }
        report = run_agents(v17=self.v17, v18=self.v18,
                            sp500=self.spx, captured=manifest)
        self.assertEqual(report["source_agents_count"], 10)
        self.assertEqual(report["actual_source_bytes_in_this_run"], 19)
        governance = report["results"][9]["result"]["source_collectors"]
        self.assertFalse(governance["all_sources_captured"])
        self.assertEqual(governance["missing_source_ids"], ["EIA_RTO_DEMAND"])
        broken = copy.deepcopy(manifest)
        broken["sources"].append({"source_id":"SEC_ARCC", "status":"archived_current_original_not_pit"})
        with self.assertRaises(ValueError):
            run_agents(v17=self.v17, v18=self.v18,
                       sp500=self.spx, captured=broken)


if __name__ == "__main__":
    unittest.main()
