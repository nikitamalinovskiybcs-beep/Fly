"""Source-ledger tests for ten AICS model improvement roles; no synthetic claims."""
import copy
import datetime as dt
import unittest

from scripts.aics_ten_model_improvement_agents import (
    AI_SHADOW, NAMES, SPX, V17, V18, read, run
)
from scripts.aics_sec_quarter_cashflow_gate import audit, OCF, CAPEX

ASOF=dt.date(2026,11,21)

def fixture_row(tag,value):
    return {
        "source_id":"XBRL_MSFT","cik":"789019","tag":tag,"unit":"USD",
        "value":value,"period_start":"2026-07-01","period_end":"2026-09-30",
        "filed_at":"2026-10-27","research_eligible_date_only_proxy":"2026-10-28",
        "original_sec_accession":"0001234567-26-000001",
        "original_companyfacts_snapshot_sha256":"a"*64,
        "original_first_document_bytes_verified":False,
        "retrospective_provider_pit_certified":False,"form":"10-Q",
    }

class ImprovementAgentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs=dict(v17=read(V17),v18=read(V18),spx=read(SPX),
                        shadow=read(AI_SHADOW),as_of=ASOF)
        cls.report=run(**cls.inputs)

    def test_ten_distinct_roles_complete_and_no_false_training(self):
        r=self.report
        self.assertEqual(r["actual_model_improvement_agents_executed"],10)
        self.assertEqual([x["name"] for x in r["agents"]],list(NAMES))
        self.assertEqual(r["total_distinct_workflow_agent_roles"],30)
        self.assertTrue(all(x["execution"]=="completed"
                            and not x["new_aics_score_approved"]
                            and not x["trades_created"]
                            for x in r["agents"]))
        self.assertIsNone(r["full_aics"])
        self.assertIsNone(r["aics_sp500_spread"])
        self.assertIsNone(r["untouched_oos_forecast_accuracy"])
        self.assertFalse(r["trained_supervised_forecast"])
        self.assertFalse(r["aics_node_weights_modified"])

    def test_financial_agent_respects_actual_period_pair_and_no_score(self):
        r=self.report["agents"][0]["research_result"]
        self.assertEqual(r["evidence_status"],"BLOCKED_NO_CURRENT_SEC_NUMERIC_RECEIPTS")
        self.assertEqual(r["node_scores_added"],0)
        sample=audit([fixture_row(OCF,120_000_000),fixture_row(CAPEX,70_000_000)],
                     as_of="2026-11-21")
        d=run(**self.inputs,finance=sample)
        x=d["agents"][0]["research_result"]
        self.assertEqual(x["direct_quarter_pairs"],1)
        self.assertEqual(x["unique_issuers_with_direct_pairs"],1)
        self.assertEqual(x["node_scores_added"],0)
        gpu=d["agents"][3]["research_result"]
        self.assertEqual(gpu["actual_hyperscaler_direct_cashflow_pairs"],1)
        self.assertIsNone(gpu["payback_months"])
        self.assertFalse(gpu["ready_for_gpu_economics_score"])

    def test_reject_false_pit_or_approved_cashflow(self):
        sample=audit([fixture_row(OCF,120),fixture_row(CAPEX,70)],
                     as_of="2026-11-21")
        for modification in ("independently_pit_attested","source_bytes_historical_first_filing_verified"):
            bad=copy.deepcopy(sample)
            bad[modification]=True
            with self.subTest(modification=modification), self.assertRaises(ValueError):
                run(**self.inputs,finance=bad)
        bad=copy.deepcopy(sample)
        bad["candidate_quarter_pairs"][0]["aics_node_score"]=80
        with self.assertRaises(ValueError):
            run(**self.inputs,finance=bad)

    def test_historical_ai_equities_never_backfilled(self):
        x=self.report["agents"][1]["research_result"]
        self.assertEqual(len(x["research_candidate_roster"]),7)
        self.assertEqual(x["approved_historical_2024_2026_points"],0)
        self.assertEqual(x["observations_retrospective_whatif"],3)
        self.assertFalse(x["historically_fixed_basket_proven"])
        shadow=copy.deepcopy(self.inputs["shadow"])
        shadow["approved_historical_constituency"]=True
        with self.assertRaises(ValueError):
            run(**{**self.inputs,"shadow":shadow})
        with self.assertRaises(ValueError):
            run(**{**self.inputs,"as_of":dt.date(2026,11,20)})

    def test_credit_and_power_require_original_dollar_exposures(self):
        credit=self.report["agents"][2]["research_result"]
        power=self.report["agents"][4]["research_result"]
        self.assertEqual(credit["source_level_credit_exposure_edges_verified"],0)
        self.assertIsNone(credit["transmission_simulation"])
        self.assertFalse(credit["ready_for_network_propagation"])
        self.assertFalse(power["site_level_data_center_meter_data_verified"])
        self.assertIsNone(power["bottleneck_forecast"])

    def test_lead_lag_counts_actual_asof_features_only(self):
        a=self.report["agents"][5]["research_result"]
        self.assertEqual(a["retrospective_1month_sp500_outcomes"],23)
        self.assertEqual(a["feature_outcome_pairs_by_node"]["AI Equities"],0)
        self.assertGreater(a["feature_outcome_pairs_by_node"]["Private Credit"],0)
        self.assertFalse(a["causal_influence_established"])
        self.assertFalse(a["forecasting_weights_updated"])

    def test_real_sp500_drawdown_label_samples_not_predictions(self):
        a=self.report["agents"][6]["research_result"]
        for horizon, expected in (("1",23),("3",21),("6",18)):
            self.assertEqual(a["drawdown_label_horizons"][horizon][
                "retrospective_observed_outcome_labels"],expected)
            self.assertIsNone(a["drawdown_label_horizons"][horizon]["forecast_probability"])
        self.assertTrue(a["label_is_future_result_not_feature"])
        self.assertFalse(a["supervised_training_executed"])

    def test_walkforward_and_challenger_dont_promote_predictor(self):
        walk=self.report["agents"][7]["research_result"]
        challenger=self.report["agents"][8]["research_result"]
        self.assertFalse(walk["forecast_skill_reportable"])
        self.assertEqual(walk["independent_out_of_sample_months"],0)
        self.assertEqual(challenger["observed_next_month_pairs"],23)
        self.assertGreater(float(challenger["retrospective_monthly_baseline_absolute_error_pct"]),0)
        self.assertIsNone(challenger["aics_excess_predictive_skill_vs_baseline"])

    def test_calibration_requires_strict_actual_oos(self):
        cal=self.report["agents"][9]["research_result"]
        self.assertEqual(cal["minimum_calibration_training_observations"],36)
        self.assertEqual(cal["minimum_untouched_oos_labels"],12)
        self.assertEqual(cal["independent_oos_labels_confirmed"],0)
        self.assertFalse(cal["ready_to_train_supervised_model"])
        self.assertIsNone(cal["cross_validated_prediction_quality"])
        self.assertEqual(cal["production_weight_total_unchanged"],1050)

    def test_sp500_month_alignment_and_future_score_failure(self):
        spx=copy.deepcopy(self.inputs["spx"])
        spx["points"][0]["month"]="2026-10"
        with self.assertRaises(ValueError):
            run(**{**self.inputs,"spx":spx})
        data=copy.deepcopy(self.inputs["v18"])
        data["monthly_last_weekday_market_proxy"][-1]["node_scores"][
            "Hyperscalers"]["research_eligible_date"]="2026-11-05"
        with self.assertRaises(ValueError):
            run(**{**self.inputs,"v18":data})

if __name__=="__main__":
    unittest.main()
