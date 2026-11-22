"""V55 future-only model contract: test-only hypothetical receipts != actual market data."""
from __future__ import annotations

import copy
import datetime as dt
import json
import unittest

from scripts.aics_v55_forward_prospective_conductor import (
    FROZEN,SELECTED,FROZEN_DATE,validate_freeze,build,score_candidate,
    git_blob_sha,REQUIRED_FEATURES
)

# Deliberately HYPOTHETICAL test fixture for future technical behavior.
# NEVER persist or describe these fake prices/inputs as market observations.
FIXTURE_NOW=dt.datetime(2026,12,3,14,0,tzinfo=dt.timezone.utc)
FEATURES={name:{"value":50.0 if name in ("B","S") else 5.0,
                "source_first_seen_at_utc":"2026-12-01T10:00:00+00:00",
                "source_uri":"https://example.invalid/UNIT-TEST-NOT-REAL",
                "source_sha256":"a"*64,
                "independently_attested_publication_PIT":False}
          for name in REQUIRED_FEATURES}


def mock_future():
    return {
        "schema":"aics-v55-prospective-research-snapshot-v1",
        "signal_month":"2026-11",
        "market_close_date":"2026-11-30",
        "market_close_retrieved_at_utc":"2026-12-01T09:00:00+00:00",
        "market_close_source_uri":"https://example.invalid/NOT-A-REAL-MARKET-FEED",
        "market_close_source_sha256":"b"*64,
        "forecast_created_at_utc":"2026-12-02T09:00:00+00:00",
        "features":copy.deepcopy(FEATURES),
        "certified_11node_AICS":None,
        "independent_source_delivery_pit_certified":False,
        "trading_permission":False,
    }


class V55ForwardProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen=json.loads(FROZEN.read_text(encoding="utf-8"))

    def test_five_old_experts_and_code_are_exactly_frozen(self):
        v=validate_freeze(self.frozen)
        self.assertEqual(v["five_exact_frozen_expert_ids"],list(SELECTED))
        self.assertEqual(v["default_fusion"],"median")
        self.assertEqual(v["frozen_execution_code_git_blob"],
                         "3420c289c6bd4b0387396e50937a525f19f4035e")
        self.assertEqual(git_blob_sha(b"test"),"30d74d258442c7c65512eafab474568dd706c430")
        bad=copy.deepcopy(self.frozen)
        bad["chosen_top5_agent_ids"][0]="EXPERT-100"
        with self.assertRaises(ValueError):
            validate_freeze(bad)

    def test_current_2026_11_22_has_no_new_observed_predictions(self):
        r=build(self.frozen)
        self.assertEqual(r["current_operational_status"],"AWAITING_GENUINE_FIRST_NEW_MONTH_SOURCE")
        self.assertFalse(r["first_new_prospective_month_has_real_market_and_feature_snapshot"])
        self.assertTrue(r["prospective_missing_event_outcomes_must_remain_null"])
        self.assertIsNone(r["prospective_research_score"])
        self.assertIsNone(r["full_11_node_AICS"])
        self.assertFalse(r["production_trades"])

    def test_historical_crisis_onset_is_earlier_than_reported_old_crossings(self):
        r=build(self.frozen)
        self.assertEqual(r["historical_dotcom_nasdaq_crisis_onset"],"2000-03-10")
        self.assertEqual(r["historical_funding_crisis_onset"],"2007-08-09")
        self.assertFalse(r["old_crossing_precedes_actual_2000_or_2007_onset"])
        self.assertFalse(r["old_historical_crossing_independently_reproduced"])
        self.assertFalse(r["historical_10pct_crisis_backtest_falsifiable"])

    def test_hypothetical_future_fixture_obeys_five_unchanged_algorithms(self):
        out=build(self.frozen,mock_future(),actual_now=FIXTURE_NOW)
        s=out["prospective_research_score"]
        self.assertEqual(s["market_month"],"2026-11")
        self.assertEqual([x["model_id"] for x in s["five_individual_frozen_expert_shadow_scores"]],
                         list(SELECTED))
        xs=[x["shadow_risk_0_100"] for x in s["five_individual_frozen_expert_shadow_scores"]]
        self.assertAlmostEqual(s["five_equal_weight_mean_shadow_score_NOT_AICS"],
                               round(sum(xs)/5,6))
        self.assertEqual(s["five_median_shadow_score_NOT_AICS"],sorted(xs)[2])
        self.assertIsNone(s["full_11_node_AICS"])
        self.assertEqual(s["forward_event_horizons_months"],[1,3,6])
        self.assertFalse(s["future_outcomes_matured"])
        self.assertIsNone(s["future_crisis_warning_accuracy"])
        self.assertFalse(s["trade_permission"])

    def test_future_dated_self_report_cannot_create_live_forecast_today(self):
        with self.assertRaisesRegex(ValueError,"future timestamp"):
            score_candidate(mock_future(),actual_now=dt.datetime(
                2026,11,22,13,0,tzinfo=dt.timezone.utc))

    def test_source_first_seen_after_forecast_is_blocked(self):
        x=mock_future()
        x["features"]["B"]["source_first_seen_at_utc"]="2026-12-03T10:00:00Z"
        with self.assertRaisesRegex(ValueError,"after its forecast"):
            score_candidate(x,actual_now=FIXTURE_NOW)

    def test_historical_stale_month_or_backdated_market_receipt_blocked(self):
        x=mock_future()
        x["signal_month"]="2026-10"
        x["market_close_date"]="2026-10-30"
        with self.assertRaisesRegex(ValueError,"Pre-freeze"):
            score_candidate(x,actual_now=FIXTURE_NOW)
        x=mock_future()
        x["market_close_retrieved_at_utc"]="2026-11-27T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"No scoring prior"):
            score_candidate(x,actual_now=FIXTURE_NOW)

    def test_missing_11_observed_features_or_false_pit_assertion_blocked(self):
        x=mock_future()
        x["features"].pop("BM2")
        with self.assertRaisesRegex(ValueError,"eleven"):
            score_candidate(x,actual_now=FIXTURE_NOW)
        x=mock_future()
        x["features"]["S"]["independently_attested_publication_PIT"]=True
        with self.assertRaisesRegex(ValueError,"Do not assert"):
            score_candidate(x,actual_now=FIXTURE_NOW)

    def test_invalid_hash_naive_clock_and_fictional_full_index_blocked(self):
        x=mock_future()
        x["features"]["S"]["source_sha256"]="wrong"
        with self.assertRaises(ValueError):
            score_candidate(x,actual_now=FIXTURE_NOW)
        x=mock_future()
        x["forecast_created_at_utc"]="2026-12-02T09:00:00"
        with self.assertRaisesRegex(ValueError,"Naive timestamp"):
            score_candidate(x,actual_now=FIXTURE_NOW)
        x=mock_future()
        x["certified_11node_AICS"]=500
        with self.assertRaisesRegex(ValueError,"Only unapproved"):
            score_candidate(x,actual_now=FIXTURE_NOW)


if __name__=="__main__":
    unittest.main()
