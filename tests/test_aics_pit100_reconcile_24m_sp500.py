"""PIT100 independent month-by-month reconciliation and SPX context tests."""
from __future__ import annotations
import copy
import unittest
from scripts.aics_pit100_reconcile_24m_sp500 import reconcile,markdown_report
from scripts.aics_pit100_rebuild_24m_research import build as simple_build
from scripts.aics_pit100_rebuild_24_month_public_filing_panel import build as rich_build,SP500
from scripts.aics_pit_100_real_cutoff_agents import (
    build as pit_build,read_bytes,OVERLAY,CREDIT,REGISTRY,REPO,
    EQUITIES,TERMS,FUNDING,STATUS,
)
from scripts.aics_early_imbalance_cashflow_shadow import (
    build as cash_build,read,Y2025,Q42025,Q12026,Q22026,Q32026,
)


class IndependentPIT100MonthlyReconcilation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs=[read_bytes(f) for f in
                    (OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,TERMS,FUNDING,STATUS)]
        cls.sp500=read_bytes(SP500)
        cash=cash_build(read(Y2025),read(Q42025),read(Q22026),
                        read(Q32026),q1=read(Q12026),as_of="2026-11-22")
        cls.pit=pit_build(*cls.inputs,cash,as_of="2026-11-22")
        cls.simple=simple_build(*cls.inputs,cls.pit)
        cls.rich=rich_build(cls.inputs[0],cls.inputs[1],cls.sp500,
                            cls.pit,as_of="2026-11-22")

    def test_24_months_independently_reconciled_and_no_production_scores(self):
        x=reconcile(self.simple,self.rich,self.sp500)
        self.assertEqual(x["research_months_reconciled"],24)
        self.assertEqual(x["independent_replay_methods_compared"],2)
        self.assertEqual(x["month_node_disagreements_remaining"],0)
        self.assertEqual(len(x["monthly_aligned_research_panel"]),24)
        self.assertEqual(x["monthly_aligned_research_panel"][-1]["month"],"2026-10")
        self.assertEqual(x["quality_by_panel"]["market"]["last_month_known_weight"],725)
        self.assertEqual(x["quality_by_panel"]["calendar"]["last_month_known_weight"],950)
        self.assertTrue(all(r["full_11node_AICS"] is None for r in x["monthly_aligned_research_panel"]))
        self.assertTrue(all(r["AICS_SP500_spread"] is None for r in x["monthly_aligned_research_panel"]))
        self.assertIsNone(x["forecast_accuracy_or_2000_2008_similarity_pct"])
        self.assertEqual(x["independently_certified_historical_PIT_nodes"],0)
        self.assertFalse(x["trades_created"])
        self.assertIn("2025-12",markdown_report(x))
        self.assertIn("S&P 500",markdown_report(x))

    def test_fed_g17_joint_two_original_measurements_preserved_both_methods(self):
        x=reconcile(self.simple,self.rich,self.sp500)
        joint=x["validated_joint_G17_original_release"]
        self.assertEqual(joint["official_publication_date"],"2025-12-23")
        self.assertEqual(joint["observation_months"],["2025-10","2025-11"])
        self.assertEqual(joint["values"],["74.70","74.40"])
        self.assertEqual(joint["latest_research_monthly_candidate"],"74.40")
        self.assertTrue(joint["separate_original_measurements_not_conflicting_publications"])
        self.assertFalse(joint["historical_original_first_provider_feed_receipt_attested"])
        self.assertEqual(x["G17_research_source_period_conflicts_remaining"],0)
        for mode in ("market","calendar"):
            s=next(v for v in self.simple[mode+"_monthly_rebuilt"] if v["month"]=="2025-12")
            b=next(v for v in self.rich["monthly_rebuilt_panels"][mode] if v["month"]=="2025-12")
            self.assertEqual(s["node_scores_rebuilt_from_original_events"]["Semiconductors Supply"]["research_score_not_PIT_certified"],"74.4")
            self.assertEqual(b["event_source_scores"]["Semiconductors Supply"]["score_0_100_research_only"],"74.4")

    def test_retrospective_sp500_is_not_reused_as_aics_feature(self):
        x=reconcile(self.simple,self.rich,self.sp500)
        self.assertFalse(x["SP500_24m_observed_closes_original_feed_PIT_certified"])
        self.assertEqual(x["monthly_aligned_research_panel"][0]["sp500_close_retrieved_expost"],"6032.38")
        self.assertIsNone(x["monthly_aligned_research_panel"][0]["sp500_same_month_return_pct_retrieved_expost"])
        self.assertEqual(x["monthly_aligned_research_panel"][-1]["sp500_close_retrieved_expost"],"7580.08")
        s=copy.deepcopy(self.sp500)
        s["points"][0]["sp500_month_end_close"]="1"
        with self.assertRaises(ValueError):reconcile(self.simple,self.rich,s)

    def test_forged_pit_promotion_or_independent_disagreement_fail_closed(self):
        for target,key,bad in (
            ("simple","fully_rebuilt_production_AICS",500),
            ("rich","full_11node_AICS",500),
            ("rich","independently_historical_PIT_first_delivery_certified",True),
        ):
            a,b=copy.deepcopy(self.simple),copy.deepcopy(self.rich)
            (a if target=="simple" else b)[key]=bad
            with self.subTest(target=target,key=key),self.assertRaises(ValueError):
                reconcile(a,b,self.sp500)
        a=copy.deepcopy(self.simple)
        a["market_monthly_rebuilt"][0]["node_scores_rebuilt_from_original_events"]["Insurers"]["research_score_not_PIT_certified"]="66"
        with self.assertRaises(ValueError):reconcile(a,self.rich,self.sp500)

if __name__=="__main__":
    unittest.main()
