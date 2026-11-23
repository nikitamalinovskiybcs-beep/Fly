"""V53 source-real only model tournament, 100 unique feature algorithms and top 5."""
from __future__ import annotations
import copy
import json
import unittest
from scripts.aics_v51_credit_magnitude_early_warning import (
    ORIGINAL,V18,SPX,build as v51_build
)
from scripts.aics_v53_hundred_model_top5_ensemble import (
    FAMILIES,source_rows,candidate_score,choose,run
)


class HundredModelFiveChampionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src=[json.loads(p.read_text(encoding="utf-8")) for p in (ORIGINAL,V18,SPX)]
        cls.v51=v51_build(*src)
        cls.output=run(cls.v51)

    def test_one_hundred_distinct_scoring_strategies_actually_executed(self):
        r=self.output
        self.assertEqual(len(FAMILIES),10)
        self.assertEqual(r["hundred_distinct_deterministic_model_expert_strategies_executed"],100)
        self.assertEqual(r["variants_per_specialist_team"],10)
        self.assertEqual(r["actual_independently_running_new_LLM_agents"],0)
        experts=r["100_separately_evaluated_model_experts"]
        self.assertEqual(len(experts),100)
        self.assertEqual(len({x["agent_id"] for x in experts}),100)
        self.assertEqual(len({(x["family"],x["variant"]) for x in experts}),100)
        sig={tuple(row["risk"] for row in expert["historical_risk_scores_not_AICS"]) for expert in experts}
        self.assertEqual(len(sig),100)
        self.assertTrue(all(len(expert["historical_risk_scores_not_AICS"])==18 for expert in experts))

    def test_five_distinct_family_champions_selected_and_fused(self):
        r=self.output
        top=r["five_selected_unique_architecture_experts"]
        self.assertEqual(len(top),5)
        self.assertEqual(len({x["agent_id"] for x in top}),5)
        self.assertEqual(len({x["family"] for x in top}),5)
        self.assertEqual(top[0]["family"],"one_month_market_shock_analyst")
        self.assertEqual(top[0]["variant"],8)
        self.assertEqual(len(r["family_champions"]),10)
        self.assertTrue(r["selection_uses_same_historical_outcomes_as_reported_performance"])
        self.assertTrue(r["selection_is_posthoc_100_candidate_multiple_testing"])

    def test_both_ensemble_arithmetic_fusions_have_real_history(self):
        r=self.output
        rows=r["monthly_five_champion_shadow"]
        self.assertEqual(len(rows),24)
        eligible=[x for x in rows if x["model_eligible_source"]]
        self.assertEqual(len(eligible),18)
        self.assertEqual(eligible[0]["month"],"2025-02")
        self.assertEqual(eligible[-1]["month"],"2026-07")
        self.assertTrue(all(x["mean_five_shadow_risk_NOT_AICS"] is not None
                            and x["median_five_shadow_risk_NOT_AICS"] is not None
                            and x["AICS_production_score"] is None for x in eligible))
        self.assertTrue(all(x["mean_five_shadow_risk_NOT_AICS"] is None
                            for x in rows[-3:]))
        self.assertEqual(r["most_recent_ensemble_eligible_month"],"2026-07")

    def test_historical_5pct_auc_positive_but_not_predictive_validated(self):
        r=self.output
        metrics=[x for x in r["actual_sp500_hindsight_metrics"]
                 if x["minimum_future_month_close_drawdown_pct"]==5]
        self.assertEqual([x["n"] for x in metrics],[18,18,15])
        self.assertEqual([x["observed_positive_month_labels"] for x in metrics],[2,3,3])
        median=[x["hindsight_AUC_by_variant"]["five_experts_robust_median"] for x in metrics]
        self.assertEqual(median,[0.625,0.533333,0.583333])
        self.assertTrue(r["selection_validation_failed_independent_OOS"])
        self.assertIsNone(r["new_model_superior_forecast_skill_proven"])
        self.assertFalse(r["approved_trades_created"])

    def test_proper_negative_control_mean_fusion_loses_to_original(self):
        metrics=[x for x in self.output["actual_sp500_hindsight_metrics"]
                 if x["minimum_future_month_close_drawdown_pct"]==5]
        self.assertTrue(all(
            x["hindsight_AUC_by_variant"]["five_experts_unweighted_mean"]
            < x["hindsight_AUC_by_variant"]["official_still_unapproved_legacy_fixed_cohort"]
            for x in metrics
        ))
        self.assertGreater(self.output["high_pairwise_correlation_selected_expert_pairs_ge_0_98"],0)

    def test_no_crisis_events_no_auc_and_no_false_11node_score(self):
        r=self.output
        ten=[x for x in r["actual_sp500_hindsight_metrics"]
             if x["minimum_future_month_close_drawdown_pct"]==10]
        self.assertEqual([x["observed_positive_month_labels"] for x in ten],[0,0,0])
        self.assertTrue(all(all(z is None for z in x["hindsight_AUC_by_variant"].values())
                            for x in ten))
        self.assertTrue(r["primary_crisis_10pct_auc_all_UNDEFINED"])
        self.assertTrue(r["original_11_node_weights_1050_unchanged"])
        self.assertTrue(r["original_hot_multiplier_and_450_500_thresholds_unchanged"])
        self.assertEqual(r["independently_historical_PIT_certified_nodes"],0)
        self.assertIsNone(r["approved_live_AICS_index"])

    def test_future_market_feature_not_used_to_construct_past_model(self):
        v=copy.deepcopy(self.v51)
        a,_,original=source_rows(v)
        v["24_month_same_source_model_comparison"][-1]["same_month_SP500_close_source_observed"]="5"
        b,_,new=source_rows(v)
        self.assertEqual(original,new)
        self.assertIsNone(a[-1]["fixed_cohort_breadth_legacy_normalized_NOT_AICS"])
        with self.assertRaises(ValueError):
            candidate_score(100,1,original[3])

    def test_refuse_source_lineage_promotion_and_fake_node_data(self):
        v=copy.deepcopy(self.v51)
        v["full_11node_AICS"]=500
        with self.assertRaises(ValueError):
            run(v)
        v=copy.deepcopy(self.v51)
        v["historical_independent_first_provider_delivery_verified"]=True
        with self.assertRaises(ValueError):
            run(v)
        v=copy.deepcopy(self.v51)
        v["24_month_same_source_model_comparison"][-1][
            "matched_same_original_3BDC_source_family"]=True
        with self.assertRaises(ValueError):
            run(v)


if __name__=="__main__":
    unittest.main()
