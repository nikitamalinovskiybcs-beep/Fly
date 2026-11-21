"""Negative gates for AICS thirty-role evidence-to-improvement loop.

Fixtures simulate unavailable publishers; they are never promoted to live
receipts, predictor training, production decisions, or trading outputs.
"""
from __future__ import annotations

import copy
import unittest

from scripts.aics_ten_node_agents import NODE_TASKS
from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_ten_analysis_agents import V17, V18, SPX, read
from scripts.aics_ten_model_improvement_agents import AI_SHADOW
from scripts.aics_sec_quarter_cashflow_gate import audit
from scripts.aics_thirty_agent_cycle import build


def wave_fixture():
    rows = []
    for number, node in enumerate(NODE_TASKS, 1):
        ops = ([{"source_id": "EIA_RTO_DEMAND",
                 "status": "blocked_eia_key_missing",
                 "node_score_eligible": False}]
               if node == "Power/Data Centers" else [])
        rows.append({
            "round": number, "agent": node,
            "weight_unchanged": WEIGHTS[node],
            "research_usable_scored_node": False,
            "operations": ops,
        })
    return {
        "schema": "aics-ten-real-source-acquisition-waves-with-companyfacts-v1",
        "captured_at_utc": "2026-11-21T22:10:00+00:00",
        "rounds": 10, "source_agents": 10, "rounds_report": rows,
        "total_http_attempts": 1, "successful_http_archives": 0,
        "unique_original_source_ids_archived": 0,
        "unavailable_source_keys": ["EIA_RTO_DEMAND"],
        "actual_numeric_facts_extracted_current_sec_snapshots": 0,
        "fixed_weights_total": 1050, "production_weights_changed": False,
        "trades_created": False, "complete_index": None,
        "independent_sp500_skill": None,
        "independently_pit_verified_node_count": 0,
    }


class ThirtyAgentCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v17, cls.v18, cls.spx, cls.shadow = (
            read(V17), read(V18), read(SPX), read(AI_SHADOW))
        cls.waves = wave_fixture()
        cls.finance = audit([], as_of="2026-11-21")

    def execute(self, waves=None, finance=None):
        return build(
            waves=self.waves if waves is None else waves,
            finance=self.finance if finance is None else finance,
            v17=self.v17, v18=self.v18, spx=self.spx,
            shadow=self.shadow,
        )

    def test_thirty_roles_and_real_gaps_without_prediction_claim(self):
        report = self.execute()
        self.assertEqual(report["agent_groups"]["total_distinct_roles_executed"],30)
        self.assertEqual(report["weights_total_unchanged"],1050)
        self.assertEqual(report["analysis"]["market_proxy_months"],24)
        self.assertEqual(report["analysis"]["historical_full_aics_months"],0)
        self.assertTrue(report["analysis"]["analysis_is_previous_V17_V18_not_new_sec_score_ingestion"])
        self.assertIsNone(report["complete_11_node_aics"])
        self.assertIsNone(report["crisis_probability"])
        self.assertIsNone(report["model_improvement"]["new_predictive_skill"])
        self.assertFalse(report["eligible_for_production_promotion"])
        self.assertFalse(report["trades_created"])
        self.assertFalse(report["weights_changed"])
        self.assertEqual(report["cycle_decision"],
                         "RESEARCH_ONLY_NOT_AUTONOMOUS_PRODUCTION")
        tasks={x["experiment"] for x in report["next_experiments"]}
        self.assertIn("2026_Q1_4_ISSUER_CASHFLOW_GAP",tasks)
        self.assertIn("ORIGINAL_SEC_NUMERIC_SOURCE_TO_NODE",tasks)
        self.assertIn("AI_EQUITIES_HISTORICAL_CONSTITUENTS",tasks)
        self.assertIn("SPV_CREDIT_RECOURSE_NETWORK",tasks)
        self.assertIn("FROZEN_FORMULA_WALK_FORWARD",tasks)
        self.assertIn("RETRY_MISSING_PRIMARY_SOURCES",tasks)
        self.assertEqual(
            [x["priority"] for x in report["next_experiments"]],
            list(range(1,len(report["next_experiments"])+1)))

    def test_inconsistent_sec_numeric_snapshot_count_fails_closed(self):
        bad=copy.deepcopy(self.waves)
        bad["actual_numeric_facts_extracted_current_sec_snapshots"]=22
        with self.assertRaises(ValueError):
            self.execute(waves=bad)

    def test_claimed_pit_or_model_promotion_fails_closed(self):
        for change in (
            {"complete_index": 669.09},
            {"production_weights_changed": True},
            {"independently_pit_verified_node_count": 11},
            {"fixed_weights_total": 1100},
            {"total_http_attempts": 0},
        ):
            bad=copy.deepcopy(self.waves)
            bad.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.execute(waves=bad)
        bad=copy.deepcopy(self.finance)
        bad["node_scores_promoted"]=1
        with self.assertRaises(ValueError):
            self.execute(finance=bad)

    def test_unverified_pair_or_future_receipt_rejected(self):
        bad=copy.deepcopy(self.waves)
        bad["rounds_report"][0]["operations"].append(
            {"source_id":"SEC_fake","node_score_eligible":True})
        with self.assertRaises(ValueError):
            self.execute(waves=bad)
        bad=copy.deepcopy(self.finance)
        bad["as_of"]="2026-11-22"
        with self.assertRaises(ValueError):
            self.execute(finance=bad)

    def test_missing_or_reordered_roles_rejected(self):
        bad=copy.deepcopy(self.waves)
        bad["rounds_report"][0]["agent"]="SPV"
        with self.assertRaises(ValueError):
            self.execute(waves=bad)
        bad=copy.deepcopy(self.waves)
        bad["rounds_report"][0]["weight_unchanged"]=999
        with self.assertRaises(ValueError):
            self.execute(waves=bad)


if __name__ == "__main__":
    unittest.main()
