"""Real AICS V40–V49 PIT audits: 27 SEC and seven BDC early proxies.

Fixtures mutate real-source metadata solely for fail-closed negative tests.
They are not observations, historical data or archived PIT proof.
"""
from __future__ import annotations

import copy
import unittest

from scripts.aics_v40_v49_ten_pit_forensics_agents import (
    build_from_repository,build,read_bytes,
    OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,STATUS,NAMES,
)
from scripts.aics_historical_crisis_analog import build as analog_build


class TenPITForensicAgentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger=[read_bytes(x) for x in
                    (OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,STATUS)]
        cls.analog=analog_build(cls.ledger[1])

    def execute(self, *,date="2026-11-22",ledger=None,analog=None):
        return build(*(self.ledger if ledger is None else ledger),
                     self.analog if analog is None else analog,as_of=date)

    def test_ten_real_original_source_agent_assignments_and_pit_leakage(self):
        r=self.execute()
        self.assertEqual(len(r["ten_agent_research_results"]),10)
        self.assertEqual([x["name"] for x in r["ten_agent_research_results"]],NAMES)
        self.assertEqual(r["source_event_count"],57)
        self.assertEqual(r["source_premature_SEC_proxies"],27)
        self.assertEqual(r["private_credit_premature_quarters"],7)
        self.assertEqual(r["market_close_quarantined_node_months"],4)
        self.assertEqual(r["calendar_close_quarantined_node_months"],5)
        self.assertEqual(r["current_project_milestone_completion"],22)
        self.assertEqual(r["approved_pit_certified_nodes"],0)
        self.assertEqual(r["newly_completed_certification_gates"],0)
        self.assertIsNone(r["approved_11node_aics"])
        self.assertIsNone(r["crisis_probability"])
        self.assertFalse(r["model_weights_changed"])
        self.assertFalse(r["trades_created"])
        self.assertEqual(r["ten_agent_research_results"][4]["eligible_original_SEC_issuer_quarters"],28)
        self.assertEqual(r["ten_agent_research_results"][4]["complete_four_issuer_quarters"],7)
        self.assertEqual(r["ten_agent_research_results"][5]["independently_source_hashed_original_SEC_archives"],10)
        self.assertEqual(r["ten_agent_research_results"][5]["historically_PIT_attested_original_provider_receipts"],0)
        self.assertEqual(r["ten_agent_research_results"][6]["retrospective_repo_months"],24)
        self.assertEqual(r["ten_agent_research_results"][6]["ALFRED_release_vintages_independently_attested"],0)
        self.assertEqual(r["ten_agent_research_results"][7]["retrospective_original_price_records"],441)
        self.assertEqual(r["ten_agent_research_results"][8]["measured_failure_mechanism_axes"],8)
        self.assertEqual(r["ten_agent_research_results"][9]["total_independent_project_gates"],66)

    def test_month_specific_lookahead_are_original_and_quarantined_not_backfilled(self):
        r=self.execute()
        market=r["ten_agent_research_results"][2]
        calendar=r["ten_agent_research_results"][3]
        self.assertEqual(market["monthly_source_windows"],24)
        self.assertEqual(market["affected_months"],["2025-05","2025-10","2026-02"])
        self.assertEqual(calendar["affected_months"],["2025-05","2025-10","2026-02","2026-10"])
        self.assertEqual([x["node"] for x in market["quarantine_journal"]],
                         ["Neoclouds","Hyperscalers","Insurers","Neoclouds"])
        self.assertEqual([x["node"] for x in calendar["quarantine_journal"]],
                         ["Neoclouds","Hyperscalers","Insurers","Neoclouds","Hyperscalers"])
        for panel in (market,calendar):
            for month in panel["date_safe_source_eligibility_replay_not_scored_index"]:
                self.assertIsNone(month["full_11node_index"])
                self.assertIsNone(month["aics_sp500_spread"])
                self.assertLessEqual(month["safe_date_only_research_known_weight"],
                                     month["original_research_known_weight"])
                self.assertTrue(month["safe_date_only_scores_are_still_not_independently_PIT_or_preregistered"])

    def test_forged_sec_early_dates_or_private_credit_14_days_fail(self):
        source=copy.deepcopy(self.ledger)
        sec=next(x for x in source[0]["source_events"]
                 if x["source_policy"]=="verified_original_sec_filed_date_plus_one_calendar_day_proxy")
        sec["available_at"]=sec["research_eligible_date"]
        with self.assertRaises(ValueError):
            self.execute(ledger=source)
        source=copy.deepcopy(self.ledger)
        source[1]["source_events"][0]["legacy_sec_plus14_available_at"]=(
            source[1]["source_events"][0]["research_available_at_proxy"])
        with self.assertRaises(ValueError):
            self.execute(ledger=source)
        source=copy.deepcopy(self.ledger)
        source[0]["monthly_last_weekday_market_proxy"][0]["known_weight"]=1050
        with self.assertRaises(ValueError):
            self.execute(ledger=source)

    def test_history_receipt_and_node_promotion_fail_closed(self):
        for idx,key,value in (
            (0,"independently_historical_pit_attested",True),
            (1,"historical_pit_source_bytes_independently_attested",True),
            (3,"contemporaneous_alfred_snapshots_attested",True),
            (4,"approved_historical_constituency",True),
            (5,"independently_certified_nodes",11),
            (5,"milestones_completed",66),
        ):
            altered=copy.deepcopy(self.ledger)
            altered[idx][key]=value
            with self.subTest(field=key),self.assertRaises(ValueError):
                self.execute(ledger=altered)
        fake=copy.deepcopy(self.analog)
        fake["quantitative_similarity_percent_2008"]=100
        with self.assertRaises(ValueError):
            self.execute(analog=fake)

    def test_late_reports_not_predated_and_source_hashes_not_first_delivery(self):
        a=self.execute(date="2026-11-12")
        b=self.execute(date="2026-11-13")
        self.assertEqual(a["ten_agent_research_results"][4]["eligible_original_SEC_issuer_quarters"],24)
        self.assertEqual(b["ten_agent_research_results"][4]["eligible_original_SEC_issuer_quarters"],28)
        self.assertEqual(a["ten_agent_research_results"][4]["complete_four_issuer_quarters"],6)
        self.assertEqual(b["ten_agent_research_results"][4]["complete_four_issuer_quarters"],7)
        self.assertEqual(a["ten_agent_research_results"][5]["independently_source_hashed_original_SEC_archives"],10)
        self.assertEqual(a["ten_agent_research_results"][5]["historically_PIT_attested_original_provider_receipts"],0)


if __name__=="__main__":
    unittest.main()
