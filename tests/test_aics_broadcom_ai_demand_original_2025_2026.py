"""Original SEC Broadcom AI demand observed zero stress is not missing-value imputation."""
import copy
import json
import unittest

from scripts.aics_broadcom_ai_demand_original_2025_2026 import RECORD, calculate


class OriginalBroadcomAIDemandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(RECORD.read_text(encoding="utf-8"))

    def test_three_real_reported_quarter_pairs(self):
        result=calculate(self.data)
        self.assertEqual([(x["period"],x["available_at"],x["score"]) for x in result],[
            ("2025-Q3","2025-09-18","0.00"),
            ("2026-Q1","2026-03-18","0.00"),
            ("2026-Q2","2026-06-17","0.00")
        ])
        self.assertEqual([(r["reported_actual_usd_m"],r["previous_guidance_usd_m"]) for r in result],[
            (5200,5100),(8400,8200),(10800,10700)])
        self.assertNotIn("2025-Q4",[x["period"] for x in result])
        self.assertTrue(all(r["full_aics"] is None and not r["historically_pit_certified"] for r in result))

    def test_original_sec_filing_dates_and_embargo_unmovable(self):
        bad=copy.deepcopy(self.data)
        bad["filings"][1]["available_at"]="2025-09-04"
        with self.assertRaisesRegex(ValueError,"14-day"):
            calculate(bad)
        bad=copy.deepcopy(self.data)
        bad["filings"][3]["filed_at"]="2026-03-01"
        with self.assertRaisesRegex(ValueError,"14-day"):
            calculate(bad)

    def test_no_unknown_q4_2025_revenue_inferred(self):
        bad=copy.deepcopy(self.data)
        bad["observations"].append({
            "period":"2025-Q4","previous_forecast_from_period":"2025-Q3",
            "reported_actual_usd_m":6500,"previous_guidance_usd_m":6200,
            "available_at":"2025-12-25","score":"0.00"
        })
        with self.assertRaisesRegex(ValueError,"Only three"):
            calculate(bad)
        bad=copy.deepcopy(self.data)
        bad["excluded_quarters"]=[]
        with self.assertRaisesRegex(ValueError,"scope"):
            calculate(bad)

    def test_zero_is_computed_from_actual_and_guidance_not_inserted(self):
        bad=copy.deepcopy(self.data)
        bad["observations"][0]["reported_actual_usd_m"]=5000
        with self.assertRaisesRegex(ValueError,"mismatch"):
            calculate(bad)
        bad=copy.deepcopy(self.data)
        bad["observations"][2]["score"]="1.00"
        with self.assertRaisesRegex(ValueError,"formula"):
            calculate(bad)

    def test_source_identity_and_fake_production_pit_denied(self):
        bad=copy.deepcopy(self.data)
        bad["filings"][0]["original_sec_exhibit_url"]="https://www.sec.gov/Archives/edgar/data/0000000/tampered.html"
        with self.assertRaisesRegex(ValueError,"URL"):
            calculate(bad)
        bad=copy.deepcopy(self.data)
        bad["historical_provider_market_pit_certified"]=True
        with self.assertRaisesRegex(ValueError,"promotion"):
            calculate(bad)
        bad=copy.deepcopy(self.data)
        bad["certified_aics"]="500.00"
        with self.assertRaisesRegex(ValueError,"promotion"):
            calculate(bad)


if __name__=="__main__":
    unittest.main()
