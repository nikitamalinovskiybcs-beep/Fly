"""Source-compare Nov20 post-roster OHLC without claiming certified market PIT."""
import copy
import json
import unittest
from scripts.aics_ai_equities_nov20_cross_vendor_replay import SOURCE, OLDER, calculate


class Nov20PostRosterSourceCrosscheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt=json.loads(SOURCE.read_text(encoding="utf-8"))
        cls.older=json.loads(OLDER.read_text(encoding="utf-8"))

    def test_exact_seven_decliners_and_frozen_reconciliation(self):
        x=calculate(self.receipt,self.older)
        self.assertEqual(x["seven_decliners"],7)
        self.assertEqual(x["equity_stress_research_only"],"100.00")
        self.assertEqual(x["mean_intraday_return_pct"],"-5.959674")
        self.assertEqual(x["market_session"],"2026-11-20")
        self.assertIsNone(x["historical_24m_composite"])
        self.assertIsNone(x["aics_sp500_historical_spread"])
        self.assertFalse(x["official_exchange_original_pit"])

    def test_no_wrong_symbol_or_missing_member(self):
        x=copy.deepcopy(self.receipt)
        x["original_ohlc_rows"][6]["symbol"]="AAPL"
        with self.assertRaisesRegex(ValueError,"Seven predeclared"):
            calculate(x,self.older)

    def test_revised_price_cannot_silently_enter(self):
        x=copy.deepcopy(self.receipt)
        x["original_ohlc_rows"][0]["close"]="150.00"
        with self.assertRaisesRegex(ValueError,"OHLC mismatch"):
            calculate(x,self.older)

    def test_no_forged_ex_post_original_pit(self):
        x=copy.deepcopy(self.receipt)
        x["caveats"]["independently_certified_pit"]=True
        with self.assertRaisesRegex(ValueError,"forged certification"):
            calculate(x,self.older)

    def test_no_forged_source_hash(self):
        x=copy.deepcopy(self.receipt)
        x["original_ohlc_rows"][0]["source_original_bytes_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"provenance"):
            calculate(x,self.older)

    def test_prior_research_scores_cannot_be_rewritten(self):
        x=copy.deepcopy(self.older)
        x["expected"]["ai_equities_score"]="85.71"
        with self.assertRaisesRegex(ValueError,"frozen release"):
            calculate(self.receipt,x)


if __name__=="__main__":
    unittest.main()
