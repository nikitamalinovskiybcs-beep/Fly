"""V59 prove sharp 24-month AICS bounds without inventing missing nodes."""
from __future__ import annotations
import copy
import json
import unittest
from decimal import Decimal

from scripts.aics_v59_24m_uncertainty_envelope import (
    SOURCE, build, month_bound, multiplier, _region
)


class AICS59RobustMissingNodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads(SOURCE.read_text(encoding="utf-8"))
        cls.result=build(cls.source)

    def test_actual_all_24_market_months_and_zero_certified_index(self):
        r=self.result
        self.assertEqual(r["original_24_market_months"],24)
        rows=r["monthly_24m_conditional_research_envelopes"]
        self.assertEqual(rows[0]["month"],"2024-11")
        self.assertEqual(rows[-1]["month"],"2026-10")
        self.assertEqual(r["months_with_certified_full_11_node_AICS"],0)
        self.assertTrue(all(row["full_11_node_AICS"] is None for row in rows))
        self.assertEqual(r["months_with_unique_robust_trading_regime"],0)
        self.assertEqual(r["months_with_risk_both_below_entry_and_above_exit"],24)
        self.assertEqual(r["adjacent_research_months_with_certain_direction"],0)
        self.assertFalse(r["production_trades_created"])
        self.assertTrue(r["research_proxy_not_real_historical_pit"])
        self.assertTrue(r["no_probability_or_confidence_interval_claimed"])

    def test_october_2026_exact_322_062_to_801_06975_not_published_index(self):
        r=self.result["monthly_24m_conditional_research_envelopes"][-1]
        self.assertEqual(r["known_node_count"],8)
        self.assertEqual(r["known_weight"],725)
        self.assertEqual(r["missing_weight"],325)
        self.assertEqual(r["known_hot_nodes_strict_gt_60"],3)
        self.assertEqual(r["missing_nodes_not_imputed"],["AI Equities","Repo","UST 30Y"])
        self.assertEqual(Decimal(r["observed_partial_weighted_sum_exact"]),Decimal("268.385"))
        self.assertEqual(Decimal(r["conditional_index_lower_exact"]),Decimal("322.062"))
        self.assertEqual(Decimal(r["conditional_index_upper_exact"]),Decimal("801.06975"))
        self.assertEqual(r["conditional_interval_width"],479.01)
        self.assertEqual(r["conditional_full_index_lower_if_all_missing_scores_ZERO_BOUND_CASE"],322.06)
        self.assertEqual(r["conditional_full_index_upper_if_all_missing_scores_100_BOUND_CASE"],801.07)
        self.assertEqual(r["entry_450_watch_500_cash_threshold_identification"],
                         "UNDECIDABLE_INCOMPLETE_NODE_COVERAGE")
        self.assertFalse(r["independently_historical_PIT_verified"])
        self.assertIsNone(r["strict_trade_action"])

    def test_initial_24_month_record_is_wide_due_to_missing_8_of_11(self):
        first=self.result["monthly_24m_conditional_research_envelopes"][0]
        self.assertEqual(first["known_node_count"],3)
        self.assertEqual(first["known_weight"],325)
        self.assertEqual(first["missing_weight"],725)
        self.assertEqual(first["known_hot_nodes_strict_gt_60"],1)
        self.assertEqual(first["conditional_full_index_lower_if_all_missing_scores_ZERO_BOUND_CASE"],39.68)
        self.assertEqual(first["conditional_full_index_upper_if_all_missing_scores_100_BOUND_CASE"],1032.31)
        self.assertGreater(first["conditional_interval_width"],990)
        self.assertEqual(self.result["original_11_weights_total"],1050)

    def test_ust_30y_is_most_valuable_missing_node_to_resolve_in_october(self):
        latest=self.result["monthly_24m_conditional_research_envelopes"][-1]
        priorities=latest["missing_node_identification_priorities"]
        self.assertEqual(priorities[0]["unobserved_node"],"UST 30Y")
        self.assertEqual(priorities[0]["fixed_weight"],125)
        self.assertEqual(priorities[0][
            "guaranteed_at_least_interval_width_reduction_if_resolved"],169.67)
        self.assertEqual({r["unobserved_node"] for r in priorities},
                         {"AI Equities","Repo","UST 30Y"})
        self.assertEqual(priorities[1]["guaranteed_at_least_interval_width_reduction_if_resolved"],138.42)
        self.assertEqual(priorities[2]["guaranteed_at_least_interval_width_reduction_if_resolved"],138.42)
        self.assertEqual(self.result[
            "most_recent_top_missing_node_to_resolve_for_robust_interval"],"UST 30Y")

    def test_proof_multiplier_exact_and_hot_strictly_greater_than_60(self):
        self.assertEqual([multiplier(h) for h in range(12)],
                         [Decimal("1"),Decimal("1"),Decimal("1"),
                          Decimal("1.20"),Decimal("1.25"),Decimal("1.30"),
                          Decimal("1.35"),Decimal("1.35"),Decimal("1.35"),
                          Decimal("1.35"),Decimal("1.35"),Decimal("1.35")])
        self.assertEqual(_region(Decimal("449"),Decimal("449.99")),
                         "CERTAIN_ENTER_IF_RESEARCH_PROXY_VALID")
        self.assertEqual(_region(Decimal("450"),Decimal("500")),
                         "CERTAIN_WATCH_IF_RESEARCH_PROXY_VALID")
        self.assertEqual(_region(Decimal("501"),Decimal("551")),
                         "CERTAIN_EXIT_IF_RESEARCH_PROXY_VALID")
        self.assertEqual(_region(Decimal("322"),Decimal("801")),
                         "UNDECIDABLE_INCOMPLETE_NODE_COVERAGE")

    def test_all_24_published_partial_sums_match_fixed_weight_formula(self):
        for row in self.result["monthly_24m_conditional_research_envelopes"]:
            with self.subTest(month=row["month"]):
                self.assertEqual(row["known_weight"]+row["missing_weight"],1050)
                self.assertEqual(row["known_node_count"]+row["missing_node_count"],11)
                low=Decimal(row["conditional_index_lower_exact"])
                high=Decimal(row["conditional_index_upper_exact"])
                raw=Decimal(row["observed_partial_weighted_sum_exact"])
                self.assertEqual(low,raw*Decimal(str(row["lower_bound_hot_multiplier"])))
                self.assertTrue(low<=high)
                self.assertTrue(row["feasible_both_under_450_and_over_500"])
                self.assertIsNone(row["full_11_node_AICS"])

    def test_fake_expost_pit_promotion_cannot_change_model_status(self):
        altered=copy.deepcopy(self.source)
        altered["historical_pit_source_bytes_independently_attested"]=True
        with self.assertRaisesRegex(ValueError,"Never treat ex-post"):
            build(altered)
        altered=copy.deepcopy(self.source)
        altered["full_11node_index_months"]=24
        with self.assertRaisesRegex(ValueError,"Never treat ex-post"):
            build(altered)
        altered=copy.deepcopy(self.source)
        altered["production_index_changed"]=True
        with self.assertRaises(ValueError):
            build(altered)

    def test_missing_node_partition_invalid_scores_or_future_sources_rejected(self):
        row=copy.deepcopy(self.source["monthly_last_weekday_market_proxy"][-1])
        row["missing_nodes"].remove("Repo")
        with self.assertRaisesRegex(ValueError,"partition exactly"):
            month_bound(row)
        row=copy.deepcopy(self.source["monthly_last_weekday_market_proxy"][-1])
        row["node_scores"]["Neoclouds"]["score"]="150"
        with self.assertRaisesRegex(ValueError,"outside"):
            month_bound(row)
        row=copy.deepcopy(self.source["monthly_last_weekday_market_proxy"][-1])
        row["node_scores"]["Neoclouds"]["research_eligible_date"]="2027-01-01"
        with self.assertRaisesRegex(ValueError,"look-ahead"):
            month_bound(row)
        row=copy.deepcopy(self.source["monthly_last_weekday_market_proxy"][-1])
        row["partial_weighted_points_not_full_aics"]="499.99"
        with self.assertRaisesRegex(ValueError,"differs"):
            month_bound(row)

    def test_no_fake_history_backfill_and_no_calendar_shift(self):
        altered=copy.deepcopy(self.source)
        altered["monthly_last_weekday_market_proxy"].pop(5)
        with self.assertRaisesRegex(ValueError,"24 real source months"):
            build(altered)
        altered=copy.deepcopy(self.source)
        altered["monthly_last_weekday_market_proxy"][-1]["month"]="2026-11"
        with self.assertRaises(ValueError):
            build(altered)

if __name__=="__main__":
    unittest.main()
