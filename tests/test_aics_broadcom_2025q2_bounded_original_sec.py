"""Strict >4400 actual issuer statement supports exact zero stress without exact revenue."""
import copy
import json
import unittest
from scripts.aics_broadcom_2025q2_bounded_original_sec import SOURCE, calculate

class BroadcomBounded2025Q2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_replay_strict_greater_than_proves_zero(self):
        x=calculate(self.source)
        self.assertEqual(x["period"],"2025-Q2")
        self.assertEqual(x["available_at"],"2025-06-19")
        self.assertEqual(x["score"],"0.00")
        self.assertEqual(x["guidance_usd_m"],4400)
        self.assertEqual(x["actual_strictly_greater_than_usd_m"],4400)
        self.assertIsNone(x["actual_exact_usd_m"])
        self.assertFalse(x["independently_historical_pit_certified"])
        self.assertIsNone(x["certified_full_aics"])

    def test_historical_gate_requires_both_sources_and_14_days(self):
        for which,early in [("prior_guidance_filing","2025-03-06"),("actual_filing","2025-06-05")]:
            bad=copy.deepcopy(self.source)
            bad[which]["available_at"]=early
            with self.assertRaisesRegex(ValueError,"embargo"):
                calculate(bad)

    def test_do_not_make_up_exact_actual_or_replace_strict_inequality(self):
        for field,val in (
            ("reported_actual_exact_usd_m",4401),
            ("reported_actual_relation",">="),
            ("reported_actual_lower_bound_strict_usd_m",4399)
        ):
            bad=copy.deepcopy(self.source)
            bad["actual_filing"][field]=val
            with self.assertRaisesRegex(ValueError,"strict lower-bound"):
                calculate(bad)

    def test_block_fake_pit_and_wrong_sources(self):
        bad=copy.deepcopy(self.source)
        bad["certification"]["historical_pit_certified"]=True
        with self.assertRaisesRegex(ValueError,"promotion"):
            calculate(bad)
        bad=copy.deepcopy(self.source)
        bad["prior_guidance_filing"]["source_url"]="https://example.com/not-original"
        with self.assertRaisesRegex(ValueError,"identity"):
            calculate(bad)
        bad=copy.deepcopy(self.source)
        bad["deduction"]["score"]="5.00"
        with self.assertRaisesRegex(ValueError,"score"):
            calculate(bad)

if __name__=="__main__":
    unittest.main()
