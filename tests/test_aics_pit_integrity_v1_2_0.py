"""AICS user-supplied CI v1.2.0 rules, safely adapted to canonical fail-closed API.

The submitted percentile method is NOT production scoring: twelve historical
values do not establish historical provider PIT, calibrated methodology, or
independent untouched 24-month OOS. Examples below are unit-test fixtures,
not recorded market data or synthetic backfill.
"""
import unittest

from scripts.aics_index import WEIGHTS, calculate, sec_available_at
from scripts.aics_pit_research_slice import PITRecordError, slice_research_records


class TestSuppliedV120PITIntegrity(unittest.TestCase):
    def test_alfred_vintage_isolation(self):
        template = {
            "source": "ALFRED", "node_id": "Semiconductors Supply",
            "metric_id": "g17", "entity": "IPG3344S",
            "observation_date": "2025-01-31",
        }
        records = [
            {**template, "realtime_start": "2025-02-05",
             "realtime_end": "2025-03-05", "value": 100.0},
            {**template, "realtime_start": "2025-03-06",
             "realtime_end": "9999-12-31", "value": 105.5},
        ]
        before = slice_research_records(records, "2025-02-15")
        after = slice_research_records(records, "2025-03-10")
        self.assertEqual([x["value"] for x in before], [100.0])
        self.assertEqual([x["value"] for x in after], [105.5])
        self.assertTrue(all(not x["independently_attested_pit"] for x in before + after))
        self.assertTrue(all(not x["model_eligible"] for x in before + after))

    def test_sec_exact_14_calendar_day_lag(self):
        self.assertEqual(sec_available_at("2025-11-01").isoformat(), "2025-11-15")
        record = {
            "source": "SEC", "node_id": "Hyperscalers", "metric_id": "capex_ocf",
            "entity": "MSFT", "observation_date": "2025-09-30",
            "filed_at": "2025-11-01", "available_at": "2025-11-15",
            "value": 0.42,
        }
        self.assertEqual(slice_research_records([record], "2025-11-14"), [])
        got = slice_research_records([record], "2025-11-15")
        self.assertEqual(len(got), 1)
        self.assertFalse(got[0]["model_eligible"])

    def test_sec_available_at_cannot_be_claimed_early(self):
        record = {
            "source": "SEC", "node_id": "Hyperscalers", "metric_id": "capex_ocf",
            "entity": "MSFT", "observation_date": "2025-09-30",
            "filed_at": "2025-11-01", "available_at": "2025-11-01", "value": 0.42,
        }
        with self.assertRaises(PITRecordError):
            slice_research_records([record], "2025-11-15")

    def test_missing_one_node_returns_null_not_fake_index(self):
        sample_scores = {node: 40 for node in list(WEIGHTS)[:-1]}
        result = calculate(sample_scores, verified_nodes=set(WEIGHTS))
        self.assertFalse(result["publishable"])
        self.assertIsNone(result["aics"])
        self.assertIn("ai_demand", result["missing_nodes"])

    def test_canonical_multiplier_h_equals_four(self):
        # Unit-test vector for arithmetic only; not 11 observed financial scores.
        sample_scores = {node: 0.0 for node in WEIGHTS}
        for node in list(WEIGHTS)[:4]:
            sample_scores[node] = 100.0
        result = calculate(sample_scores, verified_nodes=set(WEIGHTS))
        self.assertEqual(result["hot_nodes"], 4)
        self.assertAlmostEqual(result["multiplier"], 1.25)
        self.assertAlmostEqual(result["aics"], result["base"] * 1.25)

    def test_overlapping_alfred_vintages_must_not_choose_one(self):
        base = {
            "source": "ALFRED", "node_id": "Repo", "metric_id": "IORB",
            "entity": "NYFed", "observation_date": "2025-01-01", "value": 4.0,
            "realtime_start": "2025-01-03", "realtime_end": "2025-05-30",
        }
        other = {**base, "realtime_start": "2025-02-02", "value": 5.0}
        with self.assertRaises(PITRecordError):
            slice_research_records([base, other], "2025-02-15")

    def test_future_observation_not_admitted(self):
        record = {
            "source": "ALFRED", "node_id": "Repo", "metric_id": "IORB",
            "entity": "NYFed", "observation_date": "2026-11-20",
            "realtime_start": "2026-11-01", "realtime_end": "9999-12-31",
            "value": 3.92,
        }
        self.assertEqual(slice_research_records([record], "2026-11-18"), [])

    def test_self_certified_data_never_admitted(self):
        record = {
            "source": "SEC", "node_id": "SPV", "metric_id": "liability",
            "entity": "EXAMPLE", "observation_date": "2025-09-30",
            "filed_at": "2025-11-01", "available_at": "2025-11-15",
            "value": 1.0, "model_eligible": True,
        }
        with self.assertRaises(PITRecordError):
            slice_research_records([record], "2025-11-18")

    def test_filing_cannot_report_a_later_observed_period(self):
        record = {
            "source": "SEC", "node_id": "SPV", "metric_id": "liability",
            "entity": "EXAMPLE", "observation_date": "2025-11-03",
            "filed_at": "2025-11-01", "available_at": "2025-11-15",
            "value": 1.0,
        }
        with self.assertRaises(PITRecordError):
            slice_research_records([record], "2025-11-18")

    def test_unsupported_source_and_nan_fail_closed(self):
        record = {
            "source": "SEC", "node_id": "SPV", "metric_id": "liability",
            "entity": "EXAMPLE", "observation_date": "2025-09-30",
            "filed_at": "2025-11-01", "available_at": "2025-11-15",
            "value": 1.0,
        }
        with self.assertRaises(PITRecordError):
            slice_research_records([{**record, "source": "SOCIAL"}], "2025-11-18")
        with self.assertRaises(PITRecordError):
            slice_research_records([{**record, "value": float("nan")}], "2025-11-18")

    def test_unverified_sources_not_promoted_to_index(self):
        self.assertEqual(len(WEIGHTS), 11)
        self.assertEqual(sum(WEIGHTS.values()), 1050)
        report = calculate({}, verified_nodes=())
        self.assertFalse(report["publishable"])
        self.assertIsNone(report["aics"])
        self.assertEqual(len(report["unverified_nodes"]), 11)


if __name__ == "__main__":
    unittest.main()
