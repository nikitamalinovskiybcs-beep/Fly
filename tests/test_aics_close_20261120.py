"""Fail-closed checks for 20 November 2026 current-equity research rollover."""
import copy
import json
import unittest

from scripts.aics_close_20261120 import RECEIPT, BASE_RELEASE, calculate


class November20CloseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(RECEIPT.read_text(encoding="utf-8"))
        cls.base = json.loads(BASE_RELEASE.read_text(encoding="utf-8"))

    def test_all_eleven_reconcile_but_are_not_certified(self):
        result = calculate(self.data, self.base)
        self.assertEqual(result["research_aics"], "669.09")
        self.assertEqual(result["change_vs_2026_11_19"], "0.00")
        self.assertEqual(result["basket_return_open_to_close_pct"], "-5.959674")
        self.assertEqual(result["declining_securities"], 7)
        self.assertEqual(result["hot_nodes"], 5)
        self.assertEqual(len(result["nodes"]), 11)
        self.assertEqual(sum(x["weight"] for x in result["nodes"]), 1050)
        self.assertEqual(sum(x["input_status"] == "CARRIED FROM 2026-11-18"
                             for x in result["nodes"]), 10)
        self.assertIsNone(result["certified_aics"])
        self.assertFalse(result["trades_created"])

    def test_one_close_modified_rejected_even_if_breadth_unchanged(self):
        changed = copy.deepcopy(self.data)
        changed["observations"][0]["close"] = "125.54"
        with self.assertRaisesRegex(ValueError, "reconcile"):
            calculate(changed, self.base)

    def test_absent_security_and_wrong_source_rejected(self):
        missing = copy.deepcopy(self.data)
        missing["observations"].pop()
        with self.assertRaisesRegex(ValueError, "roster"):
            calculate(missing, self.base)
        changed = copy.deepcopy(self.data)
        changed["observations"][0]["source_url"] = "https://example.com/"
        with self.assertRaisesRegex(ValueError, "source"):
            calculate(changed, self.base)

    def test_source_vintage_must_not_be_backdated(self):
        changed = copy.deepcopy(self.data)
        changed["rollover"]["non_equity_inputs_from"] = "2026-11-20"
        with self.assertRaisesRegex(ValueError, "vintage"):
            calculate(changed, self.base)

    def test_cannot_promote_research_to_certified(self):
        changed = copy.deepcopy(self.data)
        changed["certified_aics"] = 669.09
        with self.assertRaisesRegex(ValueError, "certified"):
            calculate(changed, self.base)


if __name__ == "__main__":
    unittest.main()
