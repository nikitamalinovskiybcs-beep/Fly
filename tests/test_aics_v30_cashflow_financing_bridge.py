"""AICS V30 fail-closed SEC cash identity, financing vs lender causality tests."""
from __future__ import annotations

import copy
import unittest

from scripts.aics_v30_cashflow_financing_bridge import build,read,FUNDING,CASH,SEC


class AICSV30FundingBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.finance=read(FUNDING)
        cls.cash=read(CASH)
        cls.sec=read(SEC)

    def calculate(self, *, as_of="2026-11-22", funding=None, cash=None, sec=None):
        return build(
            self.finance if funding is None else funding,
            self.cash if cash is None else cash,
            self.sec if sec is None else sec,as_of=as_of)

    def test_actual_two_issuer_quarterly_cash_and_financing_reconciliation(self):
        z=self.calculate()
        self.assertEqual(z["q2_same_date_comparable_two_issuer_count"],2)
        self.assertEqual(len(z["issuer_quarter_observations"]),4)
        r={(x["period"],x["issuer"]):x for x in z["issuer_quarter_observations"]}
        self.assertEqual(r[("2026-Q1","CoreWeave")]["ocf_less_purchases_usd_m"],"-4711")
        self.assertEqual(r[("2026-Q1","Nebius")]["ocf_less_purchases_usd_m"],"-214.9")
        core=r[("2026-Q2","CoreWeave")]
        neb=r[("2026-Q2","Nebius")]
        self.assertEqual(core["ocf_less_purchases_usd_m"],"-5743")
        self.assertEqual(core["net_financing_cash_usd_m"],"10071")
        self.assertEqual(core["net_change_cash_including_restricted_usd_m"],"3584")
        self.assertEqual(core["qoq_change_ocf_minus_cash_purchases_usd_m"],"-1032")
        self.assertEqual(neb["ocf_less_purchases_usd_m"],"-3411.3")
        self.assertEqual(neb["net_financing_cash_usd_m"],"2864.9")
        self.assertEqual(neb["net_change_cash_including_restricted_usd_m"],"-528.8")
        self.assertEqual(neb["qoq_change_ocf_minus_cash_purchases_usd_m"],"-3196.4")
        self.assertEqual(core["q2_financing_components_usd_m"]["debt_issuance_net_of_costs"],"13457")
        self.assertEqual(core["q2_financing_components_usd_m"]["debt_repayments"],"-3884")
        self.assertEqual(neb["q2_financing_components_usd_m"]["treasury_share_sale"],"2846.7")
        self.assertEqual(core["source_eligible_at"],"2026-08-26")
        self.assertEqual(neb["source_eligible_at"],"2026-08-26")
        self.assertEqual(z["historically_comparable_matched_borrower_pricing_event_count"],0)
        self.assertTrue(z["coreweave_ddtl4_vs_ddtl5_spread_difference_is_not_time_series_repricing"])
        self.assertTrue(z["cashflow_financing_identity_not_causal_allocation"])
        self.assertIsNone(z["credit_spread_repricing_on_matched_instrument_bps"])
        self.assertIsNone(z["grouped_neocloud_loan_aggregate_current_outstanding_usd_m"])
        self.assertIsNone(z["crisis_probability"])
        self.assertIsNone(z["full_aics"])
        self.assertEqual(z["original_weights_total_unchanged"],1050)

    def test_cash_source_asof_gate_blocks_future_q2_records(self):
        for cutoff,n,which in (
            ("2026-05-21",0,[]),
            ("2026-05-22",1,[("2026-Q1","CoreWeave")]),
            ("2026-05-26",1,[("2026-Q1","CoreWeave")]),
            ("2026-05-27",2,[("2026-Q1","CoreWeave"),("2026-Q1","Nebius")]),
            ("2026-08-25",2,[("2026-Q1","CoreWeave"),("2026-Q1","Nebius")]),
            ("2026-08-26",4,[("2026-Q1","CoreWeave"),("2026-Q1","Nebius"),
                             ("2026-Q2","CoreWeave"),("2026-Q2","Nebius")]),
        ):
            with self.subTest(cutoff=cutoff):
                x=self.calculate(as_of=cutoff)
                self.assertEqual(len(x["issuer_quarter_observations"]),n)
                self.assertEqual(
                    [(r["period"],r["issuer"]) for r in x["issuer_quarter_observations"]],
                    which)

    def test_fake_cash_change_financing_and_original_sec_date_block(self):
        for field,value in (
            ("net_financing_cash","10070"),
            ("net_investing_cash","-7165"),
            ("cash_purchases_less_operating_cash","9999"),
        ):
            bad=copy.deepcopy(self.finance)
            bad["cash_bridges"][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.calculate(funding=bad)
        bad=copy.deepcopy(self.finance)
        bad["cash_bridges"][1]["financing_components_signed"]["treasury_share_sale"]="3000"
        with self.assertRaises(ValueError):
            self.calculate(funding=bad)
        bad=copy.deepcopy(self.finance)
        bad["cash_bridges"][0]["cash_including_restricted"]["end"]="6905"
        with self.assertRaises(ValueError):
            self.calculate(funding=bad)
        bad=copy.deepcopy(self.sec)
        bad["crwv_26_h1"]["available_at"]="2026-08-12"
        with self.assertRaises(ValueError):
            self.calculate(sec=bad)

    def test_misassigned_issuer_cash_capex_or_finance_row_blocks(self):
        bad=copy.deepcopy(self.cash)
        bad["observations"][2]["cash_purchases"]="5657.4"
        with self.assertRaises(ValueError):
            self.calculate(cash=bad)
        bad=copy.deepcopy(self.finance)
        bad["cash_bridges"][1]["issuer"]="CoreWeave"
        with self.assertRaises(ValueError):
            self.calculate(funding=bad)
        bad=copy.deepcopy(self.finance)
        bad["node_score"]=80
        with self.assertRaises(ValueError):
            self.calculate(funding=bad)


if __name__=="__main__":
    unittest.main()
