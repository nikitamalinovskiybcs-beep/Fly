"""AICS 24-month PIT100 source rebuild: 100 cutoffs and no ex-post index."""
from __future__ import annotations

import copy
import unittest
from scripts.aics_pit100_rebuild_24_month_public_filing_panel import (
    build, normalized_events, replay_at, ambiguous_public_release_pairs,
    markdown_report,OVERLAY,CREDIT,SP500,read_bytes,
)
from scripts.aics_pit_100_real_cutoff_agents import (
    build as pit100_build,REGISTRY,REPO,EQUITIES,TERMS,FUNDING,STATUS,
)
from scripts.aics_early_imbalance_cashflow_shadow import (
    build as cash_build,read,Y2025,Q42025,Q12026,Q22026,Q32026,
)


class PIT100OriginalSourceMonthlyRebuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overlay=read_bytes(OVERLAY)
        cls.credit=read_bytes(CREDIT)
        cls.spx=read_bytes(SP500)
        files=[REGISTRY,REPO,EQUITIES,TERMS,FUNDING,STATUS]
        cls.inputs=[read_bytes(x) for x in files]
        cls.cash=cash_build(read(Y2025),read(Q42025),read(Q22026),
                            read(Q32026),q1=read(Q12026),as_of="2026-11-22")
        cls.pit=pit100_build(cls.overlay,cls.credit,*cls.inputs,cls.cash,
                             as_of="2026-11-22")

    def rebuild(self,*,overlay=None,credit=None,spx=None,pit=None):
        return build(
            self.overlay if overlay is None else overlay,
            self.credit if credit is None else credit,
            self.spx if spx is None else spx,
            self.pit if pit is None else pit,
            as_of="2026-11-22")

    def test_24_market_calendar_months_are_derived_from_64_originals(self):
        r=self.rebuild()
        self.assertEqual(r["source_events_recomputed_from_unchanged_original_ledgers"],64)
        self.assertEqual(r["original_PIT100_roles_individually_verified_against_rebuild"],100)
        self.assertEqual(len(r["audit_100_unique_original_source_cutoffs"]),100)
        self.assertFalse(r["SEC_14day_artificial_delay_active"])
        self.assertFalse(r["same_day_unverified_market_close_filing_is_eligible"])
        self.assertFalse(r["independently_historical_PIT_first_delivery_certified"])
        self.assertIsNone(r["full_11node_AICS"])
        self.assertIsNone(r["aics_sp500_spread"])
        self.assertIsNone(r["24month_independent_OOS_skill"])
        self.assertFalse(r["model_weights_changed"])
        self.assertFalse(r["trades_created"])
        p=r["monthly_rebuilt_panels"]
        self.assertEqual(len(p["calendar"]),24)
        self.assertEqual(len(p["market"]),24)
        self.assertEqual([x["month"] for x in p["market"]],
                         [x["month"] for x in p["calendar"]])
        self.assertEqual(p["market"][0]["date_only_known_weight"],325)
        self.assertEqual(p["market"][0]["date_only_partial_points_not_full_AICS"],"39.68")
        self.assertEqual(p["market"][-1]["date_only_known_weight"],725)
        self.assertEqual(p["calendar"][-1]["date_only_known_weight"],950)
        self.assertEqual(p["market"][-1]["month"],"2026-10")
        self.assertEqual(p["calendar"][-1]["month"],"2026-10")
        for panel in p.values():
            for row in panel:
                self.assertLessEqual(row["date_only_known_weight"],1050)
                self.assertLessEqual(row["fresh_90d_known_weight"],row["date_only_known_weight"])
                self.assertTrue(row["missing_nodes"])
                self.assertIsNone(row["full_11_node_AICS"])
                self.assertIsNone(row["S&P500_index_spread"])
                self.assertFalse(row["source_pit_independently_certified"])

    def test_100_roles_audit_all_100_original_source_cutoffs(self):
        r=self.rebuild()
        hist=r["audit_100_unique_original_source_cutoffs"]
        self.assertEqual(len({x["actual_historical_source_cutoff"] for x in hist}),100)
        self.assertEqual(len({x["original_PIT100_role"] for x in hist}),100)
        self.assertEqual([x["original_PIT100_audit_no"] for x in hist],list(range(1,101)))
        for entry in hist:
            self.assertGreaterEqual(
                entry["calendar_public_day_rebuilt_known_weight"],
                entry["market_close_protected_rebuilt_known_weight"])
            self.assertFalse(entry["historical_PIT_source_certified"])
        text=markdown_report(r)
        self.assertIn("2024-11",text)
        self.assertIn("2026-10",text)
        self.assertIn("S&P 500",text)
        self.assertIn("G.17 joint release",text)
        self.assertIn("**no +14-day delay**",text)

    def test_fed_official_dec23_joint_oct_and_nov_measurements_are_both_valid(self):
        e=normalized_events(self.overlay,self.credit)
        conflicts=ambiguous_public_release_pairs(e)
        self.assertEqual(conflicts,[])
        source=[r for r in e if r["node"]=="Semiconductors Supply"
                and r["first_public_research_day_proxy"]=="2025-12-23"]
        self.assertEqual(len(source),2)
        self.assertEqual({x["observation_month"]:x["score"] for x in source},
                         {"2025-10":"74.70","2025-11":"74.40"})
        self.assertTrue(all(x["original_joint_publication_url"] ==
                            "https://www.federalreserve.gov/releases/g17/20251223/table7.htm"
                            for x in source))
        m=replay_at(e,"2025-12-31",market_close=False)
        self.assertEqual(
            m["event_source_scores"]["Semiconductors Supply"]["score_0_100_research_only"],
            "74.40")
        self.assertEqual(m["quarantined_conflicting_source_records"],0)
        self.assertEqual(m["ambiguous_publication_source_dates"],[])
        jan=replay_at(e,"2026-01-30",market_close=True)
        self.assertEqual(
            jan["event_source_scores"]["Semiconductors Supply"]["score_0_100_research_only"],
            "73.60")

    def test_new_public_filing_cutoff_no_same_day_market_leakage(self):
        e=normalized_events(self.overlay,self.credit)
        o=next(x for x in e if x["node"]=="Insurers"
               and x["first_public_research_day_proxy"]=="2024-10-31")
        self.assertEqual(o["legacy_original_plus14_or_release_date"],"2024-11-14")
        market=replay_at(e,"2024-10-31",market_close=True)
        cal=replay_at(e,"2024-10-31",market_close=False)
        self.assertNotIn("Insurers",market["event_source_scores"])
        self.assertIn("Insurers",cal["event_source_scores"])
        # Original Q3 hyperscaler first-complete filing is October 30.
        m=replay_at(e,"2026-10-30",market_close=True)
        c=replay_at(e,"2026-10-30",market_close=False)
        self.assertEqual(m["event_source_scores"]["Hyperscalers"]["score_0_100_research_only"],"0.00")
        self.assertEqual(c["event_source_scores"]["Hyperscalers"]["score_0_100_research_only"],"13.09")

    def test_forged_source_numbers_and_claimed_pit_certification_blocked(self):
        overlay=copy.deepcopy(self.overlay)
        overlay["source_events"][0]["score"]="999"
        with self.assertRaises(ValueError):
            self.rebuild(overlay=overlay)
        overlay=copy.deepcopy(self.overlay)
        overlay["source_events"][0]["available_at"]="2024-11-01"
        with self.assertRaises(ValueError):
            self.rebuild(overlay=overlay)
        spx=copy.deepcopy(self.spx)
        spx["independent_pit_verified"]=True
        with self.assertRaises(ValueError):
            self.rebuild(spx=spx)
        pit=copy.deepcopy(self.pit)
        pit["100_audit_results"][0]["eligible_event_counts"][
            "source_events_sec_filed_day_calendar_dateonly"]=999
        with self.assertRaises(ValueError):
            self.rebuild(pit=pit)
        overlay=copy.deepcopy(self.overlay)
        overlay["monthly_last_weekday_market_proxy"][-1]["cutoff_date"]="2026-11-30"
        with self.assertRaises(ValueError):
            self.rebuild(overlay=overlay)


if __name__=="__main__":
    unittest.main()
