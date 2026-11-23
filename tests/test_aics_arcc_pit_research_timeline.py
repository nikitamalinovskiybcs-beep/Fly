"""Offline timeline policy tests; fixture rows are not live AICS observations."""
import copy
import unittest

from scripts.aics_arcc_pit_research_timeline import EvidenceGateError, build


def fixture():
    sha = "d"*64
    periods = [
        ("2026-03-31", "2026-04-28", "2026-05-12", "2.1", "1.2"),
        ("2026-06-30", "2026-07-29", "2026-08-12", "2.4", "1.4"),
        ("2026-09-30", "2026-10-27", "2026-11-10", "2.4", "1.4"),
    ]
    sources = [{
        "period_end": "2025-12-31",
        "nonaccrual_amortized_cost_percent": "1.8",
        "nonaccrual_fair_value_percent": "1.2",
        "earliest_verified_sec_filed_at": "2026-04-28",
        "earliest_verified_sec_available_at": "2026-05-12",
        "research_csv_claimed_issuer_available_at": "2026-02-18",
        "earlier_issuer_release_original_bytes_confirmed": False,
        "retrospectively_corrobated_by_sec_exhibits_count": 3,
    }]
    for period, filed, available, cost, fair in periods:
        sources.append({
            "period_end": period,
            "SEC_exhibit_url": "https://www.sec.gov/Archives/edgar/data/1287750/fixture.html",
            "SEC_source_sha256": sha,
            "SEC_filed_at": filed,
            "SEC_available_at": available,
            "nonaccrual_amortized_cost_percent": cost,
            "nonaccrual_fair_value_percent": fair,
            "original_verified": True,
            "released_historical_PIT_certified": False,
        })
    return {
        "schema_version": "aics-arcc-sec-primary-nonaccrual-independent-raw-verification-v1",
        "research_as_of": "2026-11-18",
        "independently_verified_source_transcription_values": 8,
        "verified_sec_exhibit_originals": 3,
        "original_source_html_rehashed": 4,
        "dec_2025_prior_values_independent_sec_crosschecks": 3,
        "earlier_february_issuer_release_PIT_attested": False,
        "historical_24mo_PIT_complete": False,
        "independent_24mo_predictive_OOS": False,
        "index_aics": None, "private_credit_node_stress_score": None,
        "promotion": "BLOCKED", "primary_original_archive_sha256": sha,
        "primary_archive_artifact_id": 123, "source_values": sources,
    }


class TestARCCAsOfSafety(unittest.TestCase):
    def test_eight_original_values_without_certified_node(self):
        data = build(fixture())
        self.assertEqual(len(data["disclosures"]), 8)
        self.assertEqual(len(data["historical_asof_scenarios"]), 8)
        self.assertFalse(data["baseline_issuer_feb_2026_pit_proven"])
        self.assertEqual(data["first_conservative_baseline_sec_available_at"], "2026-05-12")
        self.assertFalse(data["source_pit_historical_release_independently_attested"])
        self.assertFalse(data["private_credit_sector_representative"])
        self.assertEqual(data["synthetic_market_rows"], 0)
        self.assertIsNone(data["private_credit_node_stress_score"])
        self.assertIsNone(data["aics_index"])
        self.assertEqual(data["promotion"], "BLOCKED")

    def test_never_backdate_dec_2025_to_unverified_feb_release(self):
        scenarios = {s["historical_eval_date"]: s
                     for s in build(fixture())["historical_asof_scenarios"]}
        self.assertEqual(scenarios["2026-02-18"]["eligible_verified_value_count"], 0)
        self.assertIsNone(scenarios["2026-05-11"]["latest_visible_metrics"][
            "nonaccrual_amortized_cost_pct"]["value_pct"])
        self.assertEqual(scenarios["2026-05-12"]["eligible_verified_value_count"], 4)
        self.assertEqual(scenarios["2026-05-12"]["latest_visible_metrics"][
            "nonaccrual_amortized_cost_pct"]["period_end"], "2026-03-31")

    def test_must_wait_full_fourteen_days_and_not_forward_fill(self):
        scenarios = {s["historical_eval_date"]: s
                     for s in build(fixture())["historical_asof_scenarios"]}
        self.assertEqual(scenarios["2026-08-11"]["eligible_verified_value_count"], 4)
        self.assertEqual(scenarios["2026-08-12"]["eligible_verified_value_count"], 6)
        self.assertEqual(scenarios["2026-11-09"]["eligible_verified_value_count"], 6)
        self.assertEqual(scenarios["2026-11-10"]["eligible_verified_value_count"], 8)
        self.assertEqual(scenarios["2026-11-18"]["eligible_verified_value_count"], 8)

    def test_cost_and_fair_value_changes_keep_denominators_separate(self):
        metrics = build(fixture())["metrics"]
        self.assertEqual(metrics["nonaccrual_amortized_cost_pct"][
            "sequential_changes_percentage_points"], ["0.3", "0.3", "0.0"])
        self.assertEqual(metrics["nonaccrual_fair_value_pct"][
            "sequential_changes_percentage_points"], ["0.0", "0.2", "0.0"])
        self.assertEqual(metrics["nonaccrual_amortized_cost_pct"][
            "first_to_last_change_percentage_points"], "0.6")
        self.assertEqual(metrics["nonaccrual_fair_value_pct"][
            "first_to_last_change_percentage_points"], "0.2")
        self.assertEqual(metrics["nonaccrual_amortized_cost_pct"][
            "latest_verified_value_pct"], "2.4")

    def test_early_sec_available_date_rejected(self):
        source = fixture()
        source["source_values"][2]["SEC_available_at"] = "2026-08-11"
        with self.assertRaises(EvidenceGateError):
            build(source)

    def test_forged_early_february_original_proof_rejected(self):
        source = fixture()
        source["source_values"][0]["earlier_issuer_release_original_bytes_confirmed"] = True
        with self.assertRaises(EvidenceGateError):
            build(source)
        source = fixture()
        source["earlier_february_issuer_release_PIT_attested"] = True
        with self.assertRaises(EvidenceGateError):
            build(source)

    def test_forged_pit_scoring_or_twenty_four_month_oos_rejected(self):
        for key, value in [
            ("historical_24mo_PIT_complete", True),
            ("independent_24mo_predictive_OOS", True),
            ("private_credit_node_stress_score", 65),
            ("index_aics", 489),
            ("promotion", "CERTIFIED"),
        ]:
            with self.subTest(key=key):
                d = fixture()
                d[key] = value
                with self.assertRaises(EvidenceGateError):
                    build(d)

    def test_modified_source_value_is_not_accepted_without_raw_reverification(self):
        source = fixture()
        source["source_values"][2]["nonaccrual_fair_value_percent"] = "NaN"
        with self.assertRaises(EvidenceGateError):
            build(source)

    def test_missing_original_doc_or_quarter_rejected(self):
        source = fixture()
        source["source_values"].pop()
        with self.assertRaises(EvidenceGateError):
            build(source)
        source = fixture()
        source["source_values"][3]["period_end"] = "2027-01-01"
        with self.assertRaises(EvidenceGateError):
            build(source)

    def test_no_unattested_14d_spread_backfill(self):
        data = build(fixture())
        for item in data["disclosures"]:
            self.assertFalse(item["earliest_historical_release_pit_independently_attested"])
            self.assertFalse(item["score_eligible"])
            self.assertEqual(item["entity"], "ARCC")


if __name__ == "__main__":
    unittest.main()
