"""Policy tests only: artificial unit-test fixtures, NOT market observations."""
import hashlib
import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/"scripts"/"aics_score_reproducibility_gate.py"
spec=importlib.util.spec_from_file_location("score_gate",path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def fixture():
    return {"as_of":"2026-11-18","nodes":{
        name:{"score":50,"evidence":{
            "source_uri":"https://example.invalid/test-fixture",
            "source_sha256":hashlib.sha256(b"unit-test-only").hexdigest(),
            "available_at":"2026-11-01",
            "independently_verified_pit":True,
            "score_method_version":"test-only",
            "training_cutoff":"2026-10-31"}}
        for name in module.WEIGHTS}}

class GateTests(unittest.TestCase):
    def test_empty_fails_closed(self):
        r=module.evaluate({"as_of":"2026-11-18"})
        self.assertIsNone(r["index_aics"])
        self.assertEqual(r["promotion"],"BLOCKED")
    def test_fixed_weight_invariant(self):
        self.assertEqual(sum(module.WEIGHTS.values()),1050)
        self.assertEqual(len(module.WEIGHTS),11)
    def test_arithmetic_fixture_not_market_score(self):
        r=module.evaluate(fixture())
        self.assertEqual(r["index_aics"],525.0)
        self.assertEqual(r["hot_nodes"],0)
        self.assertEqual(r["multiplier"],1)
        self.assertEqual(r["promotion"],"BLOCKED")
        self.assertTrue(r["index_aics_is_ARITHMETIC_CANDIDATE_NOT_OFFICIAL"])
        self.assertTrue(r["node_coverage_is_SELF_ASSERTED_not_independent_PIT"])
        self.assertFalse(r["independent_method_registry_approval_verified"])
        self.assertIsNone(r["official_AICS"])
        self.assertIsNone(r["strict_trade_action"])
    def test_missing_node_fails(self):
        x=fixture()
        x["nodes"].pop("Repo")
        self.assertIsNone(module.evaluate(x)["index_aics"])
    def test_future_data_fails(self):
        x=fixture()
        x["nodes"]["Repo"]["evidence"]["available_at"]="2026-11-19"
        self.assertIsNone(module.evaluate(x)["index_aics"])
    def test_sec_fourteen_day_embargo(self):
        x=fixture()
        ev=x["nodes"]["Insurers"]["evidence"]
        ev.update(source_type="SEC", filed_at="2026-10-30")
        for available_at, valid in (("2026-11-12", False), ("2026-11-13", True),
                                    ("2026-11-14", False)):
            with self.subTest(available_at=available_at):
                ev["available_at"] = available_at
                result = module.evaluate(x)
                self.assertEqual("sec_embargo_violation:Insurers" not in result["errors"], valid)
                self.assertEqual(result["index_aics"] is not None, valid)

    def test_nonempty_malformed_hash_is_rejected(self):
        x = fixture()
        x["nodes"]["Repo"]["evidence"]["source_sha256"] = "unit-test-only"
        result = module.evaluate(x)
        self.assertIn("invalid_source_sha256:Repo", result["errors"])
        self.assertIsNone(result["index_aics"])

    def test_unverified_source_fails(self):
        x=fixture()
        x["nodes"]["Repo"]["evidence"]["independently_verified_pit"]=False
        self.assertIsNone(module.evaluate(x)["index_aics"])
    def test_hot_node_strict_threshold(self):
        x=fixture()
        for name in list(module.WEIGHTS)[:3]:
            x["nodes"][name]["score"]=60
        self.assertEqual(module.evaluate(x)["hot_nodes"],0)
        for name in list(module.WEIGHTS)[:3]:
            x["nodes"][name]["score"]=61
        self.assertEqual(module.evaluate(x)["multiplier"],1.20)
    def test_training_lookahead_fails(self):
        x=fixture()
        x["nodes"]["Repo"]["evidence"]["training_cutoff"]="2026-11-19"
        self.assertIsNone(module.evaluate(x)["index_aics"])

if __name__=="__main__":
    unittest.main()
