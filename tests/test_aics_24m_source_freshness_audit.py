"""Real dated AICS source freshness is not score completeness or historical PIT."""
import copy
import json
import unittest
from scripts.aics_24m_source_freshness_audit import SOURCE, OUTPUT, audit


class AICS24mSourceFreshnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger=json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_real_24_month_receipt_replays_and_weights_reconcile(self):
        report=audit(self.ledger)
        self.assertEqual(report,json.loads(OUTPUT.read_text(encoding="utf-8")))
        self.assertEqual(report["total_fresh_weight_months"],3375)
        self.assertEqual(report["total_carried_weight_months"],3950)
        self.assertEqual(report["total_missing_weight_months"],17875)
        self.assertEqual(3375+3950+17875,24*1050)
        self.assertEqual(report["fresh_month_weight_avg_pct"],"13.39")
        self.assertEqual(report["carried_month_weight_avg_pct"],"15.67")
        self.assertEqual(report["missing_month_weight_avg_pct"],"70.93")
        self.assertEqual(report["months_with_over90_day_old_eligible_source"],1)
        self.assertEqual(report["over90_weight_months"],100)

    def test_october_source_recency_and_never_full_pit(self):
        report=audit(self.ledger)
        oct=report["last_month"]
        self.assertEqual(oct["fresh_source_weight"],325)
        self.assertEqual(oct["carried_source_weight"],625)
        self.assertEqual(oct["missing_node_weight"],100)
        self.assertEqual(oct["fresh_pct_of_full_1050_not_pit"],"30.95")
        self.assertEqual(oct["carried_pct_of_full_1050_not_pit"],"59.52")
        self.assertEqual(oct["missing_pct_of_full_1050"],"9.52")
        self.assertEqual(oct["fresh_source_nodes"],["Power/Data Centers","Repo","Semiconductors Supply","UST 30Y"])
        self.assertEqual(oct["missing_nodes"],["AI Equities"])
        self.assertEqual(report["full_historical_aics_months"],0)
        self.assertEqual(report["full_aics_sp500_spread_months"],0)
        self.assertFalse(report["historically_attested_pit"])
        self.assertTrue(all(r["full_historical_aics"] is None and
                            r["historical_aics_sp500_spread"] is None
                            for r in report["rows"]))

    def test_reject_future_source_carried_flag_or_forged_pit(self):
        bad=copy.deepcopy(self.ledger)
        bad["monthly"][0]["latest_eligible_research_scores"]["Insurers"]["source_available_at"]="2026-11-21"
        with self.assertRaisesRegex(ValueError,"Undated"):
            audit(bad)
        bad=copy.deepcopy(self.ledger)
        bad["monthly"][-1]["latest_eligible_research_scores"]["Hyperscalers"]["carried_from_prior_month"]=False
        with self.assertRaisesRegex(ValueError,"stale-flag"):
            audit(bad)
        bad=copy.deepcopy(self.ledger)
        bad["score_source_events"][0]["independently_attested_historical_pit"]=True
        with self.assertRaisesRegex(ValueError,"certified"):
            audit(bad)

    def test_reject_fake_pit_index(self):
        bad=copy.deepcopy(self.ledger)
        bad["monthly"][0]["full_11_node_aics_no_multiplier"]="39.68"
        with self.assertRaisesRegex(ValueError,"promotion"):
            audit(bad)


if __name__=="__main__":
    unittest.main()
