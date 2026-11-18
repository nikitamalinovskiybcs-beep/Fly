"""AICS company universe expansion must not alter its fixed 11-node index.

Only PDF/Telegram entity provenance, candidate roles and project graphs are
validated here. These are not historical market facts or model score tests.
"""
import json
import unittest
from pathlib import Path

REGISTRY=Path(__file__).resolve().parent.parent / (
    "aics_data/research/aics_extended_company_universe_omi_telegram_2026-11-18.json"
)
WEIGHTS={"Private Credit":150,"Insurers":125,"UST 30Y":125,"Neoclouds":100,
         "AI Equities":100,"Hyperscalers":100,"SPV":100,"Repo":100,
         "Power/Data Centers":50,"Semiconductors Supply":50,"AI Demand":50}


class TestAICSExtendedIssuerUniverse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.companies={c["name"]:c for c in cls.d["companies"]}

    def test_fixed_elevent_nodes_and_weights(self):
        p=self.d["model_policy"]
        self.assertEqual(p["fixed_node_count"],11)
        self.assertEqual(p["fixed_weights"],WEIGHTS)
        self.assertEqual(sum(p["fixed_weights"].values()),1050)
        self.assertTrue(p["expanding_entity_universe_does_not_expand_index_weights"])

    def test_37_exactly_separated_company_candidates(self):
        d=self.d
        self.assertEqual(len(d["companies"]),37)
        self.assertEqual(len(self.companies),37)
        self.assertEqual(d["collections"]["company_count"],37)
        self.assertEqual(d["collections"]["pdf_named_count"],26)
        self.assertEqual(d["collections"]["telegram_only_count"],11)
        self.assertEqual(
            sum(c["origin"]=="OMI_PDF" for c in d["companies"]),26
        )

    def test_small_neoclouds_separate_by_primary_versus_telegram_provenance(self):
        d=self.d["collections"]
        self.assertEqual(set(d["pdf_specific_named_neoclouds"]),
                         {"CoreWeave","Nebius Group","Crusoe Energy"})
        self.assertEqual(set(d["telegram_only_small_neocloud_candidates"]),
                         {"Lambda","Firmus","SharonAI","GMI","Nscale"})
        for name in d["pdf_specific_named_neoclouds"]:
            self.assertEqual(self.companies[name]["origin"],"OMI_PDF")
            self.assertIn("Neoclouds",self.companies[name]["candidate_nodes"])
            self.assertTrue(self.companies[name]["original_pdf_pages"])
        for name in d["telegram_only_small_neocloud_candidates"]:
            self.assertEqual(self.companies[name]["origin"],
                             "TELEGRAM_SCREENSHOTS_NOT_IN_OMI_PDF")
            self.assertEqual(self.companies[name]["original_pdf_pages"],[])
            self.assertIn("Neoclouds",self.companies[name]["candidate_nodes"])

    def test_all_company_roles_are_candidates_not_certified_scores(self):
        for x in self.d["companies"]:
            self.assertTrue(x["candidate_nodes"])
            self.assertTrue(set(x["candidate_nodes"]) <= set(WEIGHTS))
            self.assertIsNone(x["stress_score"])
            self.assertIsNone(x["confirmed_financial_exposure_usd"])
            self.assertFalse(x["model_eligible"])

    def test_original_pdf_sha_is_version_pinned(self):
        pdf=self.d["source_pdf"]
        self.assertEqual(pdf["sha256"],
            "466b8a875752c85e23a41d5e33ad985c44f437ddc5cf801e132310c4e28bff60")
        self.assertEqual(pdf["source_type"],"SECONDARY_POLICY_RESEARCH")
        for x in self.d["companies"]:
            if x["origin"]=="OMI_PDF":
                self.assertTrue(all(isinstance(p,int) and 1<=p<=88
                                    for p in x["original_pdf_pages"]))

    def test_no_telegram_or_paper_figures_promoted_to_primary_exposure(self):
        for x in self.d["reported_relationships"]:
            self.assertFalse(x["score_eligible"])
            self.assertFalse(x["legal_entity_ciks_verified"])
            self.assertIn(x["source_status"],{
                "OMI_PDF_SECONDARY_NOT_CONTRACT_ATTESTED",
                "TELEGRAM_SCREENSHOTS_NOT_IN_OMI_PDF",
            })
            for amount in x["reported_terms"]:
                self.assertIn("secondary_report",amount["kind"])
                self.assertIn(amount["unit"],{"USD billion"})
        self.assertTrue(self.d["model_policy"]["entity_mention_does_not_prove_contractual_exposure"])

    def test_abillene_project_lenders_not_confused_with_neoclouds(self):
        entities=self.companies
        self.assertEqual(entities["JPMorgan Chase"]["role"],"bank_lender_counterparty")
        self.assertNotIn("Neoclouds",entities["JPMorgan Chase"]["candidate_nodes"])
        self.assertIn("SPV",entities["Primary Digital Infrastructure"]["candidate_nodes"])
        self.assertIn("Power/Data Centers",entities["Lancium"]["candidate_nodes"])
        self.assertIn("Private Credit",entities["Blue Owl Capital"]["candidate_nodes"])
        self.assertEqual(entities["Egan Jones"]["role"],"external_rating_agency")

    def test_research_universe_does_not_open_any_progress_or_trading_gate(self):
        p=self.d["model_policy"]
        self.assertEqual(p["progress_milestone_from_name_discovery"],0)
        self.assertEqual(p["independently_validated_model_scores"],0)
        self.assertIsNone(p["certified_aics"])
        self.assertIsNone(p["all_new_company_scores"])
        self.assertTrue(p["one_economic_exposure_must_not_double_count_across_nodes"])
        self.assertEqual(p["sec_mandatory_available_at"],"filed_at_plus_14_calendar_days")

    def test_company_from_telegram_cannot_claim_paper_pages(self):
        for c in self.d["companies"]:
            if c["origin"]=="TELEGRAM_SCREENSHOTS_NOT_IN_OMI_PDF":
                self.assertFalse(c["original_pdf_pages"])
                self.assertTrue(c["telegram_image_ids"])

    def test_omit_macro_nodes_from_direct_company_stress_scoring(self):
        self.assertFalse(any(x["model_eligible"] for x in self.d["companies"]))
        self.assertEqual(self.d["status"],"CANDIDATE_UNIVERSE_NOT_MODEL_PROMOTION")


if __name__=="__main__":
    unittest.main()
