"""Offline real-source replay for the TWO node descriptive joint macro analysis."""
import copy
import json
import unittest

from scripts.aics_joint_ust_repo_observed_research import (
    REPO_PATH, UST_PATH, VOL_PATH, build
)


def sources():
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in (REPO_PATH, UST_PATH, VOL_PATH)]


class TestJointRealUSTRepo(unittest.TestCase):
    def test_24_real_months_without_model_scores(self):
        r = build(*sources())
        self.assertEqual(r["matched_distinct_month_ends"],24)
        self.assertEqual(r["missing_joint_months"],0)
        self.assertEqual(r["invented_or_interpolated_market_rows"],0)
        self.assertEqual(r["distinct_nodes"],["UST 30Y","Repo"])
        self.assertEqual(r["fixed_node_weights"],{"UST 30Y":125,"Repo":100})
        self.assertEqual(r["descriptive_counts"],{
            "months_dgs30_minus_sofr_gt_100bp":10,
            "months_sofr_above_iorb":5,
            "months_both":2,
            "months_both_dates":["2025-12-31","2026-10-31"]
        })
        self.assertEqual(r["rows"][-1]["month_end"],"2026-10-31")
        self.assertEqual(r["rows"][-1]["joint_source_observation_date"],"2026-10-29")
        self.assertEqual(r["rows"][-1]["dgs30_minus_sofr_bp"],138)
        self.assertEqual(r["rows"][-1]["sofr_minus_iorb_bp"],4)
        self.assertEqual(r["rows"][-1]["dgs30_20_daily_changes_sample_sd_bp"],"4.98")
        self.assertEqual(r["last_month_delta_vs_prior"],{
            "month_end":"2026-10-31","previous_month_end":"2026-09-30",
            "dgs30_minus_sofr_bp_change":-33,
            "sofr_minus_iorb_bp_change":6,
            "dgs30_20daily_sample_sd_bp_change":"0.57"
        })
        self.assertFalse(r["independent_historical_pit_attested"])
        self.assertTrue(r["all_24_months_used_for_descriptive_analysis_not_untouched_oos"])
        self.assertTrue(r["publication_proxy_only_not_independent_provider_release_attestation"])
        self.assertFalse(r["causal_stress_inference"])
        self.assertIsNone(r["historical_model_predictive_skill"])
        self.assertEqual(r["model_node_scores"],{"UST 30Y":None,"Repo":None})
        self.assertIsNone(r["index_aics"])
        self.assertEqual(r["promotion"],"BLOCKED")

    def test_changed_repo_rate_is_not_replaced_with_estimate(self):
        r,u,v=copy.deepcopy(sources())
        r["monthly_observations"][-1]["sofr_pct"]="3.95"
        with self.assertRaisesRegex(ValueError,"SOFR dates/levels"):
            build(r,u,v)

    def test_modified_treasury_curve_spread_fails(self):
        r,u,v=copy.deepcopy(sources())
        u["public_series_observations"][-1]["dgs30_minus_sofr_bps"]="200"
        with self.assertRaisesRegex(ValueError,"spread calculation"):
            build(r,u,v)

    def test_future_release_proxy_blocked(self):
        r,u,v=copy.deepcopy(sources())
        r["monthly_observations"][-1]["publication_proxy_date"]="2026-11-02"
        with self.assertRaisesRegex(ValueError,"publication proxy"):
            build(r,u,v)

    def test_missing_or_duplicated_asof_prevents_interpolation(self):
        for change in ("missing","duplicate"):
            with self.subTest(change=change):
                r,u,v=copy.deepcopy(sources())
                if change=="missing":
                    del r["monthly_observations"][0]
                else:
                    r["monthly_observations"][0]=r["monthly_observations"][1]
                with self.assertRaisesRegex(ValueError,"Incomplete|Duplicate"):
                    build(r,u,v)

    def test_risk_score_and_false_pit_promotion_blocked(self):
        for field,value in (
            ("source_release_timestamp_pit_attested",True),
            ("independent_24_month_oos",True),
            ("stress_score",72),
            ("index_aics",505),
        ):
            with self.subTest(field=field):
                r,u,v=copy.deepcopy(sources())
                r[field]=value
                with self.assertRaisesRegex(ValueError,"caveat altered"):
                    build(r,u,v)

    def test_no_synthetic_or_future_volatility_window_accepted(self):
        r,u,v=copy.deepcopy(sources())
        v["months"][-1]["last_yield_date"]="2026-11-15"
        with self.assertRaisesRegex(ValueError,"window ends"):
            build(r,u,v)


if __name__=="__main__":
    unittest.main()
