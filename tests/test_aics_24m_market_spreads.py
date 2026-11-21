"""Dated NDX/SPX and Repo spreads cannot backfill absent eleven-node AICS."""
import copy
import unittest

from scripts.aics_24m_market_spreads import calculate, load, NDX, SPX, COVERAGE

class MarketSpreads24mTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ndx,cls.spx,cls.coverage=load(NDX),load(SPX),load(COVERAGE)

    def test_24_monthly_spreads(self):
        result=calculate(self.ndx,self.spx,self.coverage)
        self.assertEqual(len(result),24)
        self.assertEqual(result[0]["month"],"2024-11")
        self.assertEqual(result[0]["research_only_eligible_node_count"],1)
        self.assertEqual(result[0]["research_only_partial_weighted_points_not_aics"],39.35)
        self.assertEqual(result[-1]["month"],"2026-10")
        self.assertEqual(result[0]["ndx_minus_spx_cumulative_base100_pp"],0)
        self.assertIsNone(result[0]["ndx_minus_spx_monthly_return_pp"])
        self.assertAlmostEqual(result[-1]["ndx_minus_spx_cumulative_base100_pp"],9.9591,places=4)
        self.assertAlmostEqual(result[-1]["ndx_minus_spx_monthly_return_pp"],-5.721,places=3)
        self.assertEqual(result[-1]["repo_sofr_minus_iorb_bp"],4)
        self.assertEqual(result[-1]["research_only_eligible_node_count"],10)
        self.assertEqual(result[-1]["research_only_partial_weighted_points_not_aics"],453.17)
        self.assertTrue(all(x["full_historical_aics_no_multiplier"] is None for x in result))
        self.assertTrue(all(x["full_historical_aics_sp500_spread"] is None for x in result))

    def test_mismatched_historical_period_rejected(self):
        bad=copy.deepcopy(self.ndx)
        bad["points"][7]["month"]="2026-11"
        with self.assertRaisesRegex(ValueError,"misaligned"):
            calculate(bad,self.spx,self.coverage)

    def test_zero_price_rejected(self):
        bad=copy.deepcopy(self.ndx)
        bad["points"][0]["ndx_month_end_close"]="0"
        with self.assertRaisesRegex(ValueError,"Non-positive"):
            calculate(bad,self.spx,self.coverage)

    def test_promoted_aics_rejected(self):
        bad=copy.deepcopy(self.coverage)
        bad["monthly"][-1]["full_11_node_aics_no_multiplier"]=413.27
        with self.assertRaisesRegex(ValueError,"promoted"):
            calculate(self.ndx,self.spx,bad)

    def test_unsupported_pit_claim_rejected(self):
        bad=copy.deepcopy(self.ndx)
        bad["independently_contemporaneous_pit_attested"]=True
        with self.assertRaisesRegex(ValueError,"PIT"):
            calculate(bad,self.spx,self.coverage)

if __name__=="__main__":
    unittest.main()
