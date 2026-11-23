"""V27 source-gated credit exposure / cash buildout bridge negative tests."""
from __future__ import annotations

import copy
import unittest

from scripts.aics_spv_funding_transmission_bridge import (
    read, CORE, CLOUD, NSCALE, DFS, build
)
from scripts.aics_early_imbalance_cashflow_shadow import (
    build as macro_build, Y2025, Q42025, Q12026, Q22026, Q32026
)


class SpvRecourseV27Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core, cls.cloud, cls.nscale, cls.dfs = (
            read(CORE), read(CLOUD), read(NSCALE), read(DFS))
        cls.macros = (read(Y2025), read(Q42025), read(Q22026), read(Q32026))

    def calculate(self, *, as_of="2026-11-22", core=None, nscale=None, dfs=None, cloud=None):
        macro = macro_build(*self.macros, q1=read(Q12026), as_of=as_of)
        return build(
            self.core if core is None else core,
            self.cloud if cloud is None else cloud,
            self.nscale if nscale is None else nscale,
            self.dfs if dfs is None else dfs,
            imbalance=macro, as_of=as_of)

    def test_actual_coreweave_instrument_specific_debt_not_parent_loss(self):
        r=self.calculate()
        x=r["coreweave"]
        self.assertEqual(x["source_available_at"],"2026-08-26")
        self.assertEqual(x["separate_facility_reported_debt_sum_usd_m"],3938)
        self.assertEqual(x["separate_facility_ceiling_sum_usd_m"],11600)
        self.assertEqual(x["reported_debt_to_ceiling_pct"],"33.95")
        self.assertEqual(x["same_issuer_coreweave_q2_ocf_minus_cash_ppe_usd_m"],-5743)
        self.assertEqual(len(r["coreweave_facility_edges"]),2)
        self.assertEqual(
            [row["reported_debt_usd_m"] for row in r["coreweave_facility_edges"]],
            [2837,1101])
        self.assertIn("Non-recourse",x["facilities"][0]["recourse"])
        self.assertEqual(x["facilities"][1]["recourse"],"Unconditional parent guarantee")
        self.assertIsNone(r["spv_parent_enforceable_guarantee_total_usd_m"])
        self.assertIsNone(r["current_combined_spv_debt_usd_m"])
        self.assertEqual(r["named_lender_to_borrower_current_exposure_edges"],0)
        self.assertFalse(r["production_weights_changed"])

    def test_nscale_separate_instruments_never_add_or_fill_unknown_draw(self):
        r=self.calculate()
        n=r["nscale"]
        self.assertEqual(n["combined_two_gpu_ceiling_usd_m"],3050)
        self.assertEqual(n["dell_initial_term_rent_usd_m_includes_financing_charges"],2540)
        self.assertEqual(n["separate_nscale_consolidated_2026_06_30_debt_carrying_usd_m"],137.4)
        self.assertEqual(n["separate_uk_gpu_services_historical_2026_03_31_drawn_usd_m"],58.9)
        self.assertEqual(n["separate_macquarie_historical_utilizations_usd_m_not_current_outstanding"],105)
        self.assertIsNone(n["sum_of_3050_2540_137_4_105_58_9_as_exposure"])
        self.assertIsNone(n["ward_drawn_balance_usd_m"])
        self.assertIsNone(n["north_carolina_drawn_balance_usd_m"])
        self.assertIsNone(n["outstanding_lease_liability_usd_m"])
        self.assertIsNone(n["legally_enforceable_parent_guarantee_usd_m"])
        self.assertEqual(r["named_historical_nscale_lender_borrower_relationships"],1)
        self.assertIsNone(r["verified_2008_funding_contagion_matrix"])
        self.assertIsNone(r["forecast_crisis_probability"])
        self.assertIsNone(r["historical_crisis_2008_similarity_pct"])

    def test_source_availability_sec_plus14_no_leakage(self):
        for date,core_ok,nscale_ok in (
            ("2026-08-25",False,False),
            ("2026-08-26",True,False),
            ("2026-10-01",True,False),
            ("2026-10-02",True,True),
        ):
            with self.subTest(date=date):
                r=self.calculate(as_of=date)
                self.assertEqual(r["coreweave"] is not None,core_ok)
                self.assertEqual(r["nscale"] is not None,nscale_ok)
                self.assertEqual(len(r["coreweave_facility_edges"]),2 if core_ok else 0)

    def test_reject_forged_coreweave_debt_guarantee_dates_or_recourse(self):
        for field,value in (
            ("reported_debt_usd_m",8500),
            ("recourse","Parent fully guarantees every facility"),
            ("reported_balance_to_ceiling_pct","100.00"),
            ("parent_enforceable_guarantee_usd_m",2837),
        ):
            bad=copy.deepcopy(self.core)
            bad["observations"][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.calculate(core=bad)
        bad=copy.deepcopy(self.core)
        bad["strict_aics_sec_available_at"]="2026-08-12"
        with self.assertRaises(ValueError):
            self.calculate(core=bad)

    def test_reject_nscale_rent_as_debt_and_false_publication(self):
        bad=copy.deepcopy(self.nscale)
        bad["ward_county_spv_drawn_amount_usd"]=1850000000
        with self.assertRaises(ValueError):
            self.calculate(nscale=bad)
        bad=copy.deepcopy(self.dfs)
        bad["combined_economic_exposure_usd"]=5590000000
        with self.assertRaises(ValueError):
            self.calculate(dfs=bad)
        bad=copy.deepcopy(self.dfs)
        bad["sec_available_at"]="2026-09-18"
        with self.assertRaises(ValueError):
            self.calculate(dfs=bad)

    def test_reject_fabricated_cross_issuer_cashflow_attribution(self):
        r=self.calculate()
        self.assertEqual(r["hyperscaler_buildout_context"]["hyperscaler_four_issuer_q3_2026_gap_usd_m"],-26425)
        self.assertTrue(r["hyperscaler_buildout_context"]["hyperscalers_are_not_coreweave_or_nscale"])
        self.assertFalse(r["hyperscaler_buildout_context"]["same_counterparty_exposure_or_transmission_proven"])
        self.assertIsNone(r["new_aics_node_score"])
        self.assertIsNone(r["full_11node_aics"])
        self.assertFalse(r["independent_24month_oos"])


if __name__=="__main__":
    unittest.main()
