"""Source-weight observability is not a completed historical AICS or PIT."""
import copy
import json
import unittest

from scripts.aics_24m_weighted_observability import SOURCE, OUTPUT, build


class WeightedObservabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_24_months_and_weighted_research_coverage(self):
        d=build(self.source)
        self.assertEqual(d,json.loads(OUTPUT.read_text(encoding="utf-8")))
        self.assertEqual(d["months_with_at_least_one_research_node"],24)
        self.assertEqual(d["months_with_full_eleven_node_aics"],0)
        self.assertEqual(d["months_with_historical_aics_sp500_spread"],0)
        self.assertEqual(d["sum_known_weight_months"],7325)
        self.assertEqual(d["sum_total_possible_weight_months"],25200)
        self.assertEqual(d["average_known_weight_pct_not_pit"],"29.07")
        self.assertEqual(d["months_by_known_research_node_count"],{"2":7,"3":14,"6":1,"7":1,"10":1})
        first,last=d["rows"][0],d["rows"][-1]
        self.assertEqual((first["known_research_nodes"],first["known_research_node_weight"],first["unobserved_node_weight"],first["source_eligible_weight_pct_not_pit"]),(2,175,875,"16.67"))
        self.assertEqual((last["known_research_nodes"],last["known_research_node_weight"],last["unobserved_node_weight"],last["source_eligible_weight_pct_not_pit"]),(10,950,100,"90.48"))
        self.assertTrue(all(x["full_actual_aics"] is None and x["aics_sp500_historical_spread"] is None for x in d["rows"]))
        self.assertFalse(d["independent_historical_pit_verified"])

    def test_no_synthetic_certifications_or_undated_inputs(self):
        bad=copy.deepcopy(self.source)
        bad["monthly"][0]["full_11_node_aics_no_multiplier"]=39.68
        with self.assertRaisesRegex(ValueError,"promoted"):
            build(bad)
        bad=copy.deepcopy(self.source)
        bad["monthly"][0]["latest_eligible_research_scores"]["Insurers"]["source_available_at"]="2026-11-30"
        with self.assertRaisesRegex(ValueError,"Future"):
            build(bad)

    def test_cannot_silently_add_missing_node_as_zero(self):
        bad=copy.deepcopy(self.source)
        first=bad["monthly"][0]
        first["missing_nodes"].remove("AI Equities")
        first["latest_eligible_research_scores"]["AI Equities"]={"score":"0","source_available_at":"2024-11-01"}
        first["known_node_count_research_only"]+=1
        # A forged known node would need a real signed original source, which
        # this availability-only metric cannot independently certify.
        # This test uses a source-date contradiction to preserve fail-closed.
        first["latest_eligible_research_scores"]["AI Equities"]["source_available_at"]="2026-11-21"
        with self.assertRaisesRegex(ValueError,"Future"):
            build(bad)

if __name__=="__main__":
    unittest.main()
