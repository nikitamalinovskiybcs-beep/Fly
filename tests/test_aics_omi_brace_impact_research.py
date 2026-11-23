"""OMI 2026 research must never silently become AICS market observations."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "aics_data/research/omi_brace_for_impact_oct2026_hypotheses.json"
FIXED = {
    "Private Credit":150,"Insurers":125,"UST 30Y":125,
    "Neoclouds":100,"AI Equities":100,"Hyperscalers":100,
    "SPV":100,"Repo":100,"Power/Data Centers":50,
    "Semiconductors Supply":50,"AI Demand":50,
}


class TestOMIHypotheses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=json.loads(DATA.read_text(encoding="utf-8"))

    def test_both_pdf_versions_are_sha_verified_but_not_numeric_source_proof(self):
        receipt=ROOT / "aics_data/research/omi_brace_impact_original_pdf_sha_receipt_2026-11-18.json"
        data=json.loads(receipt.read_text(encoding="utf-8"))
        checks=data["independent_sha_recalculation"]
        self.assertEqual(checks["pdfs_checked"],2)
        self.assertEqual(checks["pdf_hashes_matching_manifest"],2)
        self.assertNotEqual(checks["original_openmarkets_pdf_sha256"],
                            checks["mirror_afref_pdf_sha256"])
        self.assertFalse(data["claims_from_pdf_primary_source_verified"])
        self.assertFalse(data["metrics_from_financial_primary_sources_verified"])
        self.assertIsNone(data["index_aics"])
        self.assertEqual(data["promotion"],"BLOCKED")

    def test_11_immutable_nodes_and_weights(self):
        nodes=self.d["nodes"]
        self.assertEqual(len(nodes),11)
        self.assertEqual({x["node"]:x["weight"] for x in nodes},FIXED)
        self.assertEqual(sum(x["weight"] for x in nodes),1050)

    def test_policy_paper_bytes_verified_but_market_numbers_unverified(self):
        s=self.d["source"]
        self.assertEqual(s["classification"],"SECONDARY_POLICY_RESEARCH_NOT_PRIMARY_SOURCE_NUMERIC_EVIDENCE")
        self.assertTrue(s["original_pdf_bytes_locally_archived"])
        self.assertEqual(s["pdf_sha256"],"466b8a875752c85e23a41d5e33ad985c44f437ddc5cf801e132310c4e28bff60")
        self.assertFalse(s["alternate_publisher_pdf_identical"])
        self.assertEqual(s["original_source_pdf_pages"],88)
        self.assertFalse(s["independent_primary_numeric_sources_verified"])
        self.assertEqual(s["publication_date"],"2026-10-16")

    def test_no_node_claims_a_score_pit_or_out_of_sample_proof(self):
        d=self.d
        for n in d["nodes"]:
            self.assertIsNone(n["validated_score"])
            self.assertFalse(n["independently_verified_pit"])
            self.assertTrue(n["research_only"])
        p=d["safety"]
        self.assertEqual(p["validated_node_scores"],0)
        self.assertEqual(p["promotion"],"BLOCKED")
        for name in ("index_aics","model_score","predictive_skill_score","trade_signal"):
            self.assertIsNone(p[name])
        self.assertFalse(p["create_score"])
        self.assertFalse(p["modify_node_weights"])
        self.assertFalse(p["add_new_nodes"])
        self.assertFalse(p["allow_secondary_claims_as_certified_market_observations"])

    def test_all_secondary_numbers_remain_explicitly_unverified(self):
        claims=self.d["reported_quantitative_claims"]
        self.assertGreaterEqual(len(claims),8)
        for c in claims:
            self.assertIs(c["score_eligible"],False)
            self.assertIs(c["independently_verified"],False)
            self.assertIsInstance(c["reported_value"],(float,int))
            self.assertIsInstance(c["reported_unit"],str)
            self.assertIsInstance(c["primary_attribution"],str)
        self.assertEqual(len({c["id"] for c in claims}),len(claims))

    def test_contagion_edges_connect_only_fixed_nodes_and_are_hypotheses(self):
        edges=self.d["hypothesized_contagion_edges"]
        self.assertGreaterEqual(len(edges),10)
        for e in edges:
            self.assertIn(e["from"],FIXED)
            self.assertIn(e["to"],FIXED)
            self.assertNotEqual(e["from"],e["to"])
            self.assertIn(e["direction"],{"hypothesis","indirect_hypothesis"})

    def test_mandatory_sec_14_day_and_alfred_rule(self):
        p=self.d["safety"]
        self.assertEqual(p["sec_available_at"],"filed_at_plus_14_calendar_days")
        self.assertIs(p["alfred_requires_historical_vintage"],True)

    def test_every_fixed_node_has_primary_source_tasks(self):
        for n in self.d["nodes"]:
            self.assertTrue(n["research_hypotheses"])
            self.assertTrue(n["direct_proof_needed"])
            self.assertIn(n["relation"],{"explicit","indirect"})

    def test_repo_and_long_treasury_are_not_promoted_as_explicit(self):
        roles={n["node"]:n["relation"] for n in self.d["nodes"]}
        self.assertEqual(roles["Repo"],"indirect")
        self.assertEqual(roles["UST 30Y"],"indirect")

if __name__=="__main__":
    unittest.main()
