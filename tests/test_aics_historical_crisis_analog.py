"""Crisis-history falsifiability tests, never synthetic historical index."""
import copy
import unittest
from scripts.aics_historical_crisis_analog import V18, read, build, ANCHORS, timing


class HistoricalAicsAnalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=read(V18)
        cls.d=build(cls.data)

    def test_2000_and_2008_old_crossings_are_after_crisis_onset(self):
        for key in ("telecom2000","subprime2008"):
            with self.subTest(key=key):
                audit=self.d["comparison_eras"][key]["timing_audit"]
                self.assertEqual(audit["early_warning_of_crisis_onset_status"],
                                 "OLD_CROSSING_AFTER_OBSERVED_CRISIS_ONSET")
                self.assertLess(audit["earliest_possible_lead_to_later_failure_days"],
                                audit["latest_possible_lead_to_later_failure_days"])
                self.assertGreater(audit["earliest_possible_lead_to_later_failure_days"],0)
                self.assertFalse(audit["old_report_historic_crossing_independently_reproduced"])
                self.assertFalse(audit["actual_unlookahead_timing_skill_verified"])
        self.assertEqual(self.d["comparison_eras"]["telecom2000"][
                         "timing_audit"]["first_market_or_funding_crisis_date"],"2000-03-10")
        self.assertEqual(self.d["comparison_eras"]["subprime2008"][
                         "timing_audit"]["first_market_or_funding_crisis_date"],"2007-08-09")

    def test_real_october_2026_market_close_not_calendar_end(self):
        self.assertEqual(self.d["current_price_close_cutoff"],"2026-10-30")
        self.assertEqual(self.d["2026_research_observed_candidate_nodes"],8)
        self.assertEqual(self.d["2026_partial_known_weighted_points_not_full_index"],"268.39")
        self.assertEqual(self.d["2026_missing_market_close_nodes"],
                         ["AI Equities","Repo","UST 30Y"])
        self.assertTrue(self.d["repo_absence_does_not_mean_funding_is_calm"])

    def test_every_axis_unknown_until_historical_pit_calibration(self):
        self.assertEqual(self.d["feature_axis_count"],8)
        for axis in self.d["feature_axes"]:
            self.assertIsNone(axis["axis_2000_vs_2026_similarity_score"])
            self.assertIsNone(axis["axis_2008_vs_2026_similarity_score"])
            self.assertFalse(axis["historical_source_matched_by_definition"])
            self.assertFalse(axis["contemporaneous_2026_economic_mechanism_independently_verified"])
        self.assertIsNone(self.d["quantitative_similarity_percent_2000"])
        self.assertIsNone(self.d["quantitative_similarity_percent_2008"])
        self.assertIsNone(self.d["prediction_confidence_or_crisis_probability"])
        self.assertIsNone(self.d["historical_2000_2008_node_scores"])
        self.assertIsNone(self.d["full_AICS"])
        self.assertFalse(self.d["score_weights_modified"])
        self.assertFalse(self.d["trades_created"])

    def test_reject_future_score_and_falsely_certified_2000_2008_score(self):
        future=copy.deepcopy(self.data)
        future["monthly_last_weekday_market_proxy"][-1]["node_scores"][
            "Hyperscalers"]["research_eligible_date"]="2026-10-31"
        with self.assertRaises(ValueError):
            build(future)
        fake=copy.deepcopy(self.data)
        fake["full_11node_index_months"]=24
        with self.assertRaises(ValueError):
            build(fake)

    def test_timing_audit_disallows_claiming_early_when_after_onset(self):
        two=dict(ANCHORS["telecom2000"])
        two["claimed_old_aics_crossing_window"]=["2000-01-01","2000-03-01"]
        audit=timing(two)
        self.assertEqual(audit["early_warning_of_crisis_onset_status"],
                         "OLD_CROSSING_BEFORE_OBSERVED_CRISIS_ONSET")
        overlapping=dict(two)
        overlapping["claimed_old_aics_crossing_window"]=["2000-03-01","2000-04-01"]
        self.assertEqual(timing(overlapping)["early_warning_of_crisis_onset_status"],
                         "ONSET_AND_CROSSING_OVERLAP_UNCERTAIN")


if __name__=="__main__":
    unittest.main()
