"""Nasdaq 2026 month-end seven-name shadow must never enter historic AICS."""
import copy
import unittest

from scripts.aics_ai_equities_2026q3_retro_shadow import validate_receipt


class AIEquitiesRetrospectiveQ3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=validate_receipt()

    def test_replay_observed_month_end_research_breadth(self):
        got=self.rows
        self.assertEqual([(x["month"],x["score"]) for x in got],
                         [("2026-08","71.43"),("2026-09","57.14"),("2026-10","57.14")])
        self.assertEqual([x["conditional_research_score"] for x in got],
                         ["320.52","305.48","510.31"])
        self.assertFalse(got[0]["is_conditional_11_node_scenario"])
        self.assertFalse(got[1]["is_conditional_11_node_scenario"])
        self.assertTrue(got[2]["is_conditional_11_node_scenario"])
        self.assertTrue(all(x["actual_historical_aics"] is None for x in got))
        self.assertTrue(all(x["actual_historical_spread_vs_sp500"] is None for x in got))
        self.assertTrue(all(x["eligible_original_month_pit"] is False for x in got))

    def test_decliner_without_original_companion_rejected(self):
        from scripts.aics_ai_equities_2026q3_retro_shadow import RECORD
        import json
        bad=json.loads(RECORD.read_text(encoding="utf-8"))
        bad["observations"][2]["decliners"].append("MU")
        with self.assertRaisesRegex(ValueError,"Breadth score"):
            validate_receipt(data=bad)

    def test_no_retroactive_score_promotion(self):
        from scripts.aics_ai_equities_2026q3_retro_shadow import RECORD
        import json
        bad=json.loads(RECORD.read_text(encoding="utf-8"))
        bad["original_score_coverage_panel_promotion"]=True
        with self.assertRaisesRegex(ValueError,"promoted"):
            validate_receipt(data=bad)
        bad=json.loads(RECORD.read_text(encoding="utf-8"))
        bad["approved_historical_constituency"]=True
        with self.assertRaisesRegex(ValueError,"promoted"):
            validate_receipt(data=bad)

    def test_wrong_source_digest_rejected(self):
        from scripts.aics_ai_equities_2026q3_retro_shadow import RECORD
        import json
        bad=json.loads(RECORD.read_text(encoding="utf-8"))
        bad["original_archive"]["original_json_sha256"]["NVDA"]="0"*64
        with self.assertRaisesRegex(ValueError,"source hash"):
            validate_receipt(data=bad)

    def test_no_backdated_month_end_observation(self):
        from scripts.aics_ai_equities_2026q3_retro_shadow import RECORD
        import json
        bad=json.loads(RECORD.read_text(encoding="utf-8"))
        bad["observations"][2]["last_trading_session"]="2026-10-31"
        with self.assertRaisesRegex(ValueError,"market session"):
            validate_receipt(data=bad)

    def test_no_fake_complete_historical_index(self):
        from scripts.aics_ai_equities_2026q3_retro_shadow import COVERAGE
        import json
        bad=json.loads(COVERAGE.read_text(encoding="utf-8"))
        bad["monthly"][-1]["full_11_node_aics_no_multiplier"]=510.31
        with self.assertRaisesRegex(ValueError,"mutated"):
            validate_receipt(coverage=bad)


if __name__=="__main__":
    unittest.main()
