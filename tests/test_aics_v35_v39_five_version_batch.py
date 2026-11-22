"""Five V35-V39 real-source experiments and fail-closed gates.

Only cycle metadata are minimal test fixtures; market/cash/SEC observations
come from the previously verified original-source research ledgers.
"""
from __future__ import annotations

import copy
import unittest

from scripts.aics_v35_v39_five_version_batch import (
    build, v35_cash_signal, v36_issuer_attribution, v37_funding,
    v38_credit_crosscheck, v39_governance,
)
from scripts.aics_early_imbalance_cashflow_shadow import (
    build as cash_build, read, Y2025, Q42025, Q12026, Q22026, Q32026,
)
from scripts.aics_v30_cashflow_financing_bridge import (
    build as funding_build, FUNDING, CASH, SEC,
)
from scripts.aics_v31_interest_repo_dual_clock import (
    build as interest_build, INTEREST, REPO,
)
from scripts.aics_spv_funding_transmission_bridge import (
    build as spv_build,CORE,CLOUD,NSCALE,DFS,
)
from scripts.aics_v28_credit_relationship_topology import from_originals
from scripts.aics_v29_refinancing_maturity_overlay import build as maturity_build,TERMS
from scripts.aics_historical_crisis_analog import build as historical_build,V18


def cycle_metadata(date):
    return {
        "schema":"aics-30-agent-evidence-to-improvement-loop-v1",
        "cutoff_date":date,"agent_groups":{"total_distinct_roles_executed":30},
        "cycle_decision":"RESEARCH_ONLY_NOT_AUTONOMOUS_PRODUCTION",
        "complete_11_node_aics":None,"eligible_for_production_promotion":False,
        "weights_changed":False,"trades_created":False,
        "source_collection":{"http_attempts":36,"successful_http_archives":36},
        "next_experiments":[
            {"priority":1,"experiment":"ORIGINAL_SEC_NUMERIC_SOURCE_TO_NODE","decision":"RESEARCH"},
            {"priority":2,"experiment":"SPV_CREDIT_RECOURSE_NETWORK","decision":"RESEARCH"},
        ],
    }


def rotation_metadata(date):
    return {
        "schema":"aics-v32-v34-auto-research-batch-gated-v1",
        "utc_as_of":date,"agents_exec_group_count":30,
        "production_trading_enabled":False,
        "self_modifying_production_model_enabled":False,
        "v34_evidence_governance":{
            "certified_11node_aics":None,
            "verified_current_named_lender_dollar_exposure_edges":0,
        },
        "automatic_next_research_priority":"ORIGINAL_SEC_NUMERIC_SOURCE_TO_NODE",
    }


class V35V39RealSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cash_inputs=[read(x) for x in (Y2025,Q42025,Q22026,Q32026)]
        cls.q1=read(Q12026)
        cls.finance_inputs=[read(x) for x in (FUNDING,CASH,SEC)]
        cls.ir=read(INTEREST);cls.repo=read(REPO)
        cls.spv_inputs=[read(x) for x in (CORE,CLOUD,NSCALE,DFS)]
        cls.maturity_terms=read(TERMS)
        cls.historical=historical_build(read(V18))

    def data(self,date="2026-11-22"):
        cash=cash_build(*self.cash_inputs,q1=self.q1,as_of=date)
        finance=funding_build(*self.finance_inputs,as_of=date)
        interest=interest_build(self.ir,self.repo,finance,as_of=date)
        spv=spv_build(*self.spv_inputs,as_of=date)
        topology=from_originals(spv,as_of=date)
        maturity=maturity_build(self.maturity_terms,spv,topology,as_of=date)
        return [cash,finance,interest,maturity,cycle_metadata(date),
                rotation_metadata(date),self.historical]

    def test_five_versions_real_results_not_abstract_scaffolding(self):
        report=build(*self.data(),as_of="2026-11-22")
        self.assertEqual(report["version_count"],5)
        self.assertEqual([r["name"].split("_")[0] for r in report["versions"]],
                         ["V35","V36","V37","V38","V39"])
        a,b,c,e,f=report["versions"]
        self.assertEqual(a["observed_complete_calendar_quarters"],7)
        self.assertEqual(a["first_four_issuer_negative_gap_quarter"],"2026-Q3")
        self.assertEqual(a["first_eligible_source_date"],"2026-11-13")
        self.assertEqual([r["ocf_minus_cash_ppe_usd_m"] for r in a["calendar_quarter_points"][-4:]],
                         ["60201","20977","6709","-26425"])
        self.assertEqual(b["total_observed_deterioration_usd_m"],"-33134")
        self.assertEqual(b["largest_contributing_issuer"],"Amazon")
        self.assertEqual(b["largest_contributor_share_of_net_deterioration_pct"],"78.52")
        self.assertEqual(c["source_eligible_q2_issuers"],2)
        funding={x["issuer"]:x for x in c["same_quarter_issuer_financing_evidence"]}
        self.assertEqual(funding["CoreWeave"]["observed_debt_issuance_net_of_costs_less_repayments_usd_m"],"9573")
        self.assertEqual(funding["Nebius"]["reported_equity_net_cash_receipts_usd_m"],"2811.1")
        self.assertIsNone(funding["Nebius"]["observed_debt_issuance_net_of_costs_less_repayments_usd_m"])
        self.assertEqual(e["eligible_contractual_facility_count"],3)
        self.assertEqual(e["near_term_365d_contractual_maturity_count"],1)
        self.assertEqual(e["earliest_known_contract_maturity"],"2027-10-16")
        self.assertFalse(e["coreweave_Q3_SEC_10Q_calendar_gate_passed"])
        self.assertEqual(e["coreweave_Q3_IR_net_interest_over_revenue_pct_research_only"],"23.1")
        self.assertIsNone(e["matched_instrument_new_spread_change_bps"])
        self.assertEqual(f["actual_agent_roles_executed"],30)
        self.assertEqual(f["2000_historical_first_crisis_warning_reproduced"],False)
        self.assertEqual(f["2008_historical_first_crisis_warning_reproduced"],False)
        self.assertIsNone(f["approved_full_AICS"])
        self.assertIsNone(report["PIT_attested_full_11_node_index"])
        self.assertEqual(report["synthetic_rows_added"],0)
        self.assertFalse(report["trades_created"])

    def test_sec_dates_protect_q3_signal_and_ir(self):
        for date,n,first,sec in (
            ("2026-08-25",5,None,False),
            ("2026-08-26",6,None,False),
            ("2026-11-12",6,None,False),
            ("2026-11-13",7,"2026-Q3",False),
            ("2026-11-25",7,"2026-Q3",False),
            ("2026-11-26",7,"2026-Q3",True),
        ):
            with self.subTest(asof=date):
                a,b,c,e,_,_,_=self.data(date)
                o=v35_cash_signal(a,__import__("datetime").date.fromisoformat(date))
                self.assertEqual(o["observed_complete_calendar_quarters"],n)
                self.assertEqual(o["first_four_issuer_negative_gap_quarter"],first)
                self.assertEqual(v38_credit_crosscheck(e,c,__import__("datetime").date.fromisoformat(date))["coreweave_Q3_SEC_10Q_calendar_gate_passed"],sec)
                if date<"2026-11-13":
                    self.assertIsNone(v36_issuer_attribution(a,o,__import__("datetime").date.fromisoformat(date))["total_observed_deterioration_usd_m"])

    def test_forged_issuer_cash_source_or_credit_claim_fails_closed(self):
        import datetime as dt
        vals=self.data()
        cash=copy.deepcopy(vals[0])
        r=next(r for r in cash["quarterly_original_issuer_records"]
               if r["period"]=="2026-Q3" and r["issuer"]=="Amazon")
        r["cash_gap_usd_m"]="1"
        with self.assertRaises(ValueError):
            v35_cash_signal(cash,dt.date(2026,11,22))
        finance=copy.deepcopy(vals[1])
        finance["source_first_pit_provider_delivery_attested"]=True
        with self.assertRaises(ValueError):
            v37_funding(finance,dt.date(2026,11,22))
        interest=copy.deepcopy(vals[2])
        interest["matched_same_loan_spread_repricing_events_verified"]=1
        with self.assertRaises(ValueError):
            v38_credit_crosscheck(vals[3],interest,dt.date(2026,11,22))

    def test_historical_claim_or_autonomous_promotion_fails_closed(self):
        import datetime as dt
        vals=self.data()
        future=copy.deepcopy(vals[6])
        future["quantitative_similarity_percent_2008"]=76
        with self.assertRaises(ValueError):
            v39_governance(vals[4],vals[5],future,dt.date(2026,11,22))
        rot=copy.deepcopy(vals[5])
        rot["self_modifying_production_model_enabled"]=True
        with self.assertRaises(ValueError):
            v39_governance(vals[4],rot,vals[6],dt.date(2026,11,22))
        cycle=copy.deepcopy(vals[4])
        cycle["source_collection"]["successful_http_archives"]=40
        with self.assertRaises(ValueError):
            v39_governance(cycle,vals[5],vals[6],dt.date(2026,11,22))


if __name__=="__main__":
    unittest.main()
