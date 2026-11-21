"""No-multiplier research shadow: prove live formulas and reject PIT promotion."""
import copy
import json
import unittest

from scripts.aics_ir_shadow_no_multiplier import RECORD, RELEASE, calc
from scripts.aics_close_20261120 import calculate as close_calculate


class IRNoMultiplierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record=json.loads(RECORD.read_text(encoding="utf-8"))
        cls.release=json.loads(RELEASE.read_text(encoding="utf-8"))
        cls.close=close_calculate()

    def test_index_before_after_without_hot_multiplier(self):
        got=calc(self.record,self.release,self.close)
        self.assertEqual(got["weights_sum"],1050)
        self.assertEqual(got["research_no_multiplier_prior"],"514.69")
        self.assertEqual(got["research_no_multiplier_shadow"],"528.74")
        self.assertEqual(got["research_change"],"+14.05")
        self.assertEqual(got["neoclouds_ir_scenario"],"89.83")
        self.assertEqual(got["hot_nodes"],5)
        self.assertEqual(got["legacy_research_shadow_diagnostic_only"],"687.36")
        self.assertEqual(len(got["scores"]),11)
        self.assertFalse(got["old_450_500_thresholds_valid_for_no_m"])
        self.assertIsNone(got["certified_aics"])

    def test_no_fabricated_new_q3_capex(self):
        bad=copy.deepcopy(self.record)
        bad["q3_inputs"][1]["cash_purchases"]="7299.4"
        with self.assertRaisesRegex(ValueError,"mismatched"):
            calc(bad,self.release,self.close)

    def test_no_switch_to_old_multiplier_as_default(self):
        bad=copy.deepcopy(self.record)
        bad["research_method"]="MULTIPLY_BY_HOT_NODE_COUNT"
        with self.assertRaisesRegex(ValueError,"identifiers"):
            calc(bad,self.release,self.close)

    def test_no_certification_or_retroactive_thresholds(self):
        bad=copy.deepcopy(self.record)
        bad["guardrails"]["historical_entry_watch_exit_thresholds_recalibrated"]=True
        with self.assertRaisesRegex(ValueError,"certified"):
            calc(bad,self.release,self.close)

    def test_no_missing_issuer_or_unsourced_input(self):
        bad=copy.deepcopy(self.record)
        bad["q3_inputs"].pop()
        with self.assertRaisesRegex(ValueError,"panel"):
            calc(bad,self.release,self.close)
        bad=copy.deepcopy(self.record)
        bad["q3_inputs"][0]["source_url"]="https://example.com"
        with self.assertRaisesRegex(ValueError,"Unapproved"):
            calc(bad,self.release,self.close)

    def test_legacy_scores_immutable_for_research_comparison(self):
        bad=copy.deepcopy(self.release)
        bad["first_publication"]["scores"]["Repo"]=99.0
        with self.assertRaisesRegex(ValueError,"fixed-weight"):
            calc(self.record,bad,self.close)


if __name__=="__main__":
    unittest.main()
