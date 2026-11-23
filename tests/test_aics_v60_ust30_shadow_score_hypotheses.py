"""V60 tests: original ALFRED/UST source observations vs research shadow score.

Neither two research normalizers nor their conditional AICS intervals are official
AICS node scores or actual backdated PIT estimates.
"""
from __future__ import annotations
import copy
import json
import unittest

from scripts.aics_v60_ust30_shadow_score_hypotheses import (
    SOURCE_V18, SOURCE_DGS30, SOURCE_VOL, build,
    _bounds_from_assumption, _positive, _pct,
)


class AICS60USTObservationsShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overlay=json.loads(SOURCE_V18.read_text())
        cls.panel=json.loads(SOURCE_DGS30.read_text())
        cls.vol=json.loads(SOURCE_VOL.read_text())
        cls.result=build(cls.overlay,cls.panel,cls.vol)

    def test_twenty_four_real_historical_already_collected_ust_and_treasury_volatility(self):
        r=self.result
        self.assertEqual(r["research_source_months"],24)
        self.assertTrue(r["original_DGS30_and_SOFR_24m_source_dates_matched"])
        self.assertEqual(r["original_Treasury_volatility_20_daily_returns_observed_months"],24)
        self.assertEqual(r["month_count_with_VolPlusRise_hypothesis"],23)
        self.assertFalse(r["historically_original_publisher_delivery_PIT_proven"])
        self.assertFalse(r["frozen_original_UST30_node_score_method_found_and_certified"])
        self.assertTrue(r["normalization_10bp_and_50bp_thresholds_NOT_trained_or_preregistered"])

    def test_real_october_yield_spread_vol_and_signed_monthly_change(self):
        r=self.result["observed_months_and_hypothetical_score_stress_tests"][-1]
        self.assertEqual(r["month"],"2026-10")
        self.assertEqual(r["original_ALFRED_DGS30_yield_percent"],"5.32")
        self.assertEqual(r["original_ALFRED_SOFR_percent"],"3.94")
        self.assertEqual(r["original_DGS30_minus_SOFR_bp_NOT_term_premium"],"138.00")
        self.assertEqual(r["source_verified_20_daily_change_sd_bp"],"4.98")
        self.assertEqual(r["observed_month_over_month_DGS30_rise_bp"],"-27.00")
        self.assertEqual(r["candidate_Vol10_risk_proxy_0_100_NOT_OFFICIAL"],49.8)
        self.assertEqual(r["candidate_VolPlusRise_risk_proxy_0_100_NOT_OFFICIAL"],24.9)

    def test_conditional_october_volatility_hypothesis_not_canonical_aics(self):
        oct=self.result["Oct_2026_hypothesis_intervals"]
        a=oct["Vol10"]
        b=oct["VolPlusRise"]
        self.assertEqual([a["lower_conditional_research_AICS_NOT_CERTIFIED"],
                          a["upper_conditional_research_AICS_NOT_CERTIFIED"]],[396.76,689.83])
        self.assertEqual([b["lower_conditional_research_AICS_NOT_CERTIFIED"],
                          b["upper_conditional_research_AICS_NOT_CERTIFIED"]],[359.41,649.36])
        self.assertEqual(a["remaining_unobserved_original_nodes"],["AI Equities","Repo"])
        self.assertEqual(a["remaining_unknown_weight"],200)
        self.assertTrue(a["still_includes_below_450_and_above_500"])
        self.assertTrue(b["still_includes_below_450_and_above_500"])
        self.assertIsNone(a["official_AICS"])
        self.assertIsNone(b["official_AICS"])
        self.assertEqual(self.result["prior_V59_conditional_Oct_2026"],[322.06,801.07])

    def test_original_month_one_missing_prior_yield_is_not_backfilled(self):
        first=self.result["observed_months_and_hypothetical_score_stress_tests"][0]
        self.assertEqual(first["month"],"2024-11")
        self.assertEqual(first["source_verified_20_daily_change_sd_bp"],"7.22")
        self.assertEqual(first["candidate_Vol10_risk_proxy_0_100_NOT_OFFICIAL"],72.2)
        self.assertIsNone(first["candidate_VolPlusRise_risk_proxy_0_100_NOT_OFFICIAL"])
        self.assertIsNone(first["observed_month_over_month_DGS30_rise_bp"])
        self.assertIsNone(first["conditional_if_shadows_replaced_missing_UST"]["VolPlusRise"])

    def test_all_years_remain_unidentified_at_official_450_500_thresholds(self):
        r=self.result
        self.assertEqual(r["hypothesis_scenarios_with_conclusive_trading_regime_in_24m"],
                         {"Vol10":0,"VolPlusRise":0})
        self.assertTrue(all(x["original_unscored_UST_30Y_remains_missing"] for x in
                            r["observed_months_and_hypothetical_score_stress_tests"]))
        self.assertTrue(all(x["official_11node_AICS"] is None for x in
                            r["observed_months_and_hypothetical_score_stress_tests"]))
        self.assertIsNone(r["historical_full_11node_AICS"])
        self.assertEqual(r["independently_certified_AICS_nodes"],0)
        self.assertEqual(r["all_11_weights_total"],1050)
        self.assertIsNone(r["production_signal_or_trade"])
        self.assertTrue(r["readiness_22_of_66_unchanged"])

    def test_changed_or_post_dated_source_calendar_fails_closed(self):
        p=copy.deepcopy(self.panel)
        p["public_series_observations"][-1]["dgs30_observation_date"]="2026-10-30"
        with self.assertRaisesRegex(ValueError,"date mismatch"):
            build(self.overlay,p,self.vol)
        p=copy.deepcopy(self.panel)
        p["public_series_observations"][-1]["dgs30_pct"]="5.33"
        with self.assertRaisesRegex(ValueError,"arithmetic mismatch"):
            build(self.overlay,p,self.vol)
        p=copy.deepcopy(self.panel)
        p["public_series_observations"][-1]["sofr_pct"]="5.32"
        with self.assertRaisesRegex(ValueError,"arithmetic mismatch"):
            build(self.overlay,p,self.vol)

    def test_no_source_lineage_promotions(self):
        p=copy.deepcopy(self.panel)
        p["stress_scores"]["UST 30Y"]=52.0
        with self.assertRaisesRegex(ValueError,"Only original unscored"):
            build(self.overlay,p,self.vol)
        p=copy.deepcopy(self.panel)
        p["independent_provider_historical_release_proven"]=True
        with self.assertRaises(ValueError):
            build(self.overlay,p,self.vol)
        v=copy.deepcopy(self.vol)
        v["untouched_oos"]=True
        with self.assertRaises(ValueError):
            build(self.overlay,self.panel,v)

    def test_independent_existing_original_source_sha_receipt_required(self):
        with self.assertRaisesRegex(ValueError,"SHA changed"):
            build(self.overlay,self.panel,self.vol,actual_sha={
                str(SOURCE_DGS30):"a"*64,
                str(SOURCE_VOL):"b"*64,
            })
        with self.assertRaises(ValueError):
            build(self.overlay,self.panel,self.vol,actual_sha={})

    def test_clipping_and_overflow_invalid_source_stop(self):
        self.assertEqual(_positive("0.00"),0)
        self.assertEqual(_pct("5.32"),_positive("5.32"))
        with self.assertRaises(ValueError):
            _pct("40.0")
        with self.assertRaises(ValueError):
            _positive("NaN")
        with self.assertRaises(ValueError):
            _positive("-1")
        with self.assertRaises(ValueError):
            _positive("invalid")
        with self.assertRaises(ValueError):
            _positive(None)

if __name__=="__main__":
    unittest.main()
