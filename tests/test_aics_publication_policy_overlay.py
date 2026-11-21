"""Research-date policy guardrails; no certification or invented historical PIT."""
import copy
import unittest

from scripts.aics_publication_policy import (
    first_eligible_close_session, legacy_eligibility, research_eligibility,
)
from scripts.aics_research_publication_overlay import build, score

SRC = "https://www.sec.gov/Archives/edgar/data/1018724/original.htm"


class PublicationPolicyTest(unittest.TestCase):
    def test_legacy_is_immutable_plus14(self):
        result = legacy_eligibility(source_url=SRC, filed_at="2025-10-30")
        self.assertEqual(result.eligible_date, "2025-11-13")
        self.assertEqual(result.mode, "legacy_sec_plus14")
        self.assertFalse(result.independently_pit_attested)

    def test_original_sec_date_only_conservative_next_calendar_day(self):
        result = research_eligibility(
            source_url=SRC, filed_at="2025-10-30",
            public_date="2025-10-30")
        self.assertEqual(result.eligible_date, "2025-10-31")
        self.assertEqual(result.evidence_strength, "date_only_unverified_public_time")
        self.assertFalse(result.independently_pit_attested)

    def test_verified_public_timestamp_keeps_ny_date(self):
        result = research_eligibility(
            source_url=SRC, filed_at="2025-10-30",
            public_at="2025-10-30T20:59:00Z",
            proof_type="sec_public_dissemination")
        self.assertEqual(result.eligible_date, "2025-10-30")
        self.assertFalse(result.independently_pit_attested)

    def test_after_close_requires_actual_next_market_session(self):
        sessions = ["2025-10-30", "2025-10-31", "2025-11-03"]
        eligible = first_eligible_close_session(
            source_url=SRC, filed_at="2025-10-30",
            public_at="2025-10-30T21:01:00Z",
            proof_type="sec_public_dissemination", sessions=sessions)
        self.assertEqual(eligible, "2025-10-31")

    def test_before_close_same_session_allowed(self):
        eligible = first_eligible_close_session(
            source_url=SRC, filed_at="2025-10-30",
            public_at="2025-10-30T19:00:00Z",
            proof_type="sec_public_dissemination",
            sessions=["2025-10-30", "2025-10-31"])
        self.assertEqual(eligible, "2025-10-30")

    def test_date_only_never_claims_same_day_session(self):
        eligible = first_eligible_close_session(
            source_url=SRC, filed_at="2025-10-30",
            public_date="2025-10-30",
            sessions=["2025-10-30", "2025-10-31"])
        self.assertEqual(eligible, "2025-10-31")

    def test_no_naive_timestamp_or_accepted_only_proof(self):
        with self.assertRaises(ValueError):
            research_eligibility(
                source_url=SRC, filed_at="2025-10-30",
                public_at="2025-10-30T15:00:00",
                proof_type="sec_public_dissemination")
        with self.assertRaises(ValueError):
            research_eligibility(
                source_url=SRC, filed_at="2025-10-30",
                public_at="2025-10-30T19:00:00Z",
                proof_type="sec_accepted")
        with self.assertRaises(ValueError):
            research_eligibility(
                source_url=SRC, filed_at="2025-10-30",
                public_date="2025-10-29")

    def test_provenance_and_session_calendar_fail_closed(self):
        with self.assertRaises(ValueError):
            research_eligibility(source_url="http://invalid", filed_at="2025-10-30",
                                 public_date="2025-10-30")
        with self.assertRaises(ValueError):
            first_eligible_close_session(
                source_url=SRC, filed_at="2025-10-30",
                public_date="2025-10-30", sessions=["2025-10-31", "2025-10-30"])


class ResearchOverlayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = build()

    def test_q1_to_q4_actual_quarterly_source_events(self):
        events = self.report["research_events"]
        self.assertEqual([r["quarter"] for r in events],
                         ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"])
        self.assertEqual([r["research_first_eligible_date_proxy"] for r in events],
                         ["2025-05-03", "2025-08-02", "2025-10-31", "2026-02-06"])
        self.assertEqual([r["legacy_first_eligible_plus14"] for r in events],
                         ["2025-05-16", "2025-08-15", "2025-11-13", "2026-02-19"])
        self.assertTrue(all(r["candidate_gap_score"] == "0.00" for r in events))
        self.assertEqual([r["cash_gap_usd_m"] for r in events],
                         [42333, 40224, 61724, 60201])

    def test_conservative_monthly_coverage_no_invented_aics(self):
        report = self.report
        self.assertEqual(report["months"], 24)
        self.assertEqual(report["new_coverage_source_weight_months"], 1500)
        self.assertEqual(report["baseline_research_weight_months"], 8075)
        self.assertEqual(report["alternative_research_weight_months"], 9575)
        self.assertEqual(report["baseline_coverage_pct"], "32.04")
        self.assertEqual(report["alternative_coverage_pct"], "38.00")
        rows = {m["month"]:m for m in report["monthly"]}
        self.assertFalse(rows["2025-04"]["additional_source_research_node"])
        self.assertTrue(rows["2025-05"]["additional_source_research_node"])
        self.assertEqual(rows["2025-10"]["new_research_2025_source_period"], "2025-Q3")
        self.assertEqual(rows["2025-10"]["new_research_2025_source_available_at_proxy"], "2025-10-31")
        self.assertFalse(rows["2026-08"]["additional_source_research_node"])
        self.assertTrue(all(m["full_historical_aics"] is None and
                            m["aics_sp500_spread"] is None and
                            not m["independent_pit_certified"] for m in report["monthly"]))
        self.assertFalse(report["source_timestamp_pit_attested"])

    def test_nonpositive_capex_and_fabricated_full_score_rejected(self):
        with self.assertRaises(ValueError):
            score(100, 0)
        from scripts.aics_research_publication_overlay import read, BASELINE
        old = copy.deepcopy(read(BASELINE))
        old["monthly"][0]["full_11_node_aics_no_multiplier"] = "123.45"
        with self.assertRaises(ValueError):
            build(old=old)


if __name__ == "__main__":
    unittest.main()
