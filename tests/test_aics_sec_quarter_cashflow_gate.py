"""Fixture-only unit tests: numeric examples are never production evidence."""
from __future__ import annotations
import unittest
from scripts.aics_sec_quarter_cashflow_gate import audit, OCF, CAPEX

SHA="a"*64
ACC="0001234567-26-000001"

def fact(tag,value,**overrides):
    row={"source_id":"XBRL_MSFT","cik":"789019","tag":tag,"unit":"USD",
         "value":value,"period_start":"2026-07-01","period_end":"2026-09-30",
         "filed_at":"2026-10-27","research_eligible_date_only_proxy":"2026-10-28",
         "original_sec_accession":ACC,"form":"10-Q","frame":"CY2026Q3",
         "original_companyfacts_snapshot_sha256":SHA,
         "original_first_document_bytes_verified":False,
         "retrospective_provider_pit_certified":False}
    row.update(overrides)
    return row

class OriginalPeriodCashflowTests(unittest.TestCase):
    def test_direct_three_month_pair(self):
        x=audit([fact(OCF,120000000),fact(CAPEX,75000000)],as_of="2026-11-22")
        self.assertEqual(x["direct_original_3month_pair_candidates"],1)
        self.assertEqual(x["candidate_quarter_pairs"][0]["cash_gap_usd"],"45000000")
        self.assertFalse(x["independently_pit_attested"])
        self.assertEqual(x["node_scores_promoted"],0)
        self.assertIsNone(x["full_11_node_aics"])

    def test_cannot_pair_different_accessions(self):
        x=audit([fact(OCF,120),fact(CAPEX,70,original_sec_accession="0001234567-26-000002")],as_of="2026-11-22")
        self.assertEqual(x["direct_original_3month_pair_candidates"],0)
        self.assertEqual(x["blocked_period_or_source_candidates"],2)

    def test_year_to_date_refused(self):
        x=audit([fact(OCF,120,period_start="2026-01-01"),fact(CAPEX,70,period_start="2026-01-01")],as_of="2026-11-22")
        self.assertEqual(x["direct_original_3month_pair_candidates"],0)
        self.assertEqual(x["reasons"]["long_ytd_or_nonquarter_duration"],2)

    def test_late_filing_not_released_yet(self):
        x=audit([fact(OCF,120,filed_at="2026-11-22",research_eligible_date_only_proxy="2026-11-23")],as_of="2026-11-22")
        self.assertEqual(x["direct_original_3month_pair_candidates"],0)
        self.assertEqual(x["reasons"]["not_yet_available_by_current_research_date"],1)

    def test_duplicate_identical_cashflow_not_counted_twice(self):
        x=audit([fact(OCF,120),fact(OCF,120),fact(CAPEX,70)],as_of="2026-11-22")
        self.assertEqual(x["direct_original_3month_pair_candidates"],1)
        self.assertEqual(x["reasons"]["duplicate_identical_value_ignored"],1)

    def test_conflicting_same_tag_refused(self):
        x=audit([fact(OCF,120),fact(OCF,125),fact(CAPEX,70)],as_of="2026-11-22")
        self.assertEqual(x["direct_original_3month_pair_candidates"],0)
        self.assertEqual(x["reasons"]["ambiguous_multiple_values_or_source"],1)

    def test_invalid_sha_dates_and_original_claim_blocked(self):
        for change in ({"original_companyfacts_snapshot_sha256":"no"},
                       {"original_first_document_bytes_verified":True},
                       {"research_eligible_date_only_proxy":"2026-10-27"},
                       {"period_end":"2026-12-31"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                audit([fact(OCF,120,**change)],as_of="2026-11-22")

    def test_non_usd_cashflow_not_miscombined(self):
        x=audit([fact(OCF,120,unit="EUR"),fact(CAPEX,70)],as_of="2026-11-22")
        self.assertEqual(x["direct_original_3month_pair_candidates"],0)
        self.assertEqual(x["reasons"]["non_usd_cashflow_unit"],1)

if __name__=="__main__":
    unittest.main()
