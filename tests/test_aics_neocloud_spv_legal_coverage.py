"""Offline anti-fabrication tests for AICS Neoclouds/SPV 37-company audit."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_audit_neocloud_spv_legal_exposure import audit, UNIVERSE, SEC_REGISTRY


class TestNeocloudSpvContractGaps(unittest.TestCase):
    def test_exact_sources_and_candidate_counts(self):
        result = audit()
        self.assertEqual(result["research_company_count"], 37)
        self.assertEqual(result["omi_named_count"], 26)
        self.assertEqual(result["telegram_only_count"], 11)
        self.assertEqual(result["neocloud_company_candidates"], 9)
        self.assertEqual(result["spv_company_candidates"], 13)
        self.assertEqual(len(result["private_neocloud_contract_leads"]), 6)

    def test_committed_audit_matches_reproducible_source_calculation(self):
        pinned = Path("aics_data/progress/neocloud_spv_contract_gap_audit_2026-11-18.json")
        self.assertTrue(pinned.is_file())
        self.assertEqual(audit(), json.loads(pinned.read_text(encoding="utf-8")))

    def test_date_gate_four_pass_one_embargo(self):
        result = audit()
        self.assertEqual(result["sec_date_eligible_docs"], 4)
        self.assertEqual(result["sec_embargoed_docs"], 1)
        self.assertEqual(result["sec_registry_docs"], 5)
        row = next(x for x in result["sec_documents"]
                   if x["source_id"] == "CRWV_10Q_20261112")
        self.assertEqual(row["available_at"], "2026-11-26")
        self.assertEqual(row["date_gate"], "EMBARGOED_SEC_PLUS_14_DAYS")
        self.assertFalse(row["score_eligible"])

    def test_no_unsupported_score_or_financial_aggregation(self):
        result = audit()
        self.assertGreater(result["candidate_memberships_by_node"]["SPV"], 0)
        self.assertEqual(result["original_private_contracts_confirmed"], 0)
        self.assertEqual(result["independently_verified_spv_legal_recourse_contracts"], 0)
        self.assertIsNone(result["numeric_contractual_exposure_usd"])
        self.assertIsNone(result["index_aics"])
        self.assertTrue(all(x is None for x in result["node_stress_scores"].values()))
        self.assertEqual(len(result["node_stress_scores"]), 11)
        self.assertFalse(result["independently_attested_pit"])
        self.assertFalse(result["untouched_24m_oos"])
        self.assertEqual(result["promotion"], "BLOCKED")
        self.assertFalse(result["trades_created"])

    def _mutated_universe_fails(self, modify):
        x = json.loads(UNIVERSE.read_text(encoding="utf-8"))
        modify(x)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "universe.json"
            path.write_text(json.dumps(x), encoding="utf-8")
            with self.assertRaises(ValueError):
                audit(universe_path=path)

    def test_fake_exposure_not_accepted(self):
        for key, value in (("confirmed_financial_exposure_usd", 3_500_000_000),
                           ("stress_score", 63), ("model_eligible", True)):
            with self.subTest(field=key):
                self._mutated_universe_fails(
                    lambda x: x["companies"][0].__setitem__(key, value)
                )

    def test_duplicate_company_fails(self):
        self._mutated_universe_fails(
            lambda x: x["companies"][1].__setitem__("name", "CoreWeave")
        )

    def test_telegram_mislabelled_as_omi_fails(self):
        self._mutated_universe_fails(
            lambda x: x["companies"][-1].__setitem__("origin", "OMI_PDF")
        )

    def test_secondary_contract_edge_cannot_self_certify(self):
        self._mutated_universe_fails(
            lambda x: x["reported_relationships"][0].__setitem__("score_eligible", True)
        )

    def test_immutable_weights_rejected_if_changed(self):
        self._mutated_universe_fails(
            lambda x: x["model_policy"]["fixed_weights"].__setitem__("SPV", 200)
        )

    def test_sec_embargo_cannot_be_shortened(self):
        x = json.loads(SEC_REGISTRY.read_text(encoding="utf-8"))
        x["documents"][-1]["available_at"] = "2026-11-25"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sec.json"
            path.write_text(json.dumps(x), encoding="utf-8")
            with self.assertRaises(ValueError):
                audit(sec_path=path)

    def test_no_retroactive_asof_relabeling(self):
        with self.assertRaises(ValueError):
            audit(as_of=dt.date(2026, 11, 26))


if __name__ == "__main__":
    unittest.main()
