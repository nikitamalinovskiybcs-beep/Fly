"""Model-only V50 tests on the existing 24 public-source research months.

Parametric mathematical perturbations in these tests are not synthetic
historical observations, registered trading signals, or claimed OOS returns.
"""
from __future__ import annotations

import copy
import json
import math
import unittest

from scripts.aics_v50_hundred_model_orchestra import (
    SOURCE,SPX,WEIGHTS,discrete_multiplier,continuous_multiplier,bounds,zone,
    pearson,model_orchestra
)


class HundredModelOrchestraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig=json.loads(SOURCE.read_text(encoding="utf-8"))
        cls.prices=json.loads(SPX.read_text(encoding="utf-8"))
        cls.report=model_orchestra(cls.orig,cls.prices)

    def test_exactly_100_distinct_model_experiments_10_squads(self):
        report=self.report
        self.assertEqual(report["actual_deterministic_model_experiments_executed"],100)
        self.assertEqual(report["separately_trained_AI_agents_started"],0)
        self.assertEqual(len(report["100_model_experiments"]),100)
        self.assertEqual(len({x["task_id"] for x in report["100_model_experiments"]}),100)
        self.assertEqual(len(report["model_experiment_squads"]),10)
        self.assertTrue(all(x==10 for x in report["model_experiment_squads"].values()))
        self.assertTrue(all(x["historical_PIT_forecast_accuracy"] is None
                            and x["production_change_approved"] is False
                            for x in report["100_model_experiments"]))

    def test_mathematical_legacy_jump_at_hot_threshold(self):
        self.assertEqual(discrete_multiplier(2),1)
        self.assertAlmostEqual(discrete_multiplier(3),1.2)
        self.assertAlmostEqual(self.report["legacy_hot_third_node_cliff_points_at_raw_500"],100.0)
        self.assertAlmostEqual(
            self.report["continuous_shadow_10wide_third_hot_cliff_points_at_0_1_epsilon"],2.0)
        self.assertLess(self.report["continuous_shadow_10wide_third_hot_cliff_points_at_0_1_epsilon"],
                        self.report["legacy_hot_third_node_cliff_points_at_raw_500"])

    def test_smooth_shadow_is_monotonic_and_continuous(self):
        z=[continuous_multiplier([100,100,i/10]) for i in range(0,1001)]
        self.assertTrue(all(1<=v<=1.35 for v in z))
        self.assertTrue(all(a<=b for a,b in zip(z,z[1:])))
        self.assertLessEqual(max(b-a for a,b in zip(z,z[1:])),0.0021)

    def test_24_real_months_bound_without_filling_unknowns(self):
        r=self.report
        self.assertEqual(r["observed_months_evaluated"],24)
        self.assertEqual(len(r["monthly_original_model_robustness"]),24)
        self.assertEqual(r["official_legacy_model_envelope_ambiguous_months"],24)
        self.assertEqual(r["unambiguous_legacy_decision_months"],0)
        self.assertEqual(r["continuous_shadow_model_envelope_ambiguous_months"],24)
        self.assertEqual(r["last_observed_month"],"2026-10")
        self.assertEqual(len(r["last_month_unknown_nodes"]),3)
        self.assertIn("Repo",r["last_month_unknown_nodes"])
        self.assertIn("AI Equities",r["last_month_unknown_nodes"])
        self.assertIn("UST 30Y",r["last_month_unknown_nodes"])

    def test_interval_extrema_and_research_no_trade(self):
        r=self.report
        self.assertFalse(r["original_11_node_weights_changed"])
        self.assertFalse(r["original_450_500_threshold_policy_changed"])
        self.assertFalse(r["original_discrete_hot_multiplier_changed"])
        self.assertEqual(sum(WEIGHTS.values()),1050)
        self.assertEqual(r["certified_AICS_nodes"],0)
        self.assertIsNone(r["full_11_node_AICS"])
        self.assertIsNone(r["production_signal"])
        self.assertIsNone(r["backtest_accuracy_improvement"])
        self.assertFalse(r["trades_created"])
        val=bounds({"Private Credit":50})
        self.assertEqual(val["known_weight"],150)
        self.assertEqual(val["missing_weight"],900)
        self.assertLess(val["low"],val["high"])
        self.assertTrue(val["zero_or_100_missing_are_mathematical_extrema_not_observations"])

    def test_bad_lookahead_and_promoted_production_rejected(self):
        bad=copy.deepcopy(self.orig)
        bad["monthly_last_weekday_market_proxy"][0]["node_scores"]["Insurers"]["research_eligible_date"]="2026-10-01"
        with self.assertRaises(ValueError):
            model_orchestra(bad,self.prices)
        bad=copy.deepcopy(self.orig)
        bad["monthly_last_weekday_market_proxy"][0]["full_aics"]=420
        with self.assertRaises(ValueError):
            model_orchestra(bad,self.prices)
        bad=copy.deepcopy(self.orig)
        bad["historical_pit_source_bytes_independently_attested"]=True
        with self.assertRaises(ValueError):
            model_orchestra(bad,self.prices)

    def test_no_imputed_nodes_and_unapproved_thresholds(self):
        with self.assertRaises(ValueError):
            bounds({"Totally Invented Node":67})
        with self.assertRaises(ValueError):
            bounds({"Insurers":float("nan")})
        with self.assertRaises(ValueError):
            zone(300,700,entry=500,exit=450)
        self.assertEqual(zone(300,700),"ABSTAIN_SIGNAL_UNIDENTIFIED")
        self.assertEqual(zone(300,449),"ROBUST_ENTRY_SHADOW_NOT_TRADE")
        self.assertEqual(zone(501,700),"ROBUST_CASH_SHADOW_NOT_TRADE")

    def test_no_retroactive_forecast_claim(self):
        self.assertIsNone(self.report["smoothing_proven_out_of_sample_forecast_improvement"])
        self.assertIsNone(self.report["independent_historical_24_month_PIT_forecast_accuracy"])
        leads=[x for x in self.report["100_model_experiments"]
               if x["squad"]=="07_next_month_target_falsification"]
        self.assertEqual(len(leads),10)
        self.assertTrue(all(x["result"]["ex_ante_PIT_validated"] is False
                            and x["result"]["do_not_select_best_correlation"] is True
                            for x in leads))
        self.assertIsNone(pearson([1,1,1,1,1,1],[2,3,4,5,6,7]))


if __name__=="__main__":
    unittest.main()
