"""V56 online learner tests. Artificial dates/prices below are UNIT TESTS ONLY.

No fixture is evidence of real future S&P500 prices or a working crisis forecast.
"""
from __future__ import annotations

import calendar
import copy
import datetime as dt
import json
import unittest

from scripts.aics_v55_forward_prospective_conductor import SELECTED, REQUIRED_FEATURES
from scripts.aics_v56_prospective_feedback_learner import (
    INPUT, _learn, month_after, evaluate, MIN_MATURED_LABELS,
    SCHEMA, INITIAL_WEIGHTS
)

UTC=dt.timezone.utc
FAKE_NOW=dt.datetime(2028,1,10,12,0,tzinfo=UTC)


def _receipt_time(month):
    y,m=map(int,month.split("-"))
    last=dt.date(y,m,calendar.monthrange(y,m)[1])
    retrieved=dt.datetime.combine(last+dt.timedelta(days=1),dt.time(1),tzinfo=UTC)
    forecast=retrieved+dt.timedelta(hours=10)
    return last,retrieved,forecast


def synthetic_ledger(n_snapshots=13):
    """Create artificial simulation only for policy behavior; NEVER archive as market."""
    ledger={
        "schema":SCHEMA,
        "frozen_registry_date":"2026-11-22",
        "frozen_five_specialists":list(SELECTED),
        "original_11node_weight_total_unchanged":1050,
        "original_11node_AICS":None,
        "no_trades":True,
        "original_v55_forecast_snapshots":[],
        "observed_sp500_month_closes":[],
    }
    first="2026-11"
    for i in range(n_snapshots+1):
        month=month_after(first,i)
        last,retrieved,asof=_receipt_time(month)
        # Three separate artificial 5% shocks with intervening recoveries.
        close=88.0 if month=="2027-02" else 90.0 if month=="2027-07" else (
              89.0 if month=="2027-12" else 100.0)
        receipt={
            "month":month,"market_close_date":last.isoformat(),
            "retrieved_at_utc":retrieved.isoformat(),
            "source_uri":"https://example.invalid/SYNTHETIC-TEST-ONLY",
            "source_sha256":"a"*64,
            "sp500_close":close,
            "independently_verified_first_publication_PIT":False,
        }
        ledger["observed_sp500_month_closes"].append(receipt)
        if i>=n_snapshots:
            continue
        b=40+(i%5)*8
        s=22+(i%4)*12
        vals={
            "B":b,"S":s,"BM2":max(0,b-4),"SM3":max(0,s-4),
            "BM3":max(0,b-6),"SM2":max(0,s-2),
            "loss3":15+(i%3)*10,"loss1":8+(i%4)*10,
            "vol":15+(i%5)*5,"accelB":5+(i%3)*12,"accelS":4+(i%4)*15,
        }
        features={name:{
            "value":float(vals[name]),
            "source_first_seen_at_utc":retrieved.isoformat(),
            "source_uri":"https://example.invalid/ARTIFICIAL-EXPERT-FEATURE",
            "source_sha256":"b"*64,
            "independently_attested_publication_PIT":False
        } for name in REQUIRED_FEATURES}
        ledger["original_v55_forecast_snapshots"].append({
            "schema":"aics-v55-prospective-research-snapshot-v1",
            "signal_month":month,
            "market_close_date":last.isoformat(),
            "market_close_retrieved_at_utc":retrieved.isoformat(),
            "market_close_source_uri":receipt["source_uri"],
            "market_close_source_sha256":receipt["source_sha256"],
            "forecast_created_at_utc":asof.isoformat(),
            "features":features,
            "certified_11node_AICS":None,
            "independent_source_delivery_pit_certified":False,
            "trading_permission":False,
        })
    return ledger


class V56ProspectiveLearningTests(unittest.TestCase):

    def test_real_prospective_ledger_starts_without_market_fabrication(self):
        x=json.loads(INPUT.read_text(encoding="utf-8"))
        self.assertEqual(x["original_v55_forecast_snapshots"],[])
        self.assertEqual(x["observed_sp500_month_closes"],[])
        r=evaluate(x,now=dt.datetime(2026,11,22,13,0,tzinfo=UTC))
        self.assertEqual(r["original_prospective_snapshot_count"],0)
        self.assertEqual(r["matured_individual_1month_5pct_labels"],0)
        self.assertFalse(r["adaptive_weights_currently_activated"])
        self.assertEqual(r["latest_shadow_weight_state"]["prospective_five_expert_weights"],
                         INITIAL_WEIGHTS)
        self.assertEqual(r["forward_score_series"],[])
        self.assertFalse(r["trades_created"])
        self.assertIsNone(r["official_AICS_index"])

    def test_hypothetical_13_forward_snapshots_can_eventually_update_weights(self):
        report=evaluate(synthetic_ledger(),now=FAKE_NOW)
        self.assertEqual(report["original_prospective_snapshot_count"],13)
        self.assertEqual(report["original_forward_SP500_monthly_closes_count"],14)
        self.assertEqual(report["matured_individual_1month_5pct_labels"],13)
        s=report["latest_shadow_weight_state"]
        self.assertTrue(s["trained_using_matured_labels"])
        self.assertEqual(s["observed_positive_label_months"],3)
        self.assertEqual(s["distinct_observed_positive_episodes"],3)
        weights=s["prospective_five_expert_weights"]
        self.assertAlmostEqual(sum(weights.values()),1,places=7)
        self.assertTrue(all(0.15<=v<=0.4 for v in weights.values()))
        self.assertTrue(any(abs(v-0.2)>0.00001 for v in weights.values()))
        self.assertEqual(len(report["forward_score_series"]),13)
        self.assertIsNone(report["new_untouched_out_of_sample_forecast_accuracy_proven"])
        self.assertFalse(report["trades_created"])

    def test_predictions_are_from_only_previously_matured_labels(self):
        report=evaluate(synthetic_ledger(),now=FAKE_NOW)
        early=report["forward_score_series"][:11]
        self.assertTrue(all(not r["only_previous_matured_label_weights"][
                            "trained_using_matured_labels"] for r in early))
        self.assertTrue(all(r["prequential_bounded_adaptive_shadow_score_not_AICS"]==
                            r["fixed_equal_mean_shadow_not_AICS"]
                            for r in early))
        last=report["forward_score_series"][-1]
        self.assertTrue(last["only_previous_matured_label_weights"]["trained_using_matured_labels"])
        self.assertEqual(last["month"],"2027-11")
        self.assertFalse(last["next_month_outcome_used_to_make_this_forecast"])
        self.assertIsNone(last["full_AICS"])

    def test_no_weight_update_before_minimum_completed_real_labels(self):
        x=synthetic_ledger(n_snapshots=11)
        r=evaluate(x,now=FAKE_NOW)
        self.assertEqual(r["matured_individual_1month_5pct_labels"],11)
        self.assertFalse(r["adaptive_weights_currently_activated"])
        self.assertEqual(r["latest_shadow_weight_state"]["prospective_five_expert_weights"],
                         INITIAL_WEIGHTS)
        self.assertEqual(MIN_MATURED_LABELS,12)

    def test_no_training_on_future_prices_falsely_dated_in_past(self):
        x=synthetic_ledger()
        old=evaluate(x,now=FAKE_NOW)
        next_price=x["observed_sp500_month_closes"][-1]
        next_price["sp500_close"]=41.0
        modified=evaluate(x,now=FAKE_NOW)
        self.assertEqual(
            [r["only_previous_matured_label_weights"] for r in old["forward_score_series"]],
            [r["only_previous_matured_label_weights"] for r in modified["forward_score_series"]],
        )
        self.assertNotEqual(old["latest_shadow_weight_state"],
                            modified["latest_shadow_weight_state"])

    def test_future_publication_price_not_available_must_abort(self):
        x=synthetic_ledger()
        x["observed_sp500_month_closes"][-1]["retrieved_at_utc"]="2030-01-01T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"not actually available"):
            evaluate(x,now=FAKE_NOW)

    def test_duplicate_reordered_or_changed_market_origin_fail_closed(self):
        x=synthetic_ledger()
        x["original_v55_forecast_snapshots"].append(copy.deepcopy(
            x["original_v55_forecast_snapshots"][-1]))
        with self.assertRaisesRegex(ValueError,"chronologically"):
            evaluate(x,now=FAKE_NOW)
        x=synthetic_ledger()
        x["original_v55_forecast_snapshots"][1]["market_close_source_sha256"]="c"*64
        with self.assertRaisesRegex(ValueError,"exact received"):
            evaluate(x,now=FAKE_NOW)
        x=synthetic_ledger()
        x["observed_sp500_month_closes"][2]["month"]=x["observed_sp500_month_closes"][1]["month"]
        with self.assertRaises(ValueError):
            evaluate(x,now=FAKE_NOW)

    def test_missing_immutable_source_or_unverified_pit_assertion_fail(self):
        x=synthetic_ledger()
        x["original_v55_forecast_snapshots"][0]["features"]["B"]["source_sha256"]="bad"
        with self.assertRaises(ValueError):
            evaluate(x,now=FAKE_NOW)
        x=synthetic_ledger()
        x["observed_sp500_month_closes"][3]["independently_verified_first_publication_PIT"]=True
        with self.assertRaisesRegex(ValueError,"forge"):
            evaluate(x,now=FAKE_NOW)
        x=synthetic_ledger()
        x["original_11node_AICS"]=500
        with self.assertRaisesRegex(ValueError,"Unsupported"):
            evaluate(x,now=FAKE_NOW)

    def test_no_2024_to_2026_pre_freeze_training_backfill(self):
        x=synthetic_ledger()
        x["observed_sp500_month_closes"][0]["month"]="2025-01"
        with self.assertRaisesRegex(ValueError,"retrospective"):
            evaluate(x,now=FAKE_NOW)
        x=synthetic_ledger()
        x["original_v55_forecast_snapshots"][0]["signal_month"]="2024-11"
        with self.assertRaises(ValueError):
            evaluate(x,now=FAKE_NOW)


if __name__=="__main__":
    unittest.main()
