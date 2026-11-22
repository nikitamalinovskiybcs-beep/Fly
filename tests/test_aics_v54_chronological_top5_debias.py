"""AICS V54: 100-candidate retrospective cutoff-correct selection on real sources.

No synthetic market observations, no historically untouched OOS claim.
"""
from __future__ import annotations

import copy
import json
import unittest

from scripts.aics_v51_credit_magnitude_early_warning import (
    ORIGINAL,V18,SPX,build as build_v51
)
from scripts.aics_v53_hundred_model_top5_ensemble import run as build_v53
from scripts.aics_v54_chronological_top5_debias import (
    evaluate,split_months,auc,DEDUPE_ABS_PEARSON,
)


class AicsV54ModelDebiasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data=[json.loads(path.read_text(encoding="utf-8")) for path in (ORIGINAL,V18,SPX)]
        cls.v51=build_v51(*data)
        cls.v53=build_v53(cls.v51)
        cls.result=evaluate(cls.v53,cls.v51)

    def test_actually_evaluate_hundred_model_strategies_with_past_labels(self):
        r=self.result
        self.assertEqual(r["hundred_original_different_model_strategies_recomputed"],100)
        self.assertEqual(len(r["training_only_all_100_candidate_ranked_model_results"]),100)
        self.assertEqual(len({x["id"] for x in r["training_only_all_100_candidate_ranked_model_results"]}),100)
        self.assertEqual(r["historical_model_risk_feature_months"],18)
        self.assertEqual(r["model_selection_training_date_cutoff"],"2025-10")
        self.assertTrue(r["horizon_future_label_ends_before_training_cutoff"])
        self.assertTrue(r["post_cutoff_evaluation_NOT_prospective_or_untouched_OOS"])

    def test_strict_cutoff_does_not_train_on_future_labels(self):
        x=self.result["honest_time_split_metrics"]
        self.assertEqual([m["horizon_months"] for m in x],[1,3,6])
        self.assertEqual([m["training_true_labels_at_cutoff"]["month_count"] for m in x],[8,6,3])
        self.assertEqual([m["training_true_labels_at_cutoff"]["positive_months"] for m in x],[1,1,1])
        self.assertEqual([m["later_observed_labels_after_cutoff"]["month_count"] for m in x],[9,9,6])
        self.assertEqual([m["later_observed_labels_after_cutoff"]["positive_months"] for m in x],[1,2,2])
        self.assertEqual(x[0]["later_positive_months"],["2026-02"])
        self.assertEqual(x[1]["later_positive_months"],["2026-01","2026-02"])
        self.assertEqual(x[2]["later_positive_months"],["2026-01","2026-02"])
        self.assertTrue(all(m["training_true_labels_at_cutoff"]["month_count"]<
                            m["later_observed_labels_after_cutoff"]["month_count"] for m in x))
        self.assertTrue(all(m["time_windows_overlap_in_train_and_test"] is False for m in x))

    def test_one_example_of_selection_bias_train_ranking_fails_later(self):
        r=self.result
        self.assertEqual(r["five_selected_using_only_train_end_date_labels"],
                         ["EXPERT-041","EXPERT-051","EXPERT-071","EXPERT-001","EXPERT-011"])
        vals=[m["later_auc_by_competitor"]["training_time_selected_five_median"]
              for m in r["honest_time_split_metrics"]]
        self.assertEqual(vals,[0.125,0.214286,0.375])
        self.assertTrue(all(x<0.5 for x in vals))
        self.assertIsNone(r["proven_forecast_accuracy_gain"])

    def test_corr_cap_replaces_duplicated_expert_family_members(self):
        r=self.result
        self.assertEqual(DEDUPE_ABS_PEARSON,0.8)
        self.assertEqual(r["five_selected_with_0_80_max_abs_correlation_using_only_train_features"],
                         ["EXPERT-041","EXPERT-056","EXPERT-076","EXPERT-066","EXPERT-017"])
        self.assertLessEqual(r["diversity_selected_five_max_abs_pearson"],0.800001)
        self.assertGreater(r["train_selected_five_max_abs_pearson"],0.8)
        vals=[m["later_auc_by_competitor"]["training_time_diversified_five_median"]
              for m in r["honest_time_split_metrics"]]
        self.assertEqual(vals,[0.375,0.214286,0.375])
        self.assertTrue(all(x<0.5 for x in vals))

    def test_do_not_reuse_v53_cheating_ranking(self):
        old=self.result
        changed=copy.deepcopy(self.v53)
        for m in changed["100_separately_evaluated_model_experts"]:
            m["exploratory_multi_horizon_rank"]=100 if m["agent_id"]=="EXPERT-100" else -100
            for outcome in m["outcome_discrimination_5pct_expost"].values():
                outcome["hindsight_AUC"]=0.99
        new=evaluate(changed,self.v51)
        self.assertEqual(old["five_selected_using_only_train_end_date_labels"],
                         new["five_selected_using_only_train_end_date_labels"])
        self.assertEqual(old["honest_time_split_metrics"],new["honest_time_split_metrics"])

    def test_post_cutoff_real_market_prices_never_reshape_train_choice(self):
        x=copy.deepcopy(self.v51)
        for r in x["24_month_same_source_model_comparison"]:
            if r["month"]=="2026-03":
                # Controlled test corruption, NOT a claimed historical price.
                r["same_month_SP500_close_source_observed"]="100"
        later=evaluate(self.v53,x)
        self.assertEqual(self.result["five_selected_using_only_train_end_date_labels"],
                         later["five_selected_using_only_train_end_date_labels"])
        self.assertEqual(self.result["five_selected_with_0_80_max_abs_correlation_using_only_train_features"],
                         later["five_selected_with_0_80_max_abs_correlation_using_only_train_features"])
        self.assertNotEqual(
            [m["later_auc_by_competitor"] for m in self.result["honest_time_split_metrics"]],
            [m["later_auc_by_competitor"] for m in later["honest_time_split_metrics"]])

    def test_no_aics_promotion_crisis_skill_claim_or_trading(self):
        r=self.result
        self.assertIsNone(r["full_AICS_index"])
        self.assertEqual(r["certified_historical_first_delivery_PIT_nodes"],0)
        self.assertTrue(r["official_AICS_components_or_thresholds_changed"] is False)
        self.assertTrue(r["cutoff_and_model_formulas_devised_after_full_history_seen"])
        self.assertFalse(r["production_trades"])
        self.assertEqual(r["original_11_node_weights"],1050)

    def test_invalid_sources_and_classless_roc_null(self):
        self.assertIsNone(auc([1,2,3],[False,False,False]))
        self.assertIsNone(auc([1,2,3],[True,True,True]))
        self.assertEqual(auc([1,1,1],[True,False,False]),0.5)
        wrong=copy.deepcopy(self.v53)
        wrong["approved_live_AICS_index"]=610
        with self.assertRaises(ValueError):
            evaluate(wrong,self.v51)
        wrong=copy.deepcopy(self.v53)
        wrong["100_separately_evaluated_model_experts"].pop()
        with self.assertRaises(ValueError):
            evaluate(wrong,self.v51)


if __name__=="__main__":
    unittest.main()
