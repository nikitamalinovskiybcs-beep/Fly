"""No score promotion from Nov-20 official observations without a matching input."""
import copy
import json
import unittest
from scripts.aics_verify_close_source_eligibility_20261120 import LEDGER, validate
from scripts.aics_close_20261120 import calculate


class CloseSourceEligibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.close = calculate()

    def test_readiness_and_new_source_dates(self):
        got = validate(self.record, self.close)
        self.assertEqual(got["11_nodes_source_eligibility_checked"], 11)
        self.assertEqual(got["new_official_evidence_checks"], 5)
        self.assertEqual(got["score_changes"], 0)
        self.assertEqual(got["research_aics_rollover"], "669.09")
        self.assertEqual(got["next_sec_eligibility_coreweave_q3"], "2026-11-26")
        self.assertIsNone(got["certified_aics"])

    def test_disallow_backdating_coreweave(self):
        data = copy.deepcopy(self.record)
        row = next(x for x in data["newly_checked_official_evidence"] if x["node"]=="SPV")
        row["available_at"]="2026-11-20"
        with self.assertRaisesRegex(ValueError,"SEC \+14"):
            validate(data,self.close)

    def test_disallow_score_change_without_matching_evidence(self):
        data=copy.deepcopy(self.record)
        next(x for x in data["nodes"] if x["node"]=="Insurers")["score"]=2.0
        with self.assertRaisesRegex(ValueError,"Score mutated"):
            validate(data,self.close)

    def test_reject_treasury_mismatch(self):
        data=copy.deepcopy(self.record)
        row=next(x for x in data["newly_checked_official_evidence"] if x["node"]=="UST 30Y")
        row["change_bp"]="-8"
        with self.assertRaisesRegex(ValueError,"Treasury"):
            validate(data,self.close)

    def test_reject_unjustified_promotion(self):
        data=copy.deepcopy(self.record)
        data["independent_pit_attested_nodes"]=1
        with self.assertRaisesRegex(ValueError,"promotion"):
            validate(data,self.close)

    def test_reject_unhashed_met_filing_claim(self):
        data=copy.deepcopy(self.record)
        row=next(x for x in data["newly_checked_official_evidence"] if x["node"]=="Insurers")
        row["independent_rehash"]=True
        with self.assertRaisesRegex(ValueError,"byte replay"):
            validate(data,self.close)


if __name__ == "__main__":
    unittest.main()
