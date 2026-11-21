"""Nine original Prudential credit statements: identical ratio, strict SEC+14."""
import copy
import json
import unittest
from scripts.aics_pru_insurers_original_quarters import LEDGER, calculate


class PrudentialInsurersOriginalHistoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(LEDGER.read_text(encoding="utf-8"))

    def test_dated_identical_metric_2025_2026(self):
        result=calculate(self.data)
        self.assertEqual(len(result),9)
        self.assertEqual(
            [(r["quarter"],r["available_at"],r["score"]) for r in result],
            [("2024-Q3","2024-11-14","0.26"),
             ("2024-Q4","2025-02-27","0.38"),
             ("2025-Q1","2025-05-15","0.51"),
             ("2025-Q2","2025-08-14","0.77"),
             ("2025-Q3","2025-11-13","0.74"),
             ("2025-Q4","2026-02-26","0.79"),
             ("2026-Q1","2026-05-20","0.44"),
             ("2026-Q2","2026-08-19","1.32"),
             ("2026-Q3","2026-11-18","1.04")])
        self.assertTrue(all(x["historical_provider_pit_certified"] is False for x in result))
        self.assertTrue(all(x["independent_24m_oos"] is False for x in result))

    def test_10k_q4_dated_and_cross_scope_q3_denominator(self):
        result=calculate(self.data)
        self.assertEqual(result[5]["available_at"],"2026-02-26")
        self.assertEqual(result[5]["score"],"0.79")
        self.assertEqual(result[-1]["score"],"1.04")
        for idx,key,bad in ((5,"commercial_mortgage_and_other_loans_net_usd_m",64715),
                            (8,"commercial_mortgage_and_other_loans_net_usd_m",67004)):
            ledger=copy.deepcopy(self.data)
            ledger["events"][idx][key]=bad
            with self.assertRaisesRegex(ValueError,"mismatched"):
                calculate(ledger)

    def test_2024_original_filing_gates_and_unmixed_denominators(self):
        result=calculate(self.data)
        self.assertEqual(result[0]["available_at"],"2024-11-14")
        self.assertEqual(result[1]["available_at"],"2025-02-27")
        self.assertEqual(result[0]["score"],"0.26")
        self.assertEqual(result[1]["score"],"0.38")
        for idx, field, altered in (
            (0, "commercial_mortgage_and_other_loans_net_usd_m", 62573),
            (1, "commercial_mortgage_and_other_loans_net_usd_m", 62341)):
            bad=copy.deepcopy(self.data)
            bad["events"][idx][field]=altered
            with self.assertRaisesRegex(ValueError,"mismatched"):
                calculate(bad)
        bad=copy.deepcopy(self.data)
        bad["events"][1]["available_at"]="2024-12-31"
        with self.assertRaisesRegex(ValueError,"chronology"):
            calculate(bad)

    def test_exact_filing_dates_cannot_backfill(self):
        data=copy.deepcopy(self.data)
        data["events"][0]["available_at"]="2025-05-01"
        with self.assertRaisesRegex(ValueError,"chronology"):
            calculate(data)

    def test_numerator_and_denominator_tamper_rejected(self):
        for k in ("nonaccrual_no_related_acl_usd_m",
                  "commercial_mortgage_and_other_loans_net_usd_m"):
            data=copy.deepcopy(self.data)
            data["events"][2][k]+=1
            with self.assertRaisesRegex(ValueError,"mismatched"):
                calculate(data)

    def test_wrong_issuer_cannot_satisfy_event(self):
        data=copy.deepcopy(self.data)
        data["events"][1]["cik"]="1099219"
        with self.assertRaisesRegex(ValueError,"issuer"):
            calculate(data)

    def test_false_certification_rejected(self):
        data=copy.deepcopy(self.data)
        data["independently_historically_contemporaneous_pit_certified"]=True
        with self.assertRaisesRegex(ValueError,"provenance"):
            calculate(data)
        data=copy.deepcopy(self.data)
        data["model_production_formula_modified"]=True
        with self.assertRaisesRegex(ValueError,"provenance"):
            calculate(data)

    def test_original_hash_claim_rejected(self):
        data=copy.deepcopy(self.data)
        data["events"][4]["source_raw_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"chronology"):
            calculate(data)


if __name__=="__main__":
    unittest.main()
