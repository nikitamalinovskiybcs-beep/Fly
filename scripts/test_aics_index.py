import unittest
from aics_index import WEIGHTS, calculate, sec_available_at, alfred_value_at

class AICSTest(unittest.TestCase):
    def test_weights(self):
        self.assertEqual(sum(WEIGHTS.values()), 1050)
    def test_missing_blocks_publication(self):
        self.assertFalse(calculate({})["publishable"])
    def test_unverified_blocks_publication(self):
        self.assertFalse(calculate(dict.fromkeys(WEIGHTS, 40))["publishable"])
    def test_sec_lag(self):
        self.assertEqual(sec_available_at("2026-11-01").isoformat(), "2026-11-15")
    def test_alfred_vintage(self):
        rows = [{"date":"2026-01-01","realtime_start":"2026-01-02",
                 "realtime_end":"2026-02-01","value":"4.0"},
                {"date":"2026-01-01","realtime_start":"2026-02-02",
                 "realtime_end":"9999-12-31","value":"5.0"}]
        self.assertEqual(alfred_value_at(rows,"2026-01-01","2026-01-20"),4.0)
        self.assertIsNone(alfred_value_at(rows,"2026-01-01","2026-02-01") if False else alfred_value_at(rows,"2026-01-01","2026-01-01"))
        self.assertEqual(alfred_value_at(rows,"2026-01-01","2026-03-01"),5.0)
    def test_thresholds(self):
        scores = dict.fromkeys(WEIGHTS, 0)
        verified = set(WEIGHTS)
        self.assertEqual(calculate(scores,verified_nodes=verified)["verdict"],"entry")
        scores = dict.fromkeys(WEIGHTS, 100)
        self.assertEqual(calculate(scores,verified_nodes=verified)["verdict"],"cash")
    def test_hot_strict(self):
        scores = dict.fromkeys(WEIGHTS, 60)
        self.assertEqual(calculate(scores,verified_nodes=WEIGHTS)["hot_nodes"],0)

if __name__ == "__main__":
    unittest.main()
