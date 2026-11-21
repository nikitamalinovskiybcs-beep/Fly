"""Original issuer 2025-Q4 SEC direct quarterly cash-flow event safety tests."""
import copy
import json
import unittest

from scripts.aics_neocloud_2025_q4_sec_original import SOURCE, calculate


class Neocloud2025Q4OriginalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_two_actual_reported_quarters_and_first_access(self):
        x=calculate(self.original)
        self.assertEqual(x["period"],"2025-Q4")
        self.assertEqual(x["available_at"],"2026-03-12")
        self.assertEqual(x["score"],"60.87")
        self.assertEqual(x["total_cfo_usd_m"],"2393.3")
        self.assertEqual(x["total_cash_purchases_usd_m"],"6116.0")
        self.assertEqual(x["cash_funding_gap_usd_m"],"3722.7")
        self.assertFalse(x["historical_pit_certified"])
        self.assertIsNone(x["full_aics"])

    def test_sec_14_day_filing_gate_cannot_be_skipped(self):
        bad=copy.deepcopy(self.original)
        bad["sources"]["CoreWeave"]["available_at"]="2026-02-26"
        with self.assertRaisesRegex(ValueError,"embargo"):
            calculate(bad)
        bad=copy.deepcopy(self.original)
        bad["sources"]["Nebius"]["filed_at"]="2026-02-09"
        with self.assertRaisesRegex(ValueError,"embargo"):
            calculate(bad)

    def test_cashflow_or_sec_issuer_tampering_blocked(self):
        for issuer, key in [("CoreWeave","cfo_quarter_usd_m"),("Nebius","cash_purchases_quarter_usd_m")]:
            bad=copy.deepcopy(self.original)
            bad["sources"][issuer][key]="9999"
            with self.assertRaisesRegex(ValueError,"mismatch"):
                calculate(bad)
        bad=copy.deepcopy(self.original)
        bad["sources"]["Nebius"]["cik"]="1769628"
        with self.assertRaisesRegex(ValueError,"embargo"):
            calculate(bad)

    def test_nebius_ongoing_operations_scope_required(self):
        bad=copy.deepcopy(self.original)
        bad["sources"]["Nebius"]["cfo_scope"]="consolidated all-group total"
        with self.assertRaisesRegex(ValueError,"continuing"):
            calculate(bad)

    def test_invalid_promotions_and_unsupported_hash_blocked(self):
        bad=copy.deepcopy(self.original)
        bad["historical_24_month_oos_verified"]=True
        with self.assertRaisesRegex(ValueError,"certification"):
            calculate(bad)
        bad=copy.deepcopy(self.original)
        bad["sources"]["CoreWeave"]["source_raw_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"embargo"):
            calculate(bad)


if __name__=="__main__":
    unittest.main()
