"""Check real issuer IR observations and arithmetic without model certification."""
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/"aics_data/research/coreweave_q3_ir_interest_burden_2026-11-18.json"
RAW_RECEIPT=ROOT/"aics_data/progress/neocloud_spv_ir_raw_archive_receipt_2026-11-18.json"

class TestCoreWeaveIRResearch(unittest.TestCase):
    def test_observed_quarterly_ratio_from_published_values(self):
        d=json.loads(DATA.read_text())
        self.assertEqual(d["source_id"],"CRWV_2026Q3")
        self.assertEqual(d["quarter_revenue_usd_millions"],3661)
        self.assertEqual(d["quarter_net_interest_expense_usd_millions"],846)
        actual=Decimal(str(d["quarter_net_interest_expense_usd_millions"])) / Decimal(str(d["quarter_revenue_usd_millions"])) * 100
        self.assertEqual(round(actual,1),Decimal(str(d["descriptive_net_interest_expense_divided_by_revenue_pct"])))
        self.assertEqual(d["approximate_revenue_backlog_usd_billions"],132.5)

    def test_observed_value_is_traced_to_SHA_checked_raw_ir_bytes(self):
        d=json.loads(DATA.read_text())
        r=json.loads(RAW_RECEIPT.read_text())
        original=next(x for x in r["original_files"] if x["source_id"] == "CRWV_2026Q3")
        self.assertEqual(d["original_ir_html_sha256"],original["html_sha256"])
        self.assertEqual(d["source_url"],original["url"])
        self.assertTrue(d["source_bytes_independently_hash_checked"])

    def test_filing_14_day_embargo_not_prematurely_scored(self):
        d=json.loads(DATA.read_text())
        asof=dt.date.fromisoformat(d["observed_as_of"])
        filed=dt.date.fromisoformat(d["sec_10q_filed_at"])
        available=dt.date.fromisoformat(d["sec_10q_aics_available_at"])
        self.assertEqual(available,filed+dt.timedelta(days=14))
        self.assertLess(asof,available)
        self.assertLessEqual(dt.date.fromisoformat(d["source_release_date"]),asof)
        self.assertFalse(d["original_sec_filing_pit_certified"])
        self.assertIsNone(d["neocloud_stress_score"])
        self.assertIsNone(d["index_aics"])
        self.assertEqual(d["promotion"],"BLOCKED")
        self.assertFalse(d["trades_created"])

if __name__=="__main__":
    unittest.main()
