"""PIT100 ex-post lead/lag only; no synthetic user-visible market observations."""
from __future__ import annotations
import copy
import unittest
from scripts.aics_pit100_24m_expost_leadlag_diagnostic import compare,pearson
from scripts.aics_pit100_reconcile_24m_sp500 import reconcile
from scripts.aics_pit100_rebuild_24m_research import build as simple_build
from scripts.aics_pit100_rebuild_24_month_public_filing_panel import build as rich_build,SP500
from scripts.aics_pit_100_real_cutoff_agents import (
    build as pit_build,read_bytes,OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,TERMS,FUNDING,STATUS,
)
from scripts.aics_early_imbalance_cashflow_shadow import (
    build as cash_build,read,Y2025,Q42025,Q12026,Q22026,Q32026,
)


class ResearchOnlyLeadLagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inputs=[read_bytes(x) for x in
                (OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,TERMS,FUNDING,STATUS)]
        cash=cash_build(read(Y2025),read(Q42025),read(Q22026),
                        read(Q32026),q1=read(Q12026),as_of="2026-11-22")
        pit=pit_build(*inputs,cash,as_of="2026-11-22")
        sp=read_bytes(SP500)
        simple=simple_build(*inputs,pit)
        cls.rich=rich_build(inputs[0],inputs[1],sp,pit,as_of="2026-11-22")
        cls.rec=reconcile(simple,cls.rich,sp)

    def test_first_month_cohort_is_constant_across_24_months_and_expost(self):
        report=compare(self.rec,self.rich)
        self.assertEqual(report["monthly_research_observations"],24)
        self.assertEqual(report["potential_next_month_outcome_months"],23)
        self.assertGreaterEqual(report["matched_complete_first_cohort_forward_returns"],6)
        self.assertEqual(report["historical_source_cohort_fixed_from_first_month_only"],
                         sorted(self.rich["monthly_rebuilt_panels"]["market"][0]["event_source_scores"]))
        self.assertEqual(report["independent_24m_out_of_sample_forecast_labels"],0)
        self.assertFalse(report["2000_2008_crisis_onset_lead_time_certified"])
        self.assertIsNone(report["full_11node_AICS"])
        self.assertIsNone(report["full_AICS_SP500_spread"])
        self.assertFalse(report["production_trades_created"])
        self.assertTrue(report["SP500_following_month_returns_used_only_as_targets"])
        self.assertTrue(report["correlations_are_EXPOST_not_independent_forecast_skill"])
        rows=report["monthly_diagnostics"]
        self.assertEqual(rows[0]["month"],"2024-11")
        self.assertIsNone(rows[-1]["SP500_following_month_return_pct_expost_NOT_AN_INPUT"])
        self.assertEqual(len({tuple(r["fixed_first_month_research_node_cohort"]) for r in rows}),1)
        for k in (
            "descriptive_correlation_risk_vs_following_month_SP500_return_pearson",
            "descriptive_correlation_risk_vs_following_month_SP500_return_spearman",
            "negative_control_same_month_SP500_return_pearson",
        ):
            if report[k] is not None:
                self.assertTrue(-1<=report[k]<=1)

    def test_forged_production_index_or_misaligned_SP500_month_rejected(self):
        rec=copy.deepcopy(self.rec)
        rec["full_11node_AICS"]=499
        with self.assertRaises(ValueError):compare(rec,self.rich)
        rich=copy.deepcopy(self.rich)
        rich["independently_historical_PIT_first_delivery_certified"]=True
        with self.assertRaises(ValueError):compare(self.rec,rich)
        rec=copy.deepcopy(self.rec)
        rec["monthly_aligned_research_panel"][2]["market_cutoff_date"]="2030-01-01"
        with self.assertRaises(ValueError):compare(rec,self.rich)
        rec=copy.deepcopy(self.rec)
        rec["monthly_aligned_research_panel"][1]["sp500_same_month_return_pct_retrieved_expost"]="999"
        with self.assertRaises(ValueError):compare(rec,self.rich)

    def test_missing_fixed_initial_cohort_node_is_not_imputed(self):
        r=copy.deepcopy(self.rich)
        first=sorted(r["monthly_rebuilt_panels"]["market"][0]["event_source_scores"])[0]
        r["monthly_rebuilt_panels"]["market"][4]["event_source_scores"].pop(first)
        x=compare(self.rec,r)
        self.assertFalse(x["monthly_diagnostics"][4]["fixed_cohort_original_source_available_all"])
        self.assertIsNone(x["monthly_diagnostics"][4]["fixed_cohort_normalized_research_score_0_100_NOT_AICS"])
        self.assertLess(x["matched_complete_first_cohort_forward_returns"],23)

    def test_pearson_flat_and_undersampled_means_no_skill(self):
        self.assertIsNone(pearson([1,2],[1,2]))
        self.assertIsNone(pearson([1]*12,list(range(12))))
        self.assertAlmostEqual(pearson([1,2,3,4,5,6],[2,4,6,8,10,12]),1.0)

if __name__=="__main__":
    unittest.main()
