"""Parser contract tests with mock original-return fixtures, never model input."""
import copy
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import aics_insurers_mixed_credit_originals as gate

PRU_FIXTURE = {
    "pru": {
        "sec_filed_at": "2026-11-04", "sec_available_at": "2026-11-18",
        "original_sec_bytes_rehashed": 56_649_032,
        "original_sec_sha256": gate.PRU_SOURCE_SHA,
        "original_sec_url": "https://www.sec.gov/Archives/edgar/data/1137774/000113777426000221/pru-20260930.htm",
        "facts": {
            "net_commercial_mortgage_and_other_loans_millions":{
                "2025-12-31":64715,"2026-09-30":67004},
            "loan_credit_loss_allowance_millions":{
                "2025-12-31":469,"2026-09-30":449},
            "nonaccrual_loans_without_related_acl_millions":{
                "2025-12-31":442,"2026-09-30":610},
            "loan_net_change_millions":2289,
            "loan_net_change_pct":"3.54",
            "nonaccrual_no_related_allowance_change_millions":168,
            "nonaccrual_no_related_allowance_change_pct":"38.01",
        },
    },
    "met_september_10q":{"eligible_at_frozen_cutoff":False},
    "met_q3_sec_metrics_eligible":False,
}
MET_FIXTURE = {
    "period_end":"2026-06-30","filed_at":"2026-08-06",
    "sec_available_at":"2026-08-20",
    "original_full_submission_sha256":gate.MET_SOURCE_SHA,
    "embedded_primary_10q_sha256":gate.MET_PRIMARY_SHA,
    "original_sec_url":"https://www.sec.gov/Archives/edgar/data/1099219/000109921926000050/0001099219-26-000050.txt",
    "met_september_q3_available_at":"2026-11-20",
    "facts":{
        "mortgage_loans_net_millions":{"2025-12-31":84593,"2026-06-30":82856},
        "mortgage_loan_acl_millions":{"2025-12-31":1193,"2026-06-30":1358},
        "mortgage_loans_net_change_millions":-1737,
        "mortgage_loans_net_change_pct":"-2.05",
        "mortgage_acl_change_millions":165,
        "mortgage_acl_change_pct":"13.83",
        "acl_segment_end_millions":{
            "commercial":1016,"agricultural":107,"residential":235,"total":1358},
        "acl_segment_six_month_provision_millions":{"total":316},
        "net_six_month_chargeoffs_millions":151,
    },
}


def exercise(pru=None,met=None,as_of=dt.date(2026,11,19)):
    with tempfile.TemporaryDirectory() as d:
        tmp=Path(d)
        (tmp/"met_q2_original_full_submission.txt").write_bytes(b"synthetic test placeholder")
        with patch.object(gate,"pru_build",return_value=copy.deepcopy(pru or PRU_FIXTURE)),\
             patch.object(gate,"met_build",return_value=copy.deepcopy(met or MET_FIXTURE)):
            return gate.replay(tmp,tmp,as_of)


class TestMixedInsurerOriginals(unittest.TestCase):
    def test_descriptive_changes_without_cross_issuer_risk_ranking(self):
        r=exercise()
        self.assertEqual(r["pru_q3"]["nonaccrual_subset_change_pct"],"38.01")
        self.assertEqual(r["pru_q3"]["acl_change_pct"],"-4.26")
        self.assertEqual(r["pru_q3"]["loan_change_pct"],"3.54")
        self.assertEqual(r["met_q2"]["loan_change_pct"],"-2.05")
        self.assertEqual(r["met_q2"]["acl_change_pct"],"13.83")
        self.assertEqual(r["met_q2"]["acl_six_month_net_chargeoffs_millions"],151)
        self.assertEqual(r["met_q3"]["sec_available_at"],"2026-11-20")
        self.assertIsNone(r["met_q3"]["loan_balance_millions"])
        self.assertFalse(r["simultaneous_september_2026_coverage_for_both_issuers"])
        self.assertFalse(r["directly_comparable_portfolio_risk_ratios"])
        self.assertFalse(r["historic_release_time_independently_attested"])
        self.assertEqual(r["synthetic_rows"],0)
        self.assertIsNone(r["insurers_node_score"])
        self.assertIsNone(r["index_aics"])
        self.assertEqual(r["promotion"],"BLOCKED")

    def test_false_q3_met_eligibility_fails_closed(self):
        altered=copy.deepcopy(MET_FIXTURE)
        altered["met_september_q3_available_at"]="2026-11-19"
        with self.assertRaisesRegex(ValueError,"eligibility"):
            exercise(met=altered)

    def test_forged_pru_nonaccrual_and_met_acl_rejected(self):
        pru=copy.deepcopy(PRU_FIXTURE)
        pru["pru"]["facts"]["nonaccrual_loans_without_related_acl_millions"]["2026-09-30"]=611
        with self.assertRaisesRegex(ValueError,"originals"):
            exercise(pru=pru)
        met=copy.deepcopy(MET_FIXTURE)
        met["facts"]["mortgage_loan_acl_millions"]["2026-06-30"]=1359
        with self.assertRaisesRegex(ValueError,"originals"):
            exercise(met=met)

    def test_no_review_after_frozen_cutoff(self):
        with self.assertRaisesRegex(ValueError,"frozen"):
            exercise(as_of=dt.date(2026,11,20))

    def test_hash_and_missing_real_source_rejected(self):
        pru=copy.deepcopy(PRU_FIXTURE)
        pru["pru"]["original_sec_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"source original"):
            exercise(pru=pru)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                gate.replay(Path(d),Path(d))


if __name__=="__main__":
    unittest.main()
