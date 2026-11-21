"""Purely artificial arithmetic tests, not market observations or live signals."""
import hashlib
import importlib.util
import unittest
from pathlib import Path

path=Path(__file__).resolve().parents[1]/"scripts"/"aics_minimal_model.py"
spec=importlib.util.spec_from_file_location("minimal_model",path)
model_module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_module)

def model_input(score):
    return {"as_of":"2026-11-18","nodes":{
        name:{"score":score,"evidence":{
            "source_uri":"https://example.invalid/artificial-test-only",
            "source_sha256":hashlib.sha256(b"unit-test-only").hexdigest(),
            "available_at":"2026-11-01",
            "independently_verified_pit":True,
            "score_method_version":"unit-test",
            "training_cutoff":"2026-10-31"}}
        for name in model_module.gate.WEIGHTS}}

class MinimalModelTests(unittest.TestCase):
    def test_no_data_returns_no_index(self):
        r=model_module.model({"as_of":"2026-11-18","nodes":{}})
        self.assertIsNone(r["index_aics"])
        self.assertEqual(r["signal"],"INSUFFICIENT_VERIFIED_DATA")
        self.assertIsNone(r["uncertified_arithmetic_candidate"])
        self.assertFalse(r["trades_created"])
    def test_entry_band(self):
        r=model_module.model(model_input(20))
        self.assertIsNone(r["index_aics"])
        self.assertEqual(r["uncertified_arithmetic_candidate"],210)
        self.assertEqual(r["band"],"BELOW_450")
        self.assertEqual(r["promotion"],"BLOCKED")
        self.assertEqual(r["signal"],"UNVERIFIED_SCORE_CANDIDATE_RESEARCH_ONLY")
    def test_watch_band(self):
        r=model_module.model(model_input(45))
        self.assertIsNone(r["index_aics"])
        self.assertEqual(r["uncertified_arithmetic_candidate"],472.5)
        self.assertEqual(r["band"],"450_TO_500")
    def test_cash_zone(self):
        r=model_module.model(model_input(50))
        self.assertIsNone(r["index_aics"])
        self.assertEqual(r["uncertified_arithmetic_candidate"],525)
        self.assertEqual(r["band"],"ABOVE_500")
        self.assertFalse(r["trades_created"])
    def test_missing_evidence_fails_closed(self):
        x=model_input(50)
        del x["nodes"]["Repo"]["evidence"]
        self.assertIsNone(model_module.model(x)["index_aics"])
    def test_100_deterministic_safety_scenarios(self):
        # 100 arithmetic-only test cases, NOT 100 financial forecasts/backtests.
        for i in range(100):
            with self.subTest(case=i):
                x=model_input(i)
                if i%4==0:
                    x["nodes"].pop("Repo")
                elif i%4==1:
                    x["nodes"]["Repo"]["evidence"]["available_at"]="2026-12-01"
                elif i%4==2:
                    x["nodes"]["Repo"]["evidence"]["independently_verified_pit"]=False
                r=model_module.model(x)
                self.assertIsNone(r["index_aics"])
                self.assertEqual(r["promotion"],"BLOCKED")
                self.assertFalse(r["trades_created"])
                self.assertFalse(r["score_provenance_independently_audited"])
                if i%4!=3:
                    self.assertIsNone(r["uncertified_arithmetic_candidate"])
                else:
                    self.assertIsNotNone(r["uncertified_arithmetic_candidate"])
    def test_hot_multiplier(self):
        x=model_input(50)
        for name in list(model_module.gate.WEIGHTS)[:3]:
            x["nodes"][name]["score"]=61
        r=model_module.model(x)
        self.assertEqual(r["hot_nodes"],3)
        self.assertAlmostEqual(r["multiplier"],1.2)

if __name__=="__main__":
    unittest.main()
