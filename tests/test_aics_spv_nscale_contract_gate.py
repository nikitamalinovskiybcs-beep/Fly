"""Tampering fixtures for the authentic-source SPV contract-lineage gate.

These tests do not manufacture market observations or attest historical PIT.
"""
import copy
import hashlib
import json
import unittest

from scripts.aics_spv_nscale_contract_gate import (
    REGISTRY, OBSERVED, EXPECTED_CEILING, ContractEvidenceError, audit,
)


def inputs():
    raw = REGISTRY.read_bytes()
    return json.loads(raw), json.loads(OBSERVED.read_bytes()), raw


class TestNscaleSPVContractLineage(unittest.TestCase):
    def test_reproduces_original_filing_and_contract_parts_without_score(self):
        registry, observed, raw = inputs()
        report = audit(registry, observed, raw)
        self.assertEqual(report["contractual_ceiling_usd"], 1_200_000_000)
        self.assertEqual(report["fixed_commitment_usd"], 370_000_000)
        self.assertEqual(report["floating_commitment_usd"], 830_000_000)
        self.assertEqual(report["contractual_ceiling_usd"], EXPECTED_CEILING)
        self.assertEqual(report["named_borrower"], "Nscale NC Borrower SPV, LLC")
        self.assertEqual(report["named_affiliate_guarantor"], "Nscale Services US Inc.")
        self.assertEqual(report["sec_available_at"], "2026-10-02")
        self.assertEqual(report["verified_direct_source_review_contracts"], 1)
        self.assertFalse(report["original_bytes_rehashed_in_this_gate"])
        self.assertFalse(report["independently_attested_historical_pit"])
        self.assertIsNone(report["drawn_principal_usd"])
        self.assertIsNone(report["effective_recourse_usd"])
        self.assertIsNone(report["spv_node_score"])
        self.assertIsNone(report["index_aics"])
        self.assertEqual(report["promotion"], "BLOCKED")

    def test_observed_review_registry_digest_matches_actual_committed_original(self):
        registry, observed, raw = inputs()
        self.assertEqual(observed["registry_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(registry["sources"]["nscale"]["document_type"], "EX-10.24")

    def test_contractual_limit_cannot_masquerade_as_drawn_loan_or_recourse(self):
        for field, amount in (
            ("drawn_principal_from_this_agreement_usd", 1_200_000_000),
            ("effective_economic_recourse_amount_usd", 1_200_000_000),
        ):
            with self.subTest(field=field):
                r,o,raw = inputs()
                o["observations"]["nscale_nc_gpu_credit"][field] = amount
                with self.assertRaisesRegex(ContractEvidenceError, "unproven drawn"):
                    audit(r,o,raw)

    def test_forged_named_parties_and_commitments_rejected(self):
        changes = (
            ("borrower", "Unknown SPV, LLC"),
            ("affiliate_guarantor", "Nscale NC Borrower SPV, LLC"),
            ("fixed_commitment_usd", 370_000_001),
            ("floating_commitment_usd", 830_000_001),
            ("contractual_ceiling_usd", 2_000_000_000),
        )
        for key,value in changes:
            with self.subTest(field=key):
                r,o,raw = inputs()
                o["observations"]["nscale_nc_gpu_credit"][key] = value
                with self.assertRaises(ContractEvidenceError):
                    audit(r,o,raw)

    def test_filing_and_hash_substitutions_rejected(self):
        for key,value in (
            ("accession", "0001193125-26-395476"),
            ("cik", "0000000000"),
            ("document_type", "EX-10.23"),
            ("available_at", "2026-09-19"),
            ("filed_at", "2026-09-17"),
            ("document_text_sha256", "a"*64),
        ):
            with self.subTest(field=key):
                r,o,raw = inputs()
                r["sources"]["nscale"][key] = value
                with self.assertRaises(ContractEvidenceError):
                    audit(r,o,raw)

    def test_primary_source_receipt_sha_alteration_rejected(self):
        r,o,raw = inputs()
        r["sources"]["nscale"]["original"]["sha256"] = "f" * 64
        with self.assertRaises(ContractEvidenceError):
            audit(r,o,raw)

    def test_review_must_not_claim_certification_or_trade(self):
        for key,value in (
            ("independently_attested_historical_pit", True),
            ("certified_node_scores", 1),
            ("index_aics", 503),
            ("trades_created", True),
            ("production_weights_changed", True),
        ):
            with self.subTest(key=key):
                r,o,raw = inputs()
                o[key] = value
                with self.assertRaises(ContractEvidenceError):
                    audit(r,o,raw)

    def test_frozen_cutoff_cannot_be_postdated_to_2026_november_26(self):
        r,o,raw = inputs()
        r["evidence_cutoff"] = "2026-11-26"
        with self.assertRaises(ContractEvidenceError):
            audit(r,o,raw)


if __name__ == "__main__":
    unittest.main()
