"""AICS V31 negative tests: IR news is not SEC eligible; repo isn't loan cost."""
from __future__ import annotations
import copy
import unittest
from scripts.aics_v31_interest_repo_dual_clock import (
    build,read,INTEREST,REPO,FUNDING,CASH,SEC,funding_build
)


class V31IRInterestRepoGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ir=read(INTEREST)
        cls.repo=read(REPO)
        cls.funding=read(FUNDING)
        cls.cash=read(CASH)
        cls.registry=read(SEC)

    def evaluate(self, *, as_of="2026-11-22", ir=None, repo=None):
        fund=funding_build(self.funding,self.cash,self.registry,as_of=as_of)
        return build(self.ir if ir is None else ir,
                     self.repo if repo is None else repo,
                     fund,as_of=as_of)

    def test_actual_ir_interest_revenue_research_not_AICS_interest_coverage(self):
        r=self.evaluate()
        self.assertEqual(r["asof_source_status"],"IR_RESEARCH_ONLY_SEC_DATE_EMBARGO")
        self.assertTrue(r["interest_research_visible_as_of"])
        self.assertFalse(r["Q3_SEC_10Q_date_gate_passed_as_of"])
        ir=r["issuer_IR_Q3_research"]
        self.assertEqual(ir["quarter_revenue_usd_m"],3661)
        self.assertEqual(ir["quarter_net_interest_expense_usd_m"],846)
        self.assertEqual(ir["net_interest_expense_divided_by_revenue_pct"],"23.1")
        self.assertTrue(ir["ratio_is_not_interest_coverage_or_covenant_DSCR"])
        self.assertFalse(ir["AICS_model_eligible"])
        self.assertEqual(r["coreweave_source_reconciled_Q2_cash_gap_usd_m"],"-5743")
        self.assertEqual(r["coreweave_source_reconciled_Q2_net_financing_usd_m"],"10071")
        self.assertEqual(r["repo_retrospective_latest_observed_month"],"2026-10-31")
        self.assertEqual(r["repo_latest_month_sofr_minus_iorb_bps"],4)
        self.assertEqual(r["repo_latest_month_sofr_minus_bgcr_bps"],2)
        self.assertEqual(r["repo_october_minus_september_sofr_iorb_bps"],6)
        self.assertFalse(r["repo_series_is_issuer_specific_funding_spread"])
        self.assertEqual(r["matched_same_loan_spread_repricing_events_verified"],0)
        for key in ("matched_same_loan_repricing_bps","coreweave_actual_coupon_paid",
                    "crisis_probability","early_warning_skill","full_11node_aics",
                    "bank_by_bank_exposure"):
            self.assertIsNone(r[key],key)
        self.assertEqual(r["weights_total_unchanged"],1050)
        self.assertFalse(r["trades_created"])

    def test_ir_release_and_SEC_plus14_historical_embargo(self):
        for cutoff,visible,sec_ok,state in (
            ("2026-11-09",False,False,"NOT_YET_RELEASED"),
            ("2026-11-10",True,False,"IR_RESEARCH_ONLY_SEC_DATE_EMBARGO"),
            ("2026-11-12",True,False,"IR_RESEARCH_ONLY_SEC_DATE_EMBARGO"),
            ("2026-11-25",True,False,"IR_RESEARCH_ONLY_SEC_DATE_EMBARGO"),
            ("2026-11-26",True,True,"SEC_DATE_PASSED_BUT_HISTORICAL_PIT_UNATTESTED"),
        ):
            with self.subTest(cutoff=cutoff):
                r=self.evaluate(as_of=cutoff)
                self.assertEqual(r["interest_research_visible_as_of"],visible)
                self.assertEqual(r["Q3_SEC_10Q_date_gate_passed_as_of"],sec_ok)
                self.assertEqual(r["asof_source_status"],state)
                self.assertEqual(r["issuer_IR_Q3_research"] is not None,visible)
                self.assertIsNone(r["full_11node_aics"])

    def test_repo_proxy_source_date_gates(self):
        x=self.evaluate(as_of="2026-10-29")
        self.assertEqual(x["repo_retrospective_latest_observed_month"],"2026-09-30")
        self.assertEqual(x["repo_latest_month_sofr_minus_iorb_bps"],-2)
        self.assertIsNone(x["repo_october_minus_september_sofr_iorb_bps"])
        y=self.evaluate(as_of="2026-10-30")
        self.assertEqual(y["repo_retrospective_latest_observed_month"],"2026-10-31")
        self.assertEqual(y["repo_latest_month_sofr_minus_iorb_bps"],4)
        self.assertEqual(y["repo_october_minus_september_sofr_iorb_bps"],6)

    def test_forged_interest_PIT_source_or_covenant_inference_rejected(self):
        for key,value in (
            ("quarter_net_interest_expense_usd_millions",900),
            ("quarter_revenue_usd_millions",3000),
            ("sec_10q_aics_available_at","2026-11-12"),
            ("sec_10q_filed_at","2026-11-10"),
            ("source_release_date","2026-10-01"),
            ("source_bytes_independently_hash_checked",False),
            ("original_sec_filing_pit_certified",True),
            ("index_aics",669.09),
        ):
            bad=copy.deepcopy(self.ir)
            bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.evaluate(ir=bad)

    def test_fake_repo_future_publication_or_matched_issuer_spread_rejected(self):
        for key,value in (
            ("sofr_minus_iorb_bps",90),
            ("publication_proxy_date","2026-11-03"),
        ):
            bad=copy.deepcopy(self.repo)
            bad["monthly_observations"][-1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.evaluate(repo=bad)
        bad=copy.deepcopy(self.repo)
        bad["contemporaneous_alfred_snapshots_attested"]=True
        with self.assertRaises(ValueError):
            self.evaluate(repo=bad)
        bad=copy.deepcopy(self.repo)
        bad["observed_months"]=25
        with self.assertRaises(ValueError):
            self.evaluate(repo=bad)


if __name__=="__main__":
    unittest.main()
