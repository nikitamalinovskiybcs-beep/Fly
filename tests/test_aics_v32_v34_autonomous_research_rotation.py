"""AICS autonomous V32-V34 research batch tests; fixtures only for cycle metadata.

Real dated finance and interest values always loaded from repository SEC-derived
original ledgers. Synthetic cycle metadata is NEVER published as market data.
"""
from __future__ import annotations
import copy
import unittest

from scripts.aics_v32_v34_autonomous_research_rotation import build, read, TERMS, FUNDING, CASH, SEC, INTEREST, REPO
from scripts.aics_v30_cashflow_financing_bridge import build as build_funding
from scripts.aics_v31_interest_repo_dual_clock import build as build_interest


def cycle_fixture(cutoff):
    return {
        "schema":"aics-30-agent-evidence-to-improvement-loop-v1",
        "cutoff_date":cutoff,
        "agent_groups":{"total_distinct_roles_executed":30},
        "source_collection":{"http_attempts":36,"successful_http_archives":36},
        "cycle_decision":"RESEARCH_ONLY_NOT_AUTONOMOUS_PRODUCTION",
        "complete_11_node_aics":None,"crisis_probability":None,
        "weights_total_unchanged":1050,"weights_changed":False,
        "eligible_for_production_promotion":False,"trades_created":False,
        "model_improvement":{
            "credit_exposure_edges_verified":0,
            "v29_nebius_citi_named_lender_funded_usd_m":None,
            "v30_crisis_causal_skill":None,
            "v31_independently_confirmed_early_warning_skill":None,
            "v31_matched_same_loan_repricing_observations":0,
        },
        "next_experiments":[
            {"priority":1,"experiment":"ORIGINAL_SEC_NUMERIC_SOURCE_TO_NODE","decision":"RESEARCH"},
            {"priority":2,"experiment":"FROZEN_FORMULA_WALK_FORWARD","decision":"BLOCKED_UNTIL_DATA"},
        ],
    }


class AutonomousV32V34Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terms=read(TERMS)
        cls.source_funding=read(FUNDING)
        cls.source_cash=read(CASH)
        cls.sec=read(SEC)
        cls.ir=read(INTEREST)
        cls.repo=read(REPO)

    def make(self,date="2026-11-22",*,cycle=None,terms=None):
        finance=build_funding(self.source_funding,self.source_cash,self.sec,as_of=date)
        interest=build_interest(self.ir,self.repo,finance,as_of=date)
        return build(self.terms if terms is None else terms,finance,interest,
                     cycle_fixture(date) if cycle is None else cycle,as_of=date)

    def test_three_evidence_gates_with_real_finance_inputs(self):
        z=self.make()
        self.assertEqual(z["agents_exec_group_count"],30)
        self.assertEqual(z["archived_original_publisher_responses"],36)
        loan=z["v32_matched_loan_pricing_audit"]
        self.assertEqual(loan["different_facility_loan_contracts_date_eligible"],3)
        self.assertEqual([v["floating_spread_bps"] for v in loan["single_disclosed_price_per_contract_events"]],[225,450,275])
        self.assertEqual(loan["same_facility_two_eligible_amendments_verified"],0)
        self.assertIsNone(loan["net_spread_repricing_basis_points"])
        cash=z["v33_issuer_funding_and_liquidity_audit"]
        self.assertTrue(cash["q2_actual_sources_completely_reconciled"])
        rows={r["issuer"]:r for r in cash["source_eligible_2026Q2_issuer_bridges"]}
        self.assertEqual(rows["CoreWeave"]["observed_net_debt_issuance_less_repayments_usd_m"],"9573.00")
        self.assertEqual(rows["CoreWeave"]["observed_equity_issuance_or_treasury_sale_net_usd_m"],"997.00")
        self.assertEqual(rows["Nebius"]["observed_equity_issuance_or_treasury_sale_net_usd_m"],"2811.10")
        self.assertIsNone(rows["Nebius"]["observed_net_debt_issuance_less_repayments_usd_m"])
        self.assertTrue(all(x["cash_runway_months"] is None for x in rows.values()))
        governance=z["v34_evidence_governance"]
        self.assertFalse(governance["current_sec_date_gate_coreweave_2026Q3"])
        self.assertFalse(governance["24_month_independent_forward_test_available"])
        self.assertIsNone(governance["2008_numeric_similarity_pct"])
        self.assertIsNone(governance["certified_11node_aics"])
        self.assertFalse(z["self_modifying_production_model_enabled"])
        self.assertFalse(z["production_trading_enabled"])
        self.assertEqual(z["automatic_next_research_priority"],"ORIGINAL_SEC_NUMERIC_SOURCE_TO_NODE")

    def test_source_clock_rolls_forward_without_future_leakage(self):
        for cutoff, loans, cash_bridges, sec3 in (
            ("2026-04-13",0,0,False),
            ("2026-04-14",1,0,False),
            ("2026-06-01",2,0,False),
            ("2026-08-25",2,0,False),
            ("2026-08-26",2,2,False),
            ("2026-11-05",3,2,False),
            ("2026-11-25",3,2,False),
            ("2026-11-26",3,2,True),
        ):
            with self.subTest(cutoff=cutoff):
                z=self.make(cutoff)
                self.assertEqual(z["v32_matched_loan_pricing_audit"]["different_facility_loan_contracts_date_eligible"],loans)
                self.assertEqual(len(z["v33_issuer_funding_and_liquidity_audit"]["source_eligible_2026Q2_issuer_bridges"]),cash_bridges)
                self.assertIs(z["v34_evidence_governance"]["current_sec_date_gate_coreweave_2026Q3"],sec3)

    def test_refuse_false_current_credit_or_promoted_weights(self):
        for key,value in (
            ("credit_exposure_edges_verified",1),
            ("v29_nebius_citi_named_lender_funded_usd_m",3500),
            ("v30_crisis_causal_skill",0.8),
            ("v31_independently_confirmed_early_warning_skill",0.7),
            ("v31_matched_same_loan_repricing_observations",2),
        ):
            c=cycle_fixture("2026-11-22")
            c["model_improvement"][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.make(cycle=c)
        c=cycle_fixture("2026-11-22")
        c["eligible_for_production_promotion"]=True
        with self.assertRaises(ValueError):
            self.make(cycle=c)

    def test_refuse_wrong_source_date_or_added_self_promoted_research(self):
        c=cycle_fixture("2026-11-22")
        c["cutoff_date"]="2026-11-23"
        with self.assertRaises(ValueError):
            self.make(cycle=c)
        c=cycle_fixture("2026-11-22")
        c["next_experiments"][1]["priority"]=7
        with self.assertRaises(ValueError):
            self.make(cycle=c)
        c=cycle_fixture("2026-11-22")
        c["source_collection"]["successful_http_archives"]=40
        with self.assertRaises(ValueError):
            self.make(cycle=c)
        t=copy.deepcopy(self.terms)
        t["contracts"][0]["daily_compounded_sofr_float_margin_bps"]=350
        with self.assertRaises(ValueError):
            self.make(terms=t)


if __name__=="__main__":
    unittest.main()
