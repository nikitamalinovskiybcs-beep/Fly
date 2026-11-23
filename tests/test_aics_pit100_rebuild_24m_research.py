"""Fail-closed checks for PIT100 24-month original-event reconstruction."""
import copy
import unittest
from scripts.aics_pit100_rebuild_24m_research import build,replay,event_roster
from scripts.aics_pit_100_real_cutoff_agents import (
    read_bytes,OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,TERMS,FUNDING,STATUS,
)
from scripts.aics_pit_100_real_cutoff_agents import build as build100
from scripts.aics_early_imbalance_cashflow_shadow import (
    build as cash_build,read,Y2025,Q42025,Q12026,Q22026,Q32026,
)

class RebuildOriginalEventMonthPanels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=[read_bytes(p) for p in
                  (OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,TERMS,FUNDING,STATUS)]
        cash=cash_build(read(Y2025),read(Q42025),read(Q22026),read(Q32026),
                        q1=read(Q12026),as_of="2026-11-22")
        cls.pit100=build100(*cls.data,cash,as_of="2026-11-22")

    def test_rebuild_all_24x2_from_source_events(self):
        result=build(*self.data,self.pit100)
        self.assertEqual(result["historical_months"],24)
        self.assertTrue(result["active_SEC_public_filing_date_no_14day_delay"])
        self.assertEqual(result["reclocked_original_events"],
                         len(self.data[0]["source_events"])+len(self.data[1]["source_events"]))
        for field in ("market_monthly_rebuilt","calendar_monthly_rebuilt"):
            rows=result[field]
            self.assertEqual(len(rows),24)
            self.assertEqual(len({x["month"] for x in rows}),24)
            self.assertTrue(all(x["full_11node_AICS"] is None for x in rows))
            self.assertTrue(all(x["AICS_SP500_spread"] is None for x in rows))
            self.assertTrue(all(x["known_weight_research_only"]<=1050 for x in rows))
            self.assertTrue(all(x["known_node_count_research_only"]+
                                len(x["missing_nodes"])==11 for x in rows))
        self.assertEqual(result["newly_certified_PIT_nodes"],0)
        self.assertFalse(result["24month_independent_OOS"])
        self.assertFalse(result["trades_created"])

    def test_calendar_and_market_are_different_on_same_day_original_sec(self):
        roster=event_roster(*self.data[:2])
        sec=next(x for x in roster if x["source_kind"]=="SEC_FILED_DATE_ONLY")
        filing=sec["filing_or_release_date"]
        # Explicitly check rebuilt market month event cannot see filing
        # at the same cutoff, calendar end can use filing-day date proxy.
        from scripts.aics_pit_100_real_cutoff_agents import eligible,date
        self.assertTrue(eligible(filing,date(filing),market_close=False))
        self.assertFalse(eligible(filing,date(filing),market_close=True))
        self.assertEqual(len(replay(*self.data[:2],market=True)),24)
        self.assertEqual(len(replay(*self.data[:2],market=False)),24)

    def test_original_source_mutation_or_forged_100_runs_fail(self):
        fake=copy.deepcopy(self.pit100)
        fake["PIT_runs_successfully_computed"]=99
        with self.assertRaises(ValueError):build(*self.data,fake)
        fake=copy.deepcopy(self.pit100)
        fake["SEC_14day_delay_is_active"]=True
        with self.assertRaises(ValueError):build(*self.data,fake)
        fake=copy.deepcopy(self.pit100)
        fake["certified_11_node_AICS"]=500
        with self.assertRaises(ValueError):build(*self.data,fake)
        data=copy.deepcopy(self.data)
        data[0]["source_events"][0]["available_at"]="2024-11-01"
        with self.assertRaises(ValueError):build(*data,self.pit100)

    def test_rebuilt_scores_do_not_claim_independent_pit(self):
        r=build(*self.data,self.pit100)
        for k in ("market_monthly_rebuilt","calendar_monthly_rebuilt"):
            for month in r[k]:
                for node,score in month["node_scores_rebuilt_from_original_events"].items():
                    self.assertFalse(score["historical_first_delivery_attested"])
                    self.assertFalse(score["formula_preregistered"])
                    self.assertIn(node,self.data[0]["node_weights"])
                    self.assertNotIn("independently_certified_score",score)

if __name__=="__main__":unittest.main()
