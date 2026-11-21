"""AICS 24m bounds are arithmetic only, not fabricated index observations."""
import copy
import json
import unittest
from scripts.aics_24m_known_weight_bounds import INPUT, OUTPUT, build


class NoMultiplier24mBoundsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.coverage=json.loads(INPUT.read_text(encoding="utf-8"))
        cls.bounds=build(cls.coverage)

    def test_panel_matches_committed_receipt(self):
        self.assertEqual(self.bounds, json.loads(OUTPUT.read_text(encoding="utf-8")))
        self.assertEqual(len(self.bounds["rows"]),24)
        self.assertEqual(self.bounds["weights_total"],1050)

    def test_missing_ai_equities_range_not_score(self):
        last=self.bounds["rows"][-1]
        self.assertEqual(last["month"],"2026-10")
        self.assertEqual(last["known_nodes"],10)
        self.assertEqual(last["missing_nodes"],["AI Equities"])
        self.assertEqual(last["known_contribution_lower_bound"],"453.17")
        self.assertEqual(last["arithmetic_upper_bound_if_all_missing_scores_were_100"],"553.17")
        self.assertEqual(last["arithmetic_band_width"],"100")
        self.assertIsNone(last["actual_complete_aics"])
        self.assertIsNone(last["actual_aics_minus_sp500_spread"])

    def test_no_imputation_for_first_month(self):
        first=self.bounds["rows"][0]
        self.assertEqual(first["known_nodes"],0)
        self.assertEqual(first["unknown_total_node_weight"],1050)
        self.assertEqual(first["known_contribution_lower_bound"],"0.00")
        self.assertEqual(first["arithmetic_upper_bound_if_all_missing_scores_were_100"],"1050.00")
        self.assertIsNone(first["actual_complete_aics"])

    def test_no_retroactive_score_promotion(self):
        altered=copy.deepcopy(self.coverage)
        altered["monthly"][-1]["full_11_node_aics_no_multiplier"]=453.17
        with self.assertRaisesRegex(ValueError,"duplicated"):
            build(altered)

    def test_rounding_tamper_rejected(self):
        altered=copy.deepcopy(self.coverage)
        altered["monthly"][-1]["partial_known_weighted_points_not_aics"]="453.16"
        with self.assertRaisesRegex(ValueError,"rounding drift"):
            build(altered)


if __name__=="__main__":
    unittest.main()
