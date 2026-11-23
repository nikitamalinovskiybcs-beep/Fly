"""Original-SEC 2025 Neoclouds: arithmetic, chronology, no fabricated PIT."""
import copy
import json
import unittest

from scripts.aics_neocloud_2025_sec_quarters import RECEIPT, calculate


class Neocloud2025OriginalSECResearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt=json.loads(RECEIPT.read_text(encoding="utf-8"))

    def test_real_three_quarters(self):
        r=calculate(self.receipt)
        self.assertEqual([(x["period"],x["available_at"],x["score"]) for x in r],
                         [("2025-Q1","2025-06-03","100.00"),
                          ("2025-Q2","2025-08-27","100.00"),
                          ("2025-Q3","2025-11-27","51.90")])
        self.assertEqual(r[2]["total_cfo_usd_m"],"1608.734")
        self.assertEqual(r[2]["total_cash_purchases_usd_m"],"3344.388")
        self.assertTrue(all(x["full_aics"] is None for x in r))
        self.assertTrue(all(x["historical_pit_certified"] is False for x in r))

    def test_q3_ytd_claim_mismatch_rejected(self):
        v=copy.deepcopy(self.receipt)
        v["sources"]["crwv_9m"]["cfo_ytd"]="1498.051"
        with self.assertRaisesRegex(ValueError,"mismatched"):
            calculate(v)

    def test_sec_embargo_violation(self):
        v=copy.deepcopy(self.receipt)
        v["sources"]["nbis_9m"]["available_at"]="2025-11-14"
        with self.assertRaisesRegex(ValueError,"SEC 14-day"):
            calculate(v)

    def test_wrong_company_accession_rejected(self):
        v=copy.deepcopy(self.receipt)
        v["sources"]["crwv_q1"]["source_page"]=v["sources"]["nbis_q1"]["source_page"]
        with self.assertRaisesRegex(ValueError,"accession or issuer"):
            calculate(v)

    def test_retrospective_raw_hash_may_not_be_claimed(self):
        v=copy.deepcopy(self.receipt)
        v["sources"]["nbis_q2"]["source_raw_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"original bytes"):
            calculate(v)

    def test_scores_and_certifications_not_promoted(self):
        v=copy.deepcopy(self.receipt)
        v["observations"][2]["score"]="100.00"
        with self.assertRaisesRegex(ValueError,"mismatched"):
            calculate(v)
        v=copy.deepcopy(self.receipt)
        v["independent_24_month_oos"]=True
        with self.assertRaisesRegex(ValueError,"AICS index"):
            calculate(v)


if __name__=="__main__":
    unittest.main()
