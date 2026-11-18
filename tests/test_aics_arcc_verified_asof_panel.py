"""Artificial test records only: never substitute fixture data for ARCC market data."""
import datetime as dt
import unittest
from scripts.aics_arcc_verified_asof_panel import build, PanelError


def verified():
    base = {"schema_version": "aics-arcc-sec-primary-nonaccrual-independent-raw-verification-v1",
            "original_source_html_rehashed": 4, "verified_sec_exhibit_originals": 3,
            "independently_verified_source_transcription_values": 8,
            "earliest_verified_dec2025_disclosure_PIT_from_original": "2026-05-12",
            "earlier_february_issuer_release_PIT_attested": False,
            "historical_24mo_PIT_complete": False,
            "synthetic_financial_observations": 0,
            "private_credit_node_stress_score": None, "index_aics": None,
            "promotion": "BLOCKED", "primary_original_archive_sha256": "a"*64}
    base["source_values"] = [
        {"period_end": "2025-12-31", "nonaccrual_amortized_cost_percent": "1.8",
         "nonaccrual_fair_value_percent": "1.2",
         "earliest_verified_sec_filed_at": "2026-04-28",
         "earliest_verified_sec_available_at": "2026-05-12",
         "earlier_issuer_release_original_bytes_confirmed": False},
        *[{"period_end": period, "SEC_filed_at": filed, "SEC_available_at": available,
           "nonaccrual_amortized_cost_percent": cost,
           "nonaccrual_fair_value_percent": fair,
           "original_verified": True, "released_historical_PIT_certified": False}
          for period,filed,available,cost,fair in [
              ("2026-03-31","2026-04-28","2026-05-12","2.1","1.2"),
              ("2026-06-30","2026-07-29","2026-08-12","2.4","1.4"),
              ("2026-09-30","2026-10-27","2026-11-10","2.4","1.4")]]
    ]
    return base


class TestARCCVerifiedAsOfPanel(unittest.TestCase):
    def test_december_not_available_in_february(self):
        p = build(verified(), dt.date(2026,2,28))
        self.assertEqual(p["verified_observations_available_by_cutoff"], 0)
        self.assertIsNone(p["latest_known_nonaccrual_cost_pct"])

    def test_may_twelve_first_verified_original_and_q1(self):
        p = build(verified(), dt.date(2026,5,12))
        self.assertEqual(p["verified_observations_available_by_cutoff"], 2)
        self.assertEqual(p["latest_known_original_sec_period"], "2026-03-31")
        self.assertFalse(p["february_2026_unverified_claim_used"])

    def test_all_four_verified_periods_and_no_certification(self):
        p = build(verified(), dt.date(2026,11,18))
        self.assertEqual(len(p["source_observations"]), 4)
        self.assertEqual(p["latest_known_nonaccrual_cost_pct"], "2.4")
        self.assertEqual(p["latest_known_nonaccrual_fair_value_pct"], "1.4")
        self.assertIsNone(p["private_credit_node_score"])
        self.assertIsNone(p["index_aics"])
        self.assertFalse(p["independent_24m_oos"])

    def test_unverified_february_is_rejected(self):
        d=verified()
        d["source_values"][0]["earliest_verified_sec_available_at"]="2026-02-18"
        with self.assertRaises(PanelError):
            build(d, dt.date(2026,11,18))

    def test_bad_sec_14_day_gate_rejected(self):
        d=verified()
        d["source_values"][2]["SEC_available_at"]="2026-07-30"
        with self.assertRaises(PanelError):
            build(d, dt.date(2026,11,18))

    def test_false_score_promotion_rejected(self):
        d=verified()
        d["private_credit_node_stress_score"]=62
        with self.assertRaises(PanelError):
            build(d, dt.date(2026,11,18))


if __name__=="__main__":
    unittest.main()
