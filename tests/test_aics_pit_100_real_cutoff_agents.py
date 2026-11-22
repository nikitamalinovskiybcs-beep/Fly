"""PIT100 real event cutoffs, 100 audited roles, SEC public-day rule tests."""
from __future__ import annotations

import copy
import datetime as dt
import unittest

from scripts.aics_pit_100_real_cutoff_agents import (
    build,source_preflight,historical_observation_dates,eligible,
    read_bytes,OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,TERMS,FUNDING,
    STATUS,SOURCE_GROUPS,ROLES,
)
from scripts.aics_early_imbalance_cashflow_shadow import (
    build as cash_build,read,Y2025,Q42025,Q12026,Q22026,Q32026,
)


class HundredSourceDerivedHistoricalPITReplays(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=[read_bytes(x) for x in
                  (OVERLAY,CREDIT,REGISTRY,REPO,EQUITIES,TERMS,FUNDING,STATUS)]
        cls.cash=cash_build(read(Y2025),read(Q42025),read(Q22026),
                            read(Q32026),q1=read(Q12026),as_of="2026-11-22")

    def run_audit(self,inputs=None,*,asof="2026-11-22"):
        return build(*(self.data if inputs is None else inputs),
                     self.cash,as_of=asof)

    def test_100_genuine_different_source_date_audits_and_roles(self):
        rep=self.run_audit()
        self.assertEqual(rep["actual_distinct_aics_roles"],100)
        self.assertEqual(rep["original_base_aics_roles"],30)
        self.assertEqual(rep["new_PIT_specialist_roles"],70)
        self.assertEqual(rep["unique_historical_replay_cutoffs"],100)
        self.assertEqual(rep["PIT_runs_successfully_computed"],100)
        self.assertGreaterEqual(rep["available_unique_original_observation_dates"],100)
        runs=rep["100_audit_results"]
        self.assertEqual(len({r["historical_cutoff"] for r in runs}),100)
        self.assertEqual(len({r["AICS_role_id"] for r in runs}),100)
        self.assertEqual(len(set(ROLES)),100)
        self.assertEqual(len(rep["distinct_audit_families"]),10)
        self.assertTrue(all(v==10 for v in rep["checks_per_family"].values()))
        self.assertEqual([r["PIT_audit_number"] for r in runs],list(range(1,101)))
        self.assertEqual([r["audit_family"] for r in runs[::10]],list(SOURCE_GROUPS))
        self.assertTrue(all(r["cutoff_is_exact_observed_source_or_month_end_date"] for r in runs))
        self.assertTrue(all(r["historical_provider_receipt_independently_verified"] is False for r in runs))
        self.assertFalse(rep["SEC_14day_delay_is_active"])
        self.assertTrue(rep["legacy_14day_date_difference_is_not_violation_under_active_policy"])
        self.assertEqual(rep["legacy_14day_proxy_SEC_events_count"],27)
        self.assertIsNone(rep["certified_11_node_AICS"])
        self.assertIsNone(rep["AICS_SP500_spread"])
        self.assertIsNone(rep["supervised_forward_skill"])
        self.assertFalse(rep["production_model_weights_changed"])
        self.assertFalse(rep["trades_created"])

    def test_one_actual_original_sec_filing_day_before_market_close_uncertainty(self):
        # The public calendar date must not be backdated by 14 artificial days;
        # without acceptance timestamp it may still be AFTER the NYSE close.
        original=next(x for x in self.data[0]["source_events"]
                      if x["source_policy"]==
                      "verified_original_sec_filed_date_plus_one_calendar_day_proxy")
        filed=(dt.date.fromisoformat(original["available_at"])
               -dt.timedelta(days=14)).isoformat()
        cutoff=dt.date.fromisoformat(filed)
        self.assertTrue(eligible(filed,cutoff,market_close=False))
        self.assertFalse(eligible(filed,cutoff,market_close=True))
        self.assertTrue(eligible(filed,cutoff+dt.timedelta(days=1),market_close=True))
        self.assertNotEqual(filed,original["available_at"])
        self.assertEqual((dt.date.fromisoformat(original["available_at"])-cutoff).days,14)

    def test_100_separate_replays_are_deterministic_and_span_real_date_corpus(self):
        a=self.run_audit()
        b=self.run_audit()
        self.assertEqual(a,b)
        history={x["historical_cutoff"] for x in a["100_audit_results"]}
        self.assertIn(min(history),history)
        self.assertIn(max(history),history)
        self.assertTrue(min(history).startswith("2024"))
        self.assertTrue(max(history).startswith("2026"))
        names=set(SOURCE_GROUPS)
        self.assertEqual({x["audit_family"] for x in a["100_audit_results"]},names)
        self.assertEqual(sum(x["new_specialist_role"] for x in a["100_audit_results"]),70)
        self.assertEqual(sum(x["existing_core_role"] for x in a["100_audit_results"]),30)

    def test_original_source_tampering_and_false_certification_fail_closed(self):
        for index,key,value in (
            (0,"independently_historical_pit_attested",True),
            (1,"historical_pit_source_bytes_independently_attested",True),
            (3,"contemporaneous_alfred_snapshots_attested",True),
            (4,"approved_historical_constituency",True),
            (5,"known_current_lender_dollar_exposures",5),
            (6,"index_aics",600),
            (7,"independently_certified_nodes",11),
        ):
            altered=copy.deepcopy(self.data)
            altered[index][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.run_audit(altered)
        bad=copy.deepcopy(self.data)
        bad[0]["source_events"][0]["available_at"]="2024-11-01"
        with self.assertRaises(ValueError):
            self.run_audit(bad)
        bad=copy.deepcopy(self.data)
        bad[2]["crwv_26_h1"]["original"]["sha256"]="fake"
        with self.assertRaises(ValueError):
            self.run_audit(bad)

    def test_domain_answers_are_not_same_repeated_dummies(self):
        rep=self.run_audit()
        groups={name:[r for r in rep["100_audit_results"]
                      if r["audit_family"]==name] for name in SOURCE_GROUPS}
        self.assertTrue(all(len(group)==10 for group in groups.values()))
        for domain,rows in groups.items():
            self.assertEqual(len({r["historical_cutoff"] for r in rows}),10)
            self.assertTrue(all(r["domain_specific_source_derived_audit"] for r in rows))
        self.assertTrue(all(
            r["domain_specific_source_derived_audit"]["no_14calendar_day_artificial_delay_active"]
            for r in groups["SEC_PUBLIC_FILING_AND_ACCEPTANCE"]))
        self.assertTrue(all(
            r["domain_specific_source_derived_audit"]["candidate_quarter_scores_are_not_PIT_certified"]
            for r in groups["PRIVATE_CREDIT_3BDC_SOURCE_DATES"]))
        self.assertTrue(all(
            r["domain_specific_source_derived_audit"]["source_release_timestamp_attested"] is False
            for r in groups["REPO_RATE_RELEASE_VINTAGE"]))
        self.assertTrue(all(
            r["domain_specific_source_derived_audit"]["source_historic_constituents_verified"] is False
            for r in groups["AI_EQUITIES_PRICE_CONSTITUENCY_VINTAGE"]))
        self.assertTrue(all(
            r["domain_specific_source_derived_audit"]["named_current_lender_dollar_exposures"]==0
            for r in groups["NEOCLOUD_CONTRACT_BORROWER_RECOURSE"]))


if __name__=="__main__":
    unittest.main()
