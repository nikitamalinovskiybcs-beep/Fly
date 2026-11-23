"""Fail-closed real-registry checks; mutations are parser fixtures, NOT market data."""
import copy
import json
import unittest
from pathlib import Path

from scripts.aics_reconcile_company_universe import audit

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "aics_data/research/aics_extended_company_universe_omi_telegram_2026-11-18.json"
STATUS = ROOT / "aics_data/progress/status.json"


class TestCompanyReconciliation(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.status = json.loads(STATUS.read_text(encoding="utf-8"))

    def test_all_real_registry_candidates_are_accounted_for_without_scores(self):
        result = audit(self.registry, self.status)
        self.assertEqual(result["counts"],
                         {"all_candidates": 37, "omi_pdf_named": 26,
                          "telegram_only": 11, "separate_project_groups": 3})
        self.assertEqual(len(result["nodes"]), 11)
        self.assertEqual(result["nodes"]["UST 30Y"]["omi_pdf_mentions"], [])
        self.assertIn("Crusoe Energy", result["nodes"]["Neoclouds"]["omi_pdf_mentions"])
        self.assertIn("Lambda", result["nodes"]["Neoclouds"]["telegram_only_leads"])
        self.assertIsNone(result["index_aics"])
        self.assertIsNone(result["aggregated_exposure_usd"])
        self.assertEqual(result["milestones_added"], 0)
        self.assertEqual(result["promotion"], "BLOCKED")
        self.assertTrue(all(p["verified_drawn_exposure_usd"] is None
                            and not p["score_eligible"] for p in result["projects"]))

    def test_duplicate_company_blocked(self):
        r = copy.deepcopy(self.registry)
        r["companies"][1]["name"] = r["companies"][0]["name"].upper()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit(r, self.status)

    def test_telegram_cannot_claim_omi_page_or_primary_label(self):
        for field, replacement in (("original_pdf_pages", [35]),
                                   ("raw_source_status", "issuer_ir_archived")):
            r = copy.deepcopy(self.registry)
            candidate = next(c for c in r["companies"]
                             if c["origin"] == "TELEGRAM_SCREENSHOTS_NOT_IN_OMI_PDF")
            candidate[field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit(r, self.status)

    def test_invalid_extra_node_or_exposure_blocked(self):
        for field, replacement in (("candidate_nodes", ["Phoenix"]),
                                   ("confirmed_financial_exposure_usd", 100),
                                   ("stress_score", 75),
                                   ("model_eligible", True)):
            r = copy.deepcopy(self.registry)
            r["companies"][0][field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit(r, self.status)

    def test_unknown_counterparty_and_false_project_attestation_blocked(self):
        for field, replacement in (("entities", ["Fictional borrower"]),
                                   ("legal_entity_ciks_verified", True),
                                   ("score_eligible", True)):
            r = copy.deepcopy(self.registry)
            r["reported_relationships"][0][field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit(r, self.status)

    def test_secondary_reported_terms_cannot_become_primary_or_drawn(self):
        r = copy.deepcopy(self.registry)
        r["reported_relationships"][0]["reported_terms"][0]["kind"] = "verified_drawn_debt"
        with self.assertRaisesRegex(ValueError, "primary amount"):
            audit(r, self.status)

    def test_sec_embargo_and_weight_constants_cannot_change(self):
        for field, replacement in (("sec_mandatory_available_at", "filed_at"),
                                   ("fixed_weights", {"SPV": 100})):
            r = copy.deepcopy(self.registry)
            r["model_policy"][field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit(r, self.status)

    def test_competing_progress_status_cannot_promote_company_leads(self):
        for field, replacement in (("index_aics", 497),
                                   ("source_pit_attested_nodes", 1),
                                   ("promotion", "CERTIFIED")):
            s = copy.deepcopy(self.status)
            s[field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit(self.registry, s)

    def test_failed_source_date_or_pdf_hash_is_rejected(self):
        r = copy.deepcopy(self.registry)
        r["source_as_of"] = "2026-11-19"
        with self.assertRaises(ValueError):
            audit(r, self.status)
        r = copy.deepcopy(self.registry)
        r["source_pdf"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            audit(r, self.status)


if __name__ == "__main__":
    unittest.main()
