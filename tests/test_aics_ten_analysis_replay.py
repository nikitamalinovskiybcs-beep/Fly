"""Fixed-input AICS 10x10 analyst cycle reproducibility safeguards."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_ten_analysis_replay import (
    FIXED_CYCLES, V17, V18, SPX, replay
)


class TenReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = replay(as_of=dt.date(2026,11,22), manifest=None)

    def test_ten_full_runs_and_all_ten_agents_each(self):
        d=self.report
        self.assertEqual(d["cycles"],10)
        self.assertEqual(d["analysis_agents_per_cycle"],10)
        self.assertEqual(d["agent_executions"],100)
        self.assertEqual([x["cycle"] for x in d["cycles_detail"]], list(range(1,11)))
        self.assertTrue(all(x["analysis_agents_passed"]==10 for x in d["cycles_detail"]))
        self.assertTrue(d["all_results_bitwise_deterministic"])
        self.assertEqual(len({x["result_sha256"] for x in d["cycles_detail"]}),1)

    def test_market_and_research_metrics_stable_and_not_certified(self):
        d=self.report
        self.assertTrue(all(x["calendar_research_source_coverage_pct"]=="50.89"
                            for x in d["cycles_detail"]))
        self.assertTrue(all(x["market_weekday_research_source_coverage_pct"]=="50.00"
                            for x in d["cycles_detail"]))
        self.assertTrue(all(x["anomaly_research_attention_flags"]==0
                            for x in d["cycles_detail"]))
        self.assertEqual(d["source_collector_cycles_performed_here"],0)
        self.assertEqual(d["new_ml_training_samples_from_replay"],0)
        self.assertEqual(d["source_evidence_new_observations_from_replay"],0)
        self.assertEqual(d["independent_out_of_sample_backtests_created"],0)
        self.assertIsNone(d["aics_complete_index"])
        self.assertIsNone(d["aics_sp500_spread"])
        self.assertFalse(d["trading_orders_created"])
        self.assertFalse(d["production_weights_modified"])

    def test_src_bytes_before_after_identical(self):
        for source in (V17,V18,SPX):
            expected=self.report["source_input_sha256"][str(source)]
            self.assertEqual(expected, hashlib.sha256(Path(source).read_bytes()).hexdigest())
        self.assertFalse(self.report["source_manifest_available"])

    def test_wrong_number_of_cycles_fail_closed(self):
        for cycles in (0,1,9,11):
            with self.assertRaises(ValueError):
                replay(cycles=cycles, manifest=None)

    def test_tampered_original_rejected_in_temporary_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"original.json"
            data=json.loads(Path(V18).read_text())
            data["monthly_calendar_end_research"][-1]["node_scores"][
                "Hyperscalers"]["research_eligible_date"]="2026-12-01"
            p.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                replay(v18=p, manifest=None, as_of=dt.date(2026,11,22))


if __name__ == "__main__":
    unittest.main()
