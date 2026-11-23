"""SEC-original 2026 Q1 hyperscaler cash-gap restoration and causal availability."""
from __future__ import annotations

import copy
import datetime as dt
import unittest

from scripts.aics_early_imbalance_cashflow_shadow import (
    Y2025, Q42025, Q12026, Q22026, Q32026, build, read,
)


class CashGapQ12026Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = (read(Y2025), read(Q42025), read(Q22026), read(Q32026))
        cls.q1 = read(Q12026)

    def calculate(self, q1=None, *, as_of="2026-11-22"):
        return build(*self.sources, q1=self.q1 if q1 is None else q1,
                     as_of=dt.date.fromisoformat(as_of))

    def test_complete_real_seven_quarter_roster_and_totals(self):
        out=self.calculate()
        self.assertEqual(len(out["quarterly_original_issuer_records"]),28)
        self.assertEqual(len(out["complete_or_partial_quarters"]),7)
        self.assertEqual([x["period"] for x in out["complete_or_partial_quarters"]],
                         ["2025-Q1","2025-Q2","2025-Q3","2025-Q4",
                          "2026-Q1","2026-Q2","2026-Q3"])
        self.assertEqual(out["missing_quarters_not_imputed"],[])
        q={x["period"]:x for x in out["complete_or_partial_quarters"]}
        self.assertEqual(q["2026-Q1"]["issuer_count"],4)
        self.assertEqual(q["2026-Q1"]["four_issuer_ocf_usd_m"],"150727")
        self.assertEqual(q["2026-Q1"]["four_issuer_cash_ppe_usd_m"],"129750")
        self.assertEqual(q["2026-Q1"]["four_issuer_cash_gap_usd_m"],"20977")
        self.assertEqual(q["2026-Q1"]["cash_ppe_over_ocf_pct"],"86.08")
        self.assertEqual(q["2026-Q1"]["observed_negative_cash_gap_issuers"],["Amazon"])
        self.assertEqual(q["2026-Q1"]["source_eligible_at"],"2026-05-13")
        self.assertEqual(q["2025-Q4"]["four_issuer_cash_gap_usd_m"],"60201")
        self.assertEqual(q["2026-Q2"]["four_issuer_cash_gap_usd_m"],"6709")
        self.assertEqual(q["2026-Q3"]["four_issuer_cash_gap_usd_m"],"-26425")
        self.assertEqual(out["same_issuer_yoy_q3"]["cash_gap_deterioration_usd_m"],"-88149")
        self.assertIsNone(out["full_11_node_aics"])
        self.assertIsNone(out["similarity_to_2000_pct"])
        self.assertFalse(out["production_weight_change"])
        self.assertFalse(out["trading"])

    def test_sec_plus_14_cannot_move_2026_q1_into_prior_day(self):
        prior=self.calculate(as_of="2026-05-12")
        self.assertNotIn("2026-Q1",[q["period"] for q in prior["complete_or_partial_quarters"]])
        self.assertEqual(len(prior["quarterly_original_issuer_records"]),16)
        eligible=self.calculate(as_of="2026-05-13")
        q=[r for r in eligible["complete_or_partial_quarters"]
           if r["period"]=="2026-Q1"][0]
        self.assertTrue(q["four_issuer_complete"])
        self.assertEqual(q["four_issuer_cash_gap_usd_m"],"20977")
        self.assertNotIn("2026-Q2",[x["period"] for x in eligible["complete_or_partial_quarters"]])

    def test_reject_mismatched_doc_id_amount_or_historical_pit_claim(self):
        for key,val in (
            ("ppe",999),
            ("available_at","2026-05-12"),
            ("filed_at","2026-04-30"),
            ("cik","123456"),
            ("source_url","https://example.org/fake"),
        ):
            bad=copy.deepcopy(self.q1)
            bad["issuer_rows"][0][key]=val
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.calculate(q1=bad)
        bad=copy.deepcopy(self.q1)
        bad["integrity"]["historical_first_delivery_provider_pit_attested"]=True
        with self.assertRaises(ValueError):
            self.calculate(q1=bad)
        bad=copy.deepcopy(self.q1)
        bad["totals"]["ocf_usd_m"]=150728
        with self.assertRaises(ValueError):
            self.calculate(q1=bad)

    def test_previous_missing_q1_research_mode_remains_explicit(self):
        old=build(*self.sources,as_of=dt.date(2026,11,22))
        self.assertEqual(old["missing_quarters_not_imputed"],["2026-Q1"])
        self.assertEqual(len(old["quarterly_original_issuer_records"]),24)


if __name__=="__main__":
    unittest.main()
