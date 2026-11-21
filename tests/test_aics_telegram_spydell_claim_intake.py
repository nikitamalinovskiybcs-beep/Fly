"""Checks source screenshot evidence taxonomy; NEVER creates historical market data."""
import datetime as dt
import json
import re
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "aics_data/research/spydell_telegram_nvidia_circular_financing_claims_2026-11-18.json"
WEIGHTS = {
    "Private Credit":150,"Insurers":125,"UST 30Y":125,
    "Neoclouds":100,"AI Equities":100,"Hyperscalers":100,
    "SPV":100,"Repo":100,"Power/Data Centers":50,
    "Semiconductors Supply":50,"AI Demand":50
}

class TestTelegramIntake(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(DATA.read_text(encoding="utf-8"))
        cls.c={x["id"]:x for x in cls.doc["quantitative_claims"]}

    def test_exact_11_input_jpgs_have_sha256(self):
        xs=self.doc["telegram_source"]["images"]
        self.assertEqual(len(xs),11)
        self.assertEqual({x["filename"] for x in xs},
                         {f"10000525{i:02d}.jpg" for i in range(11)})
        for item in xs:
            self.assertRegex(item["sha256"],r"^[0-9a-f]{64}$")
            self.assertFalse(item["image_is_market_source"])

    def test_all_counterparties_are_candidate_research_only(self):
        names=self.doc["extracted_company_names"]
        self.assertGreaterEqual(len(names),23)
        self.assertEqual(len(set(x["name"] for x in names)),len(names))
        for n in names:
            self.assertFalse(n["score_eligible"])
            self.assertIsNone(n["verified_counterparty_exposure_usd"])
            self.assertTrue(set(n["candidate_nodes"]) <= set(WEIGHTS))

    def test_original_aics_nodes_unchanged(self):
        self.assertEqual(set(self.doc["fixed_aics_nodes"]),set(WEIGHTS))
        self.assertEqual(sum(WEIGHTS.values()),1050)
        self.assertEqual(self.doc["certified_node_scores"],0)
        self.assertEqual(self.doc["telegram_only_new_certified_metrics"],0)

    def test_never_inject_telegram_claims_into_aics(self):
        self.assertGreaterEqual(len(self.c),27)
        for item in self.c.values():
            self.assertFalse(item["score_eligible"])
            self.assertFalse(item["independently_verified_pit"])
            self.assertIn(item["primary_verification"],{
                "PRIMARY_SEC_AMOUNT_CORROBORATED_SOURCE_HASH_PENDING",
                "PRIMARY_SEC_RELATED_VALUE_BUT_TELEGRAM_LABEL_INACCURATE",
                "TELEGRAM_ASSERTION_PRIMARY_DEAL_UNVERIFIED",
            })
            self.assertTrue(set(item["candidate_nodes"]) <= set(WEIGHTS))
            self.assertIsInstance(item["screenshots"],list)
            self.assertTrue(item["screenshots"])
        for key in ("index_aics","predictive_skill_score","trade_signal"):
            self.assertIsNone(self.doc[key])
        self.assertEqual(self.doc["model_promotion"],"BLOCKED")

    def test_sec_filing_14_calendar_days(self):
        filing=self.doc["primary_sources"]["nvda_q2fy27_10q"]
        filed=dt.date.fromisoformat(filing["filed_at"])
        ready=dt.date.fromisoformat(filing["available_at"])
        self.assertEqual(ready-filed,dt.timedelta(days=14))
        self.assertEqual(ready.isoformat(),"2026-09-09")
        self.assertIsNone(filing["original_sec_html_sha256"])
        self.assertFalse(filing["original_source_bytes_archived_in_project"])

    def test_guarantee_maximum_not_funded_debt(self):
        gross=Decimal(str(self.c["NVDA_MAX_CONTINGENT_GUARANTEES_108_5"]["value"]))
        sb=Decimal(str(self.c["NVDA_SB_ENERGY_GUARANTEES_105"]["value"]))
        self.assertEqual(gross-sb,Decimal("3.5"))
        self.assertEqual(self.c["NVDA_MAX_CONTINGENT_GUARANTEES_108_5"]["dimension"],
                         "contingent_gross_max")
        self.assertTrue(self.doc["categorization_rules"]["unfunded_guarantees_are_not_drawn_debt"])

    def test_accounts_receivable_quarter_delta_only(self):
        cur=Decimal(str(self.c["NVDA_AR_63_059"]["value"]))
        prev=Decimal(str(self.c["NVDA_PRIOR_Q_AR_40_710"]["value"]))
        reported=Decimal(str(self.c["NVDA_AR_QOQ_DELTA_22_349"]["value"]))
        self.assertEqual(cur-prev,reported)
        self.assertEqual(self.c["NVDA_DSO_59_8"]["primary_verification"],
                         "TELEGRAM_ASSERTION_PRIMARY_DEAL_UNVERIFIED")

    def test_deferred_revenue_is_not_equal_to_customer_advance_balance(self):
        accrued=self.c["NVDA_DEFERRED_REVENUE_6_412"]
        advance=self.c["NVDA_CUSTOMER_ADVANCES_2_8"]
        self.assertEqual(Decimal(str(accrued["value"])),Decimal("6.412"))
        self.assertEqual(Decimal(str(advance["value"])),Decimal("2.8"))
        self.assertNotEqual(accrued["value"],advance["value"])
        self.assertEqual(accrued["primary_verification"],
                         "PRIMARY_SEC_RELATED_VALUE_BUT_TELEGRAM_LABEL_INACCURATE")

    def test_equity_stock_and_future_commitment_separate(self):
        market=Decimal(str(self.c["NVDA_MARKETABLE_EQUITY_42_783"]["value"]))
        private=Decimal(str(self.c["NVDA_NONMARKET_EQUITY_47_898"]["value"]))
        self.assertEqual(market+private,Decimal("90.681"))
        self.assertEqual(self.c["NVDA_90_681_SUBTOTAL"]["value"],90.681)
        self.assertEqual(self.c["NVDA_EQUITY_FUTURE_25"]["dimension"],
                         "future_equity_commitments")

    def test_cloud_and_lease_categories_never_conflated(self):
        self.assertEqual(self.c["NVDA_AI_CLOUD_COMMITMENTS_36"]["value"],36)
        self.assertEqual(self.c["NVDA_CLOUD_SERVICE_FUTURE_29"]["value"],29)
        self.assertEqual(self.c["NVDA_DC_LEASE_NOT_COMMENCED_25"]["value"],25)
        self.assertEqual(self.c["NVDA_DC_LEASE_NOT_COMMENCED_20"]["value"],20)
        for key in ("contract_amounts_may_overlap","no_sum_across_stocks_flows_guarantees_and_future_commitments"):
            self.assertTrue(self.doc["categorization_rules"][key])

    def test_alleged_private_party_financing_not_auto_approved(self):
        for ident in (
            "NVDA_COREWEAVE_TAKE_OR_PAY_6_3",
            "NVDA_FIRMUS_SHARONAI_GMI_29_7",
            "NVDA_LAMBDA_LEASE_1_5",
            "XAI_COLOSSUS_FINANCING_20",
            "NVDA_GROQ_17",
            "NVDA_OPTICS_10",
        ):
            self.assertEqual(self.c[ident]["primary_verification"],
                             "TELEGRAM_ASSERTION_PRIMARY_DEAL_UNVERIFIED")
            self.assertFalse(self.c[ident]["score_eligible"])

    def test_edges_are_not_arithmetic_additive_market_data(self):
        edges=self.doc["counterparty_edges"]
        self.assertGreaterEqual(len(edges),12)
        for edge in edges:
            self.assertFalse(edge["score_eligible"])
        self.assertFalse(self.doc["telegram_source"]["original_images_in_git_repository"])

if __name__ == "__main__":
    unittest.main()
