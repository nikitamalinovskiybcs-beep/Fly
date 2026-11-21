"""AICS V29: original SEC loan terms only, no invented maturity/debt or lookahead."""
from __future__ import annotations

import copy
import unittest

from scripts.aics_v29_refinancing_maturity_overlay import (
    TERMS, read, build
)
from scripts.aics_v28_credit_relationship_topology import from_originals
from scripts.aics_spv_funding_transmission_bridge import (
    build as spv_build, CORE, CLOUD, NSCALE, DFS
)


class LoanRefinancingTermsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources=[read(x) for x in (CORE,CLOUD,NSCALE,DFS)]
        cls.contracts=read(TERMS)

    def evaluate(self, as_of="2026-11-22", terms=None):
        spv=spv_build(*self.sources,as_of=as_of)
        topology=from_originals(spv,as_of=as_of)
        return build(self.contracts if terms is None else terms,
                     spv,topology,as_of=as_of)

    def test_three_contracts_valid_date_and_no_false_current_debt(self):
        x=self.evaluate()
        self.assertEqual(x["eligible_contract_count"],3)
        self.assertEqual(x["loan_maturities_within_365_calendar_days"],1)
        self.assertEqual(x["first_known_contractual_maturity"],"2027-10-16")
        self.assertFalse(x["first_known_contractual_maturity_is_outstanding_principal_due"])
        self.assertEqual(x["coreweave_admin_agents_named"],2)
        self.assertTrue(x["nebius_citi_mandated_arranger_and_lender_named"])
        self.assertEqual(x["individual_lender_allocations_verified"],0)
        self.assertEqual(x["current_named_lender_borrower_dollar_exposure_edges"],0)
        self.assertIsNone(x["actual_credit_refinancing_need_usd_m"])
        self.assertIsNone(x["actual_coupon_including_base_rate"])
        self.assertIsNone(x["actual_dscr_breach_count"])
        self.assertIsNone(x["full_aics"])
        self.assertIsNone(x["crisis_probability"])
        self.assertFalse(x["production_model_changed"])
        z={r["facility_id"]:r for r in x["contractual_term_records"]}
        a,b,c=z["CRWV_DDTL4"],z["CRWV_DDTL5"],z["NBIS_CITI_BRIDGE"]
        self.assertEqual(a["contractual_capacity_usd_m_not_debt"],8500)
        self.assertEqual(a["most_recent_verified_numeric_debt_usd_m_at_2026_06_30_not_current"],2837)
        self.assertEqual(a["maturity"],"2032-03-31")
        self.assertEqual(a["named_administrative_agent"],"MUFG Bank, Ltd.")
        self.assertEqual(a["initial_or_contractual_floating_spread_bps"],225)
        self.assertEqual(a["dscr_contractual_minimum_x_not_actual"],"1.15")
        self.assertEqual(b["maturity"],"2031-11-15")
        self.assertEqual(b["initial_or_contractual_floating_spread_bps"],450)
        self.assertEqual(b["most_recent_verified_numeric_debt_usd_m_at_2026_06_30_not_current"],1101)
        self.assertTrue(b["commitment_period_ended_by_asof"])
        self.assertEqual(b["dscr_contractual_minimum_x_not_actual"],"1.35")
        self.assertEqual(c["named_mandated_arranger_and_lender"],"Citibank, N.A.")
        self.assertEqual(c["maturity"],"2027-10-16")
        self.assertEqual(c["initial_or_contractual_floating_spread_bps"],275)
        self.assertEqual(c["contractual_term_sofr_stepup_bps_every_90d"],25)
        self.assertEqual(c["contractual_max_margin_bps_subject_to_adjustments"],350)
        self.assertIsNone(c["current_outstanding_usd_m"])
        self.assertTrue(all(v["named_lender_funded_amount_usd_m"] is None for v in z.values()))

    def test_sec_14_source_date_and_june_numeric_debt_date_independent(self):
        for cutoff,facilities,debts in (
            ("2026-04-13",0,0),
            ("2026-04-14",1,0),
            ("2026-05-31",1,0),
            ("2026-06-01",2,0),
            ("2026-08-25",2,0),
            ("2026-08-26",2,2),
            ("2026-11-04",2,2),
            ("2026-11-05",3,2),
        ):
            with self.subTest(cutoff=cutoff):
                x=self.evaluate(cutoff)
                self.assertEqual(x["eligible_contract_count"],facilities)
                self.assertEqual(sum(z["most_recent_verified_numeric_debt_usd_m_at_2026_06_30_not_current"] is not None
                                     for z in x["contractual_term_records"]),debts)
        self.assertEqual(self.evaluate("2026-11-04")["loan_maturities_within_365_calendar_days"],0)

    def test_forged_filing_date_source_role_margin_or_maturity_blocked(self):
        for index,key,value in [
            (0,"available_at","2026-03-31"),
            (0,"source_url","https://example.org/contract"),
            (0,"contractual_maturity","2027-03-31"),
            (0,"daily_compounded_sofr_float_margin_bps",450),
            (0,"dscr_minimum_x","2.00"),
            (0,"administrative_agent","Other unknown bank"),
            (1,"historical_reported_debt_usd_m",3100),
            (1,"parent_recourse","non-recourse"),
            (2,"mandated_lead_arranger_and_lender","Unidentified"),
            (2,"contractual_maturity","2026-11-30"),
            (2,"margin_cap_bps",999),
            (2,"actual_total_drawn_usd_m",3500),
            (2,"lender_by_lender_amount_usd_m",3500),
        ]:
            v=copy.deepcopy(self.contracts)
            v["contracts"][index][key]=value
            with self.subTest(index=index,key=key),self.assertRaises(ValueError):
                self.evaluate(terms=v)

    def test_no_original_pit_or_trades_or_portfolio_return_claim(self):
        for field,value in [
            ("historical_first_delivery_provider_pit_certified",True),
            ("known_current_lender_dollar_exposures",1),
            ("unmodified_11node_aics",669.09),
            ("trades_created",True),
        ]:
            v=copy.deepcopy(self.contracts)
            v[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.evaluate(terms=v)


if __name__=="__main__":
    unittest.main()
