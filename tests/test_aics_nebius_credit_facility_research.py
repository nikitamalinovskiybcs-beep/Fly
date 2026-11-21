"""Guard a real SEC 6-K financing record from unsafe PIT or SPV promotion."""
import datetime as dt
import json
import re
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / (
    "aics_data/research/nebius_sec_6k_credit_facility_2026_10_22.json"
)

class TestNebiusFacilitySourceTerms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(DATA.read_text(encoding="utf-8"))

    def test_sec_filing_14_calendar_day_availability(self):
        d = self.record
        filed = dt.date.fromisoformat(d["source_filing_date"])
        available = dt.date.fromisoformat(d["available_at"])
        self.assertEqual(available - filed, dt.timedelta(days=14))
        self.assertEqual(available, dt.date(2026, 11, 5))
        self.assertLessEqual(available, dt.date.fromisoformat(d["as_of"]))

    def test_primary_sec_provenance_without_false_sha(self):
        d = self.record
        self.assertRegex(d["source_url"],
                         r"^https://www\.sec\.gov/Archives/edgar/data/1513845/000110465926117978/[A-Za-z0-9_.-]+\.htm$")
        self.assertEqual(d["source_accession"], "0001104659-26-117978")
        self.assertIsNone(d["raw_source_sha256"])
        self.assertFalse(d["original_source_bytes_archived"])
        self.assertFalse(d["independently_verified_pit"])

    def test_contractual_facility_is_not_disbursed_debt(self):
        terms = self.record["terms"]
        self.assertEqual(terms["aggregate_principal_capacity_usd"], 3500000000)
        self.assertIsNone(terms["amount_currently_drawn_usd"])
        self.assertEqual(terms["facility_type"], "senior_secured_term_loan_bridge")

    def test_spread_is_term_sofr_not_daily_sofr(self):
        terms = self.record["terms"]
        self.assertEqual(terms["borrowing_reference_rate"], "Term SOFR")
        self.assertEqual(terms["initial_margin_basis_points"], 275)
        self.assertEqual(terms["step_up_basis_points_per_90_day_period"], 25)
        self.assertEqual(terms["max_margin_basis_points"], 350)
        self.assertTrue(terms["margin_adjustments_possible"])

    def test_legal_structure_is_not_proven_spv(self):
        d = self.record
        self.assertEqual(set(d["candidate_nodes"]), {"SPV", "Neoclouds"})
        self.assertFalse(d["spv_legal_structure_proven"])
        self.assertEqual(len(d["terms"]["borrower_entities"]), 3)

    def test_correct_term_and_filing_dates(self):
        terms = self.record["terms"]
        self.assertEqual(terms["agreement_date"], "2026-10-17")
        self.assertEqual(terms["maturity_date"], "2027-10-16")
        self.assertLess(dt.date.fromisoformat(terms["agreement_date"]),
                        dt.date.fromisoformat(terms["maturity_date"]))

    def test_no_numeric_index_or_trading_signal(self):
        d = self.record
        for field in ("observed_stress_score_0_100", "spv_node_score",
                      "neoclouds_node_score", "index_aics", "model_score"):
            self.assertIsNone(d[field])
        self.assertFalse(d["score_eligible"])
        self.assertTrue(d["research_only"])
        self.assertFalse(d["trades_created"])

    def test_no_unverified_primary_source_backfill(self):
        d = self.record
        as_of_prior = dt.date(2026, 11, 4)
        eligible = dt.date.fromisoformat(d["available_at"])
        self.assertGreater(eligible, as_of_prior)
        self.assertEqual(d["historical_cutoff_rule"],
                         "SEC_FILED_PLUS_14_CALENDAR_DAYS")


if __name__ == "__main__":
    unittest.main()
