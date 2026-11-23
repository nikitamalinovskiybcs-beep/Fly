"""Offline fixture-only tests (artificial test payloads are NOT market evidence)."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_ten_node_agents import (
    NODE_TASKS, SEC_CIK, collect, sources, validate_original
)
from scripts.aics_source_anomaly_ml import (
    MIN_TRAINING, observed_events, online_learn, read, V17, V18
)

NOW = dt.datetime(2026, 11, 22, 12, tzinfo=dt.timezone.utc)


def fake_primary(url, user_agent):
    if "/submissions/CIK" in url:
        cik = url.split("CIK")[-1].split(".json")[0]
        return json.dumps({
            "cik": int(cik),
            "filings": {"recent": {"form": ["10-Q"], "filingDate": ["2026-11-20"],
                                   "accessionNumber": ["0000123456-26-000001"]}},
        }).encode()
    if "stlouisfed.org" in url:
        return json.dumps({"observations": [{
            "date": "2026-11-20", "realtime_start": "2026-11-22",
            "realtime_end": "9999-12-31", "value": "3.0"}]}).encode()
    if "markets.newyorkfed.org" in url:
        return json.dumps({"refRates": [{
            "effectiveDate": "2026-11-20", "type": "SOFR", "percentRate": 3.8,
            "volumeInBillions": 2400.0}]}).encode()
    if "api.eia.gov" in url:
        return json.dumps({"response":{"data":[{
            "period":"2026-11-20T10","respondent":"CISO","type":"D","value":"20250"
        }]}}).encode()
    if "federalreserve.gov" in url:
        return b"<!doctype html><html><body>Fixture, not real market data</body></html>"
    raise AssertionError("Unknown source endpoint")


class AicsTenNodeCollectorTest(unittest.TestCase):
    def test_all_ten_node_rosters_and_shared_sources(self):
        self.assertEqual(len(NODE_TASKS), 10)
        self.assertEqual(len(SEC_CIK), 15)
        spec = sources(NOW, fred_api_key="PRIVATE_TEST_KEY", eia_api_key="PRIVATE_TEST_EIA_KEY")
        self.assertEqual(len(spec), 20)
        self.assertEqual(set(spec), {s for v in NODE_TASKS.values() for s in v})
        self.assertEqual(NODE_TASKS["Neoclouds"], NODE_TASKS["SPV"])

    def test_offline_never_calls_any_network(self):
        def fail(*args):
            raise AssertionError("An offline collection touched network")
        with tempfile.TemporaryDirectory() as tmp:
            x = collect(out=Path(tmp), now=NOW, live=False, transport=fail)
            self.assertEqual(x["agent_count"], 10)
            self.assertEqual(x["original_sources_archived"], 0)
            self.assertEqual(x["unique_publisher_sources"], 20)
            self.assertEqual(x["deduplicated_source_calls"], 2)
            self.assertTrue(all(a["stress_score"] is None for a in x["agents"]))
            self.assertIsNone(x["index_aics"])
            self.assertFalse(x["trades_created"])

    def test_mocked_live_captures_each_original_once_and_hashes(self):
        calls = []
        def transport(url, ua):
            calls.append(url)
            return fake_primary(url, ua)
        with tempfile.TemporaryDirectory() as tmp:
            x = collect(out=Path(tmp), now=NOW, live=True, transport=transport,
                        contact="AICS Research research-team@institution.org",
                        fred_api_key="PRIVATE_TEST_KEY",
                        eia_api_key="PRIVATE_TEST_EIA_KEY")
            self.assertEqual(len(calls), 20)
            self.assertEqual(len(set(calls)), 20)
            self.assertEqual(x["original_sources_archived"], 20)
            self.assertTrue(all(a["status"] == "captured_current_unverified"
                                for a in x["agents"]))
            self.assertTrue(all(s["status"] == "archived_current_original_not_pit"
                                for s in x["sources"]))
            self.assertTrue(all(s["historical_provider_pit_attested"] is False
                                and s["score_eligible"] is False for s in x["sources"]))
            self.assertEqual(x["independently_verified_node_scores"], 0)
            self.assertIsNone(x["model_predictive_accuracy"])
            self.assertIsNone(x["index_aics"])
            self.assertFalse(x["production_weights_changed"])
            self.assertEqual(len(list((Path(tmp) / "raw").iterdir())), 20)
            manifest = json.loads((Path(tmp) / "manifest.json").read_text())
            self.assertEqual(manifest["agent_count"], 10)
            self.assertNotIn("PRIVATE_TEST_KEY", (Path(tmp) / "manifest.json").read_text())
            self.assertNotIn("PRIVATE_TEST_EIA_KEY", (Path(tmp) / "manifest.json").read_text())

    def test_sec_real_world_zero_padded_string_cik_is_same_identity(self):
        spec = sources(NOW, fred_api_key="x")["SEC_ARCC"]
        original = {
            "cik": "0001287750",
            "filings": {"recent": {
                "form": ["10-Q"], "filingDate": ["2026-11-20"],
                "accessionNumber": ["0001287750-26-000001"]
            }},
        }
        parsed = validate_original(spec, json.dumps(original).encode(), at=NOW)
        self.assertEqual(parsed["reported_recent_filing_rows"], 1)
        original["cik"] = "0001287751"
        with self.assertRaises(ValueError):
            validate_original(spec, json.dumps(original).encode(), at=NOW)

    def test_missing_credentials_block_sec_and_fred_without_silent_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            x = collect(out=Path(tmp), now=NOW, live=True, transport=fake_primary,
                        contact="", fred_api_key="")
            self.assertEqual(x["original_sources_archived"], 2)
            source = {item["source_id"]: item for item in x["sources"]}
            self.assertEqual(source["EIA_RTO_DEMAND"]["status"],
                             "blocked_eia_api_key_missing")
            self.assertTrue(any(a["status"] == "blocked_or_offline" for a in x["agents"]))
            self.assertTrue(all(a["stress_score"] is None for a in x["agents"]))

    def test_eia_hourly_actual_demand_and_future_rejection(self):
        s = sources(NOW, fred_api_key="x", eia_api_key="z")
        self.assertIn("api_key=z", s["EIA_RTO_DEMAND"]["url"])
        real = fake_primary(s["EIA_RTO_DEMAND"]["url"], "ua")
        info = validate_original(s["EIA_RTO_DEMAND"], real, at=NOW)
        self.assertEqual(info["reported_rows"], 1)
        self.assertEqual(info["source_structure"],
                         "eia_930_hourly_demand_data_not_dc_specific")
        missing = b'{"response":{"id":"v2","routes":[]}}'
        with self.assertRaises(ValueError):
            validate_original(s["EIA_RTO_DEMAND"], missing, at=NOW)
        future = b'{"response":{"data":[{"period":"2026-11-23T10","respondent":"CISO","type":"D","value":"20300"}]}}'
        with self.assertRaises(ValueError):
            validate_original(s["EIA_RTO_DEMAND"], future, at=NOW)

    def test_original_validation_fails_closed(self):
        s = sources(NOW, fred_api_key="x")
        with self.assertRaises(ValueError):
            validate_original(s["SEC_ARCC"],
                              fake_primary(s["SEC_BXSL"]["url"], "ua"), at=NOW)
        future = b'{"refRates":[{"type":"SOFR","effectiveDate":"2026-11-23"}]}'
        with self.assertRaises(ValueError):
            validate_original(s["NYFED_SOFR"], future, at=NOW)


class OnlineAnomalyLearningTest(unittest.TestCase):
    def _fixture(self):
        # Unit-test fixtures only; no invented value enters any research ledger.
        values = [9, 10, 11, 10, 9, 11, 10, 12, 99]
        return [{"node":"Insurers",
                 "available":f"2026-01-{i:02d}",
                 "score":str(v), "source":f"fixture_{i}"}
                for i,v in enumerate(values,1)]

    def test_prequential_train_prior_only_and_alerts_are_not_trades(self):
        x = online_learn(self._fixture(), as_of=dt.date(2026,2,1))
        self.assertEqual(x["research_events_evaluated"], 9)
        self.assertEqual(x["events_with_trainable_history"], 1)
        p = x["sample_decisions"][-1]
        self.assertEqual(p["prior_observations"], MIN_TRAINING)
        self.assertEqual(p["training_max_date"], "2026-01-08")
        self.assertEqual(p["model_status"], "causal_research_assessed")
        self.assertEqual(p["model_alert"], "positive_stress_anomaly_research")
        self.assertTrue(p["anomaly_z"] > 3.5)
        self.assertIsNone(x["predictive_accuracy"])
        self.assertIsNone(x["complete_11_node_index"])
        self.assertFalse(x["aics_weights_changed"])
        self.assertFalse(x["trades_created"])

    def test_same_day_events_cannot_train_each_other(self):
        items=self._fixture()[:8] + [
            {"node":"Insurers","available":"2026-01-09",
             "score":"99","source":"another_original"},
            {"node":"Insurers","available":"2026-01-09",
             "score":"98","source":"additional_original"}]
        x = online_learn(items, as_of=dt.date(2026,2,1))
        self.assertEqual([r["prior_observations"] for r in x["sample_decisions"][-2:]],
                         [8,8])
        self.assertEqual(x["events_with_trainable_history"], 2)

    def test_future_and_broken_inputs_are_rejected(self):
        x = online_learn(self._fixture(), as_of=dt.date(2026,1,5))
        self.assertEqual(x["research_events_evaluated"], 5)
        with self.assertRaises(ValueError):
            online_learn(self._fixture()+[dict(self._fixture()[0])],
                         as_of=dt.date(2026,2,1))
        with self.assertRaises(ValueError):
            online_learn(self._fixture()[:1], min_training=2)
        invalid = self._fixture()[:1]
        invalid[0]["score"] = "NaN"
        with self.assertRaises(ValueError):
            online_learn(invalid)

    def test_actual_persisted_history_is_research_only(self):
        x = online_learn(observed_events(read(V17), read(V18)),
                         as_of=dt.date(2026,11,22))
        self.assertGreaterEqual(x["research_events_evaluated"], 50)
        self.assertGreaterEqual(x["events_with_trainable_history"], 1)
        self.assertTrue(all(r["training_max_date"] is None or
                            r["training_max_date"] < r["source_eligible_at"]
                            for r in x["sample_decisions"]))
        self.assertFalse(x["source_delivery_historically_pit_attested"])
        self.assertFalse(x["pre_registered_out_of_sample"])
        self.assertEqual(x["supervised_prediction_status"],
                         "BLOCKED_UNTIL_REALIZED_LABELS_AND_FROZEN_OOS")


if __name__ == "__main__":
    unittest.main()
