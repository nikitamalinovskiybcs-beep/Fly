"""V51 actual 3-BDC quarterly model design checks; no synthetic market rows."""
from __future__ import annotations

import copy
import json
import unittest

from scripts.aics_v51_credit_magnitude_early_warning import (
    ORIGINAL,V18,SPX,WEIGHTS,original_quarter_hybrids,auc,build,table,
)


class CreditMagnitudeModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger=json.loads(ORIGINAL.read_text(encoding="utf-8"))
        cls.v18=json.loads(V18.read_text(encoding="utf-8"))
        cls.spx=json.loads(SPX.read_text(encoding="utf-8"))
        cls.report=build(cls.ledger,cls.v18,cls.spx)

    def test_7_real_3bdc_issuer_cohort_scores_no_official_change(self):
        r=self.report
        self.assertEqual(r["issuer_quarters_observed"],24)
        self.assertEqual(r["quarterly_breadth_replay_events"],7)
        self.assertEqual(r["historical_market_months_examined"],24)
        self.assertEqual(r["same_original_source_family_months_comparable"],21)
        self.assertEqual(r["same_source_months_excluded_no_2026Q2Q3_original_cohort"],3)
        self.assertTrue(r["unchanged_official_private_credit_score"])
        self.assertTrue(r["unchanged_official_AICS_11node_weights"])
        self.assertTrue(r["unchanged_official_hot_multiplier_and_450_500_thresholds"])
        self.assertIsNone(r["model_accuracy_improvement_proven"])
        self.assertIsNone(r["full_11node_AICS"])
        self.assertEqual(r["certified_AICS_nodes"],0)
        self.assertFalse(r["trades_created"])
        self.assertEqual(sum(WEIGHTS.values()),1050)

    def test_small_three_issuer_deterioration_no_longer_maps_to_100(self):
        q=original_quarter_hybrids(self.ledger)
        self.assertEqual(q["2024-Q4"]["issuer_cost_changes_percentage_points"],
                         {"ARCC":"0.40","BXSL":"0.10","OBDC":"0.10"})
        self.assertEqual(q["2024-Q4"]["breadth_legacy_score_0_100"],"100.00")
        self.assertEqual(q["2024-Q4"]["positive_shock_magnitude_0_100"],"20.00")
        self.assertEqual(q["2024-Q4"]["largest_single_issuer_positive_shock_0_100"],"40.00")
        self.assertEqual(q["2024-Q4"]["hybrid_40_30_30_shadow_0_100"],"58.00")

    def test_concentrated_large_credit_shock_is_not_masked_by_breadth(self):
        q=original_quarter_hybrids(self.ledger)
        self.assertEqual(q["2025-Q3"]["worsening_issuers"],["OBDC"])
        self.assertEqual(q["2025-Q3"]["breadth_legacy_score_0_100"],"33.33")
        self.assertEqual(q["2025-Q3"]["hybrid_40_30_30_shadow_0_100"],"53.33")
        self.assertEqual(q["2026-Q1"]["breadth_legacy_score_0_100"],"66.67")
        self.assertEqual(q["2026-Q1"]["hybrid_40_30_30_shadow_0_100"],"69.67")

    def test_crisis_event_absent_so_10pct_auc_must_be_none(self):
        r=self.report
        primary=[row for row in r["observed_real_SP500_hindsight_event_discrimination"]
                 if row["forward_minimum_month_close_drop_threshold_pct"]=="10"]
        self.assertEqual(len(primary),3)
        self.assertFalse(r["forward_10pct_crisis_target_scored"])
        self.assertTrue(all(x["observed_positive_event_months"]==0 for x in primary))
        self.assertTrue(all(x["hindsight_ROC_AUC_hybrid_shadow"] is None and
                            x["hindsight_ROC_AUC_original_breadth"] is None and
                            x["hindsight_ROC_AUC_past_3month_SP500_loss_baseline"] is None
                            for x in primary))

    def test_expost_5pct_secondary_paired_market_baseline(self):
        r=self.report
        event=[x for x in r["observed_real_SP500_hindsight_event_discrimination"]
               if x["forward_horizon_months"]==6 and
               x["forward_minimum_month_close_drop_threshold_pct"]=="5"][0]
        self.assertEqual(event["same_eligible_month_sample_size"],15)
        self.assertGreater(event["observed_positive_event_months"],0)
        self.assertTrue(event["scorable_for_crisis_discrimination"])
        for name in ("hindsight_ROC_AUC_original_breadth","hindsight_ROC_AUC_hybrid_shadow",
                     "hindsight_ROC_AUC_past_3month_SP500_loss_baseline"):
            self.assertGreaterEqual(event[name],0)
            self.assertLessEqual(event[name],1)
        self.assertTrue(event["explicitly_expost_not_out_of_sample"])
        self.assertEqual(auc([1,1,1],[True,False,False]),0.5)
        self.assertIsNone(auc([1,2,3],[False,False,False]))

    def test_exclude_months_with_unrelated_original_credit_lineage(self):
        rows=self.report["24_month_same_source_model_comparison"]
        self.assertEqual([r["month"] for r in rows[-3:]],
                         ["2026-08","2026-09","2026-10"])
        self.assertTrue(all(r["fixed_cohort_hybrid_shadow_normalized_NOT_AICS"] is None
                            and r["matched_same_original_3BDC_source_family"] is False
                            for r in rows[-3:]))

    def test_source_issuer_shift_does_not_silently_recalculate_scores(self):
        bad=copy.deepcopy(self.ledger)
        next(x for x in bad["original_issuer_quarter_observations"]
             if x["issuer"]=="BXSL" and x["quarter"]=="2024-Q4")[
             "nonaccrual_amortized_cost_pct"]="0.4"
        with self.assertRaises(ValueError):
            build(bad,self.v18,self.spx)

    def test_monthly_source_lookahead_and_false_index_rejected(self):
        bad=copy.deepcopy(self.v18)
        bad["monthly_last_weekday_market_proxy"][0]["node_scores"]["Private Credit"][
            "research_eligible_date"]="2027-01-01"
        with self.assertRaises(ValueError):
            build(self.ledger,bad,self.spx)
        bad=copy.deepcopy(self.v18)
        bad["monthly_last_weekday_market_proxy"][0]["full_aics"]=430
        with self.assertRaises(ValueError):
            build(self.ledger,bad,self.spx)

    def test_prices_checked_and_future_outcomes_not_features(self):
        bad=copy.deepcopy(self.spx)
        bad["points"][0]["sp500_month_end_close"]="-42"
        with self.assertRaises(ValueError):
            build(self.ledger,self.v18,bad)
        original_quarters,original_rows,_=table(self.ledger,self.v18,self.spx)
        modified=copy.deepcopy(self.spx)
        modified["points"][-1]["sp500_month_end_close"]="1"
        new_quarters,new_rows,_=table(self.ledger,self.v18,modified)
        self.assertEqual(original_quarters,new_quarters)
        self.assertEqual([r["fixed_cohort_hybrid_shadow_normalized_NOT_AICS"] for r in original_rows],
                         [r["fixed_cohort_hybrid_shadow_normalized_NOT_AICS"] for r in new_rows])


if __name__=="__main__":
    unittest.main()
