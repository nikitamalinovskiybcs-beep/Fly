"""V52 100 model-scenario checks on real historical output, never fake data."""
from __future__ import annotations

import copy
import json
import unittest

from scripts.aics_v51_credit_magnitude_early_warning import ORIGINAL,V18,SPX,build as v51_build
from scripts.aics_v52_horizon_credit_model_robustness import (
    evaluate,shadow_channel,_cohort_sample,_event_episodes,_jackknife,
    _paired_metrics,auc,dec
)


class HorizonCreditModelV52Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sources=[json.loads(p.read_text(encoding="utf-8")) for p in (ORIGINAL,V18,SPX)]
        cls.v51=v51_build(*sources)
        cls.result=evaluate(cls.v51)
        cls.close=[dec(r["same_month_SP500_close_source_observed"])
                   for r in cls.v51["24_month_same_source_model_comparison"]]

    def test_100_horizon_threshold_scenarios_are_executed_not_100_trained_ais(self):
        r=self.result
        self.assertEqual(r["100_coordinated_model_falsification_scenarios"],100)
        self.assertEqual(r["number_of_horizon_director_roles"],10)
        self.assertEqual(r["actually_new_independently_trained_agents"],0)
        self.assertEqual(len(r["100_expost_model_falsification_tasks"]),100)
        self.assertEqual(len({x["task_id"] for x in r["100_expost_model_falsification_tasks"]}),100)
        self.assertTrue(all(x["out_of_sample_prediction_skill"] is None
                            for x in r["100_expost_model_falsification_tasks"]))

    def test_fast_breadth_preserved_and_slow_severity_shadow_retained(self):
        self.assertEqual(shadow_channel(1),("breadth_fast","1.00","0.00"))
        self.assertEqual(shadow_channel(3),("equal_mid","0.50","0.50"))
        self.assertEqual(shadow_channel(6),("severity_slow","0.00","1.00"))
        rows=self.result["secondary_5pct_same_month_model_comparison"]
        one=next(x for x in rows if x["horizon_months"]==1)
        three=next(x for x in rows if x["horizon_months"]==3)
        six=next(x for x in rows if x["horizon_months"]==6)
        self.assertAlmostEqual(one["AUC_V52_horizon_split_expost"],0.609375)
        self.assertEqual(one["AUC_V52_horizon_split_expost"],one["AUC_legacy_expost"])
        self.assertEqual(six["AUC_V52_horizon_split_expost"],six["AUC_V51_severity_expost"])
        self.assertAlmostEqual(six["AUC_V52_horizon_split_expost"],0.6388888888888888)
        self.assertTrue(three["AUC_V52_horizon_split_expost"] is not None)

    def test_tiny_real_crash_sample_held_out_cluster_removes_six_month_edge(self):
        x=self.result
        self.assertEqual(x["six_month_positive_month_count"],3)
        self.assertEqual(x["six_month_distinct_positive_episode_count"],2)
        self.assertFalse(x["six_month_v51_auc_better_after_every_positive_episode_omission"])
        self.assertAlmostEqual(x["six_month_one_episode_omission_min_V51_auc_gap"],0.0)
        j=next(r for r in x["secondary_5pct_episode_deletion_robustness"]
               if r["horizon_months"]==6)
        self.assertEqual(len(j["leave_one_actual_positive_episode_out"]),2)
        self.assertEqual(
            [v["held_out_event_episode_months"]
             for v in j["leave_one_actual_positive_episode_out"]],
            [["2025-02"],["2026-01","2026-02"]])
        self.assertEqual(
            next(v for v in j["leave_one_actual_positive_episode_out"]
                 if v["held_out_event_episode_months"]==["2026-01","2026-02"])[
                 "V51_minus_legacy_auc_gap_without_episode"],
            0.0,
        )

    def test_10pct_crisis_warning_unscorable_in_all_named_horizons(self):
        x=self.result
        self.assertEqual(x["primary_crisis_10pct_positive_months_by_1_3_6m"],[0,0,0])
        self.assertTrue(x["primary_crisis_AUC_all_undefined"])
        self.assertIsNone(x["model_improved_independent_crisis_warning_performance"])
        self.assertIsNone(x["independent_out_of_sample_test"])
        self.assertIsNone(x["production_11node_AICS"])
        self.assertFalse(x["trades_created"])

    def test_episodes_do_not_double_count_adjacent_month_as_new_crash(self):
        rows=[
            {"month":"2025-02","event":True},
            {"month":"2025-03","event":False},
            {"month":"2026-01","event":True},
            {"month":"2026-02","event":True},
        ]
        p=_event_episodes(rows)
        self.assertEqual([x["positive_months"] for x in p],
                         [["2025-02"],["2026-01","2026-02"]])

    def test_outcome_label_not_used_to_select_alternative_each_month(self):
        r=self.result
        self.assertTrue(r["horizon_split_proposed_after_observing_V51_results"])
        self.assertFalse(r["shadow_horizon_parameters_trainable_from_current_expost_grid"])
        rows=_cohort_sample(self.v51,self.close,1,dec(5))
        self.assertEqual(len(rows),18)
        self.assertTrue(all(a["old"]==a["split"] for a in rows))
        x=_cohort_sample(self.v51,self.close,6,dec(5))
        self.assertEqual(len(x),15)
        self.assertTrue(all(a["hybrid"]==a["split"] for a in x))
        self.assertEqual(sum(a["event"] for a in x),3)

    def test_negative_guard_bad_pit_promotion_and_source_roster(self):
        mutated=copy.deepcopy(self.v51)
        mutated["full_11node_AICS"]=620
        with self.assertRaises(ValueError):
            evaluate(mutated)
        mutated=copy.deepcopy(self.v51)
        mutated["historical_independent_first_provider_delivery_verified"]=True
        with self.assertRaises(ValueError):
            evaluate(mutated)
        mutated=copy.deepcopy(self.v51)
        mutated["24_month_same_source_model_comparison"][0]["matched_same_original_3BDC_source_family"]=False
        with self.assertRaises(ValueError):
            evaluate(mutated)

    def test_auc_requires_both_positive_and_negative_and_ties_half(self):
        self.assertEqual(auc([1,1,1],[True,False,False]),0.5)
        self.assertIsNone(auc([1,2,3],[False,False,False]))
        self.assertIsNone(auc([1,2,3],[True,True,True]))
        with self.assertRaises(ValueError):
            shadow_channel(0)


if __name__=="__main__":
    unittest.main()
