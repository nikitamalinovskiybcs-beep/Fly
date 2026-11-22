"""V61 source-to-score threshold instability tests: no fictitious market prices.

All candidate 0-100 Repo and UST score mappings are UNAPPROVED sensitivity
rules, not the production AICS index or historical PIT availability.
"""
from __future__ import annotations
import copy
import hashlib
import json
import unittest
from decimal import Decimal

from scripts.aics_v61_repo_ai_source_to_score_model_risk import (
    V18,DGS30,VOL,REPO,AI,EQUITY_DIRECTORY,REHASH,
    build,_accept_repo,_accept_ai,_zone,_scenario
)


class AICS61OriginalRepoAIModelRiskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths=(V18,DGS30,VOL,REPO,AI,EQUITY_DIRECTORY,REHASH)
        cls.objs=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
        cls.hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        cls.report=build(*cls.objs,hashes=cls.hashes)

    def test_three_real_sources_preserved_without_promoting_old_snapshots(self):
        r=self.report
        self.assertEqual(r["real_repo_original_monthly_observations"],24)
        self.assertEqual(r["ust30_actual_monthly_observations_already"],24)
        self.assertEqual(r["real_nasdaq_equity_retro_session_months"],3)
        self.assertEqual(r["real_nasdaq_current_seven_company_directory_found"],7)
        self.assertTrue(r["AI_retro_price_retrieved_after_2026_Aug_Sep_Oct"])
        self.assertFalse(r["Repo_intraday_historical_release_independently_attested"])
        self.assertFalse(r["AI_historical_seven_member_basket_and_split_adjustments_attested"])
        self.assertFalse(r["AI_Equities_approved_old_month_price_to_score_verified"])
        self.assertFalse(r["UST_official_0_to_100_risk_node_score_found"])
        self.assertFalse(r["Repo_official_0_to_100_risk_node_score_found"])
        self.assertEqual(r["research_24m_independent_PIT_certified_nodes"],0)
        self.assertEqual(r["new_trades_created"],0)
        self.assertIsNone(r["official_full_11node_AICS"])

    def test_all_august_september_october_six_scenario_matrices(self):
        r=self.report
        months=r["three_months_2026Q3_research_model_definition_risk"]
        self.assertEqual([x["month"] for x in months],
                         ["2026-08","2026-09","2026-10"])
        self.assertEqual(r["scenarios_calculated_real_original_source_not_real_scores"],18)
        self.assertEqual([len(x["six_nonofficial_score_combinations"]) for x in months],
                         [6,6,6])
        self.assertTrue(all(x["official_full_AICS"] is None for x in months))
        self.assertTrue(all(not x["trades_created"] for x in months))
        self.assertTrue(all(x["new_approved_node_scores"]==0 for x in months))
        self.assertTrue(all(all(t["risk_if_ALL_nonapproved_shadows_assumed_NOT_REAL_AICS"] is None
                                for t in r["six_nonofficial_score_combinations"])
                            for r in months[:2]))
        self.assertTrue(all(t["still_missing_unscored_original_nodes"]==[]
                            for t in months[-1]["six_nonofficial_score_combinations"]))

    def test_october_actual_sofr_iorb_and_equity_retrospective_breadth(self):
        oct=self.report["three_months_2026Q3_research_model_definition_risk"][-1]
        self.assertEqual(oct["original_observed_SOFR_percent"],"3.94")
        self.assertEqual(oct["original_observed_IORB_percent"],"3.9")
        self.assertEqual(oct["original_observed_SOFR_minus_IORB_bp"],4)
        self.assertEqual(oct["original_observed_SOFR_minus_BGCR_bp"],2)
        self.assertEqual(oct["equity_retro_decliners_count"],4)
        self.assertEqual(oct["equity_retro_7_symbol_research_score_NOT_ELIGIBLE"],"57.14")
        self.assertEqual(oct["old_known_8_7_nodes_fixed_as_V18"],8)
        self.assertEqual(oct["conditional_old_interval"],[322.06,801.07])
        self.assertEqual(oct["old_known_hot_nodes"],3)

    def test_october_shows_even_hypothetical_ENTRY_WATCH_EXIT(self):
        oct=self.report["three_months_2026Q3_research_model_definition_risk"][-1]
        row={(x["candidate_UST_rule"],x["candidate_Repo_rule"]):x
             for x in oct["six_nonofficial_score_combinations"]}
        expected={
            ("Vol10","RepoZeroBoundary"):(465.33,"HYPOTHETICAL_WATCH_450_TO_500_NOT_ACTIONABLE"),
            ("Vol10","RepoPremium20bpPostHoc"):(489.33,"HYPOTHETICAL_WATCH_450_TO_500_NOT_ACTIONABLE"),
            ("Vol10","RepoPremium10bpPostHoc"):(513.33,"HYPOTHETICAL_CASH_GT_500_NOT_ACTIONABLE"),
            ("VolPlusRise","RepoZeroBoundary"):(427.98,"HYPOTHETICAL_ENTRY_LT_450_NOT_ACTIONABLE"),
            ("VolPlusRise","RepoPremium20bpPostHoc"):(451.98,"HYPOTHETICAL_WATCH_450_TO_500_NOT_ACTIONABLE"),
            ("VolPlusRise","RepoPremium10bpPostHoc"):(475.98,"HYPOTHETICAL_WATCH_450_TO_500_NOT_ACTIONABLE"),
        }
        self.assertEqual(set(row),set(expected))
        for pair,(score,zone) in expected.items():
            self.assertEqual(row[pair]["risk_if_ALL_nonapproved_shadows_assumed_NOT_REAL_AICS"],score)
            self.assertEqual(row[pair]["hypothetical_threshold_zone_NOT_ACTIONABLE"],zone)
            self.assertIsNone(row[pair]["official_AICS"])
            self.assertIsNone(row[pair]["trade_action"])
        self.assertEqual(oct["number_of_different_hypothetical_regions"],3)
        self.assertTrue(self.report["market_outcome_used_to_select_scenario"] is False)

    def test_ai_retro_score_is_exactly_four_over_seven_not_source_PIT(self):
        ai=self.objs[4]
        listings=self.objs[5]
        claims=_accept_ai(ai,listings)
        self.assertEqual(len(claims),3)
        self.assertEqual(claims["2026-10"]["score"],"57.14")
        self.assertEqual(sorted(claims["2026-10"]["decliners"]),
                         ["GOOGL","MSFT","NVDA","ORCL"])
        bad=copy.deepcopy(ai)
        bad["score_eligible_at_2026_10_31"]=True
        with self.assertRaises(ValueError):
            _accept_ai(bad,listings)
        bad=copy.deepcopy(ai)
        bad["observations"][-1]["score"]="58.0"
        with self.assertRaisesRegex(ValueError,"arithmetic"):
            _accept_ai(bad,listings)
        bad=copy.deepcopy(ai)
        bad["research_symbols"].append("ZZZ")
        with self.assertRaises(ValueError):
            _accept_ai(bad,listings)

    def test_24_repo_market_months_have_exact_spread_arithmetic(self):
        d=_accept_repo(self.objs[3])
        self.assertEqual(len(d),24)
        self.assertEqual(d["2026-10"]["sofr_minus_iorb_bps"],4)
        self.assertEqual(d["2026-10"]["sofr_minus_bgcr_bps"],2)
        bad=copy.deepcopy(self.objs[3])
        bad["monthly_observations"][-1]["sofr_minus_iorb_bps"]=25
        with self.assertRaisesRegex(ValueError,"arithmetic"):
            _accept_repo(bad)
        bad=copy.deepcopy(self.objs[3])
        bad["source_release_timestamp_pit_attested"]=True
        with self.assertRaises(ValueError):
            _accept_repo(bad)

    def test_month_count_and_original_official_aics_fail_closed(self):
        r=self.report
        self.assertEqual(r["months_where_posthoc_reasonable_normalizers_disagree_on_450_500_regime"],1)
        self.assertTrue(r["official_index_still_unknown_for_all_24_months"])
        self.assertTrue(r["strict_readiness_delivered_milestones_22_of_66_unchanged"])
        self.assertFalse(r["trading_approved"])
        self.assertTrue(r["new_score_normalizers_10_20_basis_points_are_post_hoc_research_only"])
        self.assertEqual(r["october_original_conditional_range"],[322.06,801.07])

    def test_raw_market_source_independent_receipt_sha_mismatch_blocks(self):
        wrong=dict(self.hashes)
        wrong[str(REPO)]="a"*64
        with self.assertRaisesRegex(ValueError,"SHA256 mismatch"):
            build(*self.objs,hashes=wrong)
        bad=copy.deepcopy(self.objs[6])
        bad["index_aics"]=500
        with self.assertRaisesRegex(ValueError,"cannot be promoted"):
            build(*self.objs[:6],bad,hashes=self.hashes)

    def test_edge_model_thresholds_strict_preserved(self):
        self.assertEqual(_zone(Decimal("449.99")),"HYPOTHETICAL_ENTRY_LT_450_NOT_ACTIONABLE")
        self.assertEqual(_zone(Decimal("450")),"HYPOTHETICAL_WATCH_450_TO_500_NOT_ACTIONABLE")
        self.assertEqual(_zone(Decimal("500")),"HYPOTHETICAL_WATCH_450_TO_500_NOT_ACTIONABLE")
        self.assertEqual(_zone(Decimal("500.01")),"HYPOTHETICAL_CASH_GT_500_NOT_ACTIONABLE")

if __name__=="__main__":
    unittest.main()
