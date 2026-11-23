"""V57 tests: 10k REAL optimization steps; synthetic variants only in tests.

Does not create additional financial observations or train OpenAI's model.
"""
from __future__ import annotations

import copy
import json
import unittest

from scripts.aics_v51_credit_magnitude_early_warning import ORIGINAL,V18,SPX,build as v51_build
from scripts.aics_v53_hundred_model_top5_ensemble import run as v53_run
from scripts.aics_v55_forward_prospective_conductor import SELECTED
from scripts.aics_v57_ten_thousand_real_gradient_steps import (
    STEPS, LOO_STEPS, MIN_W, MAX_W, _fit, _loss, _project_simplex,
    _observations, build,
)


class V57TenThousandRealTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src=[json.loads(p.read_text(encoding="utf-8")) for p in (ORIGINAL,V18,SPX)]
        cls.v51=v51_build(*src)
        cls.v53=v53_run(cls.v51)
        cls.result=build(cls.v51,cls.v53)

    def test_10000_actual_optimizer_steps_plus_8000_training_sensitivities(self):
        r=self.result
        self.assertEqual(r["actual_gradient_optimization_steps_executed"],10000)
        self.assertEqual(r["additional_leave_one_month_out_research_fit_steps"],8000)
        self.assertEqual(len(r["optimizer_trace_every_1000_steps"]),10)
        self.assertEqual(r["optimizer_trace_every_1000_steps"][-1]["optimizer_step"],10000)
        self.assertEqual(len(r["leave_one_real_training_month_out_weight_sensitivity"]),8)
        self.assertEqual(r["training_month_count"],8)
        self.assertEqual(r["later_month_count"],9)

    def test_five_frozen_experts_still_sum_to_one_and_stay_bounded(self):
        r=self.result
        self.assertEqual(r["frozen_five_ids"],list(SELECTED))
        weights=r["model_weights_trained_on_historical_eight_real_train_labels"]
        self.assertEqual(set(weights),set(SELECTED))
        self.assertAlmostEqual(sum(weights.values()),1,places=8)
        self.assertTrue(all(MIN_W-1e-9<=x<=MAX_W+1e-9 for x in weights.values()))
        self.assertTrue(r["frozen_5_model_code_unchanged"])
        self.assertFalse(r["the_new_weights_supersede_live_V56_equal_weights"])

    def test_actual_history_not_generated_fictitious_10000_examples(self):
        r=self.result
        self.assertEqual(r["number_of_new_market_observations_generated"],0)
        self.assertEqual(r["number_of_new_real_prospective_forecasts"],0)
        self.assertEqual(r["separate_autonomous_trained_AI_agents_created"],0)
        self.assertTrue(r["optimizer_steps_are_repeated_training_on_same_8_real_examples"])
        self.assertTrue(r["this_does_NOT_establish_untouched_OOS_skill"])
        self.assertTrue(r["model_and_2025_10_split_chosen_AFTER_history_observed"])
        self.assertEqual(r["training_positive_label_months"],1)
        self.assertEqual(r["later_positive_label_months"],1)

    def test_no_new_10pct_crisis_prediction_or_main_index(self):
        r=self.result
        self.assertIsNone(r["10pct_crisis_warning_accuracy"])
        self.assertIsNone(r["whole_11node_index"])
        self.assertEqual(r["independently_verified_historical_PIT_nodes"],0)
        self.assertFalse(r["production_AICS_weights_changed"])
        self.assertFalse(r["official_hot_multiplier_or_thresholds_changed"])
        self.assertFalse(r["trades_created"])
        self.assertTrue(r["optimization_research_only_not_deployable_regardless_in_sample_or_later_result"])

    def test_actual_earlier_and_later_are_disjoint(self):
        rows,_,_=_observations(self.v51,self.v53)
        early=[r for r in rows if r["split"]=="earlier"]
        later=[r for r in rows if r["split"]=="later"]
        self.assertEqual(len(early),8)
        self.assertEqual(len(later),9)
        self.assertFalse(set(x["month"] for x in early)&set(x["month"] for x in later))
        self.assertTrue(all(x["month"]<="2025-10" for x in early))
        self.assertTrue(all(x["month"]>"2025-10" for x in later))

    def test_train_fit_never_touches_later_labels_even_if_they_were_altered(self):
        rows,_,_=_observations(self.v51,self.v53)
        train=[r for r in rows if r["split"]=="earlier"]
        new=copy.deepcopy(rows)
        for row in new:
            if row["split"]=="later":
                row["observed_real_drawdown_5pct_label"]=not row["observed_real_drawdown_5pct_label"]
        w,_=_fit(train,steps=123)
        w_other,_=_fit([x for x in new if x["split"]=="earlier"],steps=123)
        self.assertEqual(w,w_other)

    def test_actual_train_squared_ordinal_loss_can_be_measured_not_called_accuracy(self):
        rows,_,_=_observations(self.v51,self.v53)
        train=[r for r in rows if r["split"]=="earlier"]
        w,trace=_fit(train,steps=STEPS)
        self.assertEqual(len(trace),10)
        self.assertLessEqual(_loss(train,w),_loss(train,[0.2]*5)+1e-10)
        self.assertTrue(all(trace[i]["optimizer_step"]<trace[i+1]["optimizer_step"]
                            for i in range(9)))
        self.assertTrue(self.result["train_5pct_model_comparison"]["not_calibrated_crisis_probability"])

    def test_projection_and_unsafe_optimizer_bounds_fail_closed(self):
        w=_project_simplex([1,2,3,4,5])
        self.assertAlmostEqual(sum(w),1,places=9)
        self.assertTrue(all(MIN_W<=a<=MAX_W for a in w))
        with self.assertRaises(ValueError):
            _project_simplex([0.1,float("nan"),0.1,0.1,0.1])
        with self.assertRaises(ValueError):
            _fit([{"risk_by_frozen_expert":[0.2]*5,"observed_real_drawdown_5pct_label":False}],
                 steps=STEPS+1)
        with self.assertRaises(ValueError):
            _fit([],steps=10)

if __name__=="__main__":
    unittest.main()
