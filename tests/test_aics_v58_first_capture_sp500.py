"""Tests for actual, future-only FRED market-close capture. ALL fixture prices fake.

Do not use the test CSV as a real source receipt, forecast, or backfill.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import unittest
from decimal import Decimal

from scripts.aics_v58_first_capture_sp500 import (
    LEDGER, SOURCE_URL, _parse_source, receipt, update_ledger, _following_month,
)

UTC=dt.timezone.utc
NOW_NOV=dt.datetime(2026,11,22,18,0,tzinfo=UTC)
NOW_DEC=dt.datetime(2026,12,2,18,0,tzinfo=UTC)


def csv_test(*rows):
    return ("observation_date,SP500\n"+
            "".join(f"{d},{p}\n" for d,p in rows)).encode("utf-8")


def mocked_complete():
    """These fabricated values exist ONLY in this test fixture."""
    return csv_test(
        ("2026-10-30","7111.00"),
        ("2026-11-20","7040.12"),
        ("2026-11-27","7012.30"),
        ("2026-11-30","7000.50"),
        ("2026-12-01","7015.50"),
    )


class FirstCaptureSP500Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.empty=json.loads(LEDGER.read_text(encoding="utf-8"))

    def test_current_november_22_cannot_capture_october_as_new_forward_month(self):
        data=csv_test(("2026-10-30","7111.00"),("2026-11-20","7040.12"))
        report=receipt(data,now=NOW_NOV)
        self.assertEqual(report["status"],"NOT_YET_ELIGIBLE_POST_FREEZE_MONTH")
        self.assertEqual(report["required_completed_month"],"2026-10")
        self.assertIsNone(report["month_close_candidate_for_V56"])
        new,changed=update_ledger(self.empty,report,data)
        self.assertFalse(changed)
        self.assertEqual(new,self.empty)

    def test_future_month_cannot_be_claimed_complete_until_first_next_month_trade(self):
        data=csv_test(("2026-11-20","7040.12"),
                      ("2026-11-27","7012.30"),
                      ("2026-11-30","7000.50"))
        report=receipt(data,now=NOW_DEC)
        self.assertEqual(report["status"],"WAITING_FOR_FIRST_NEXT_MONTH_MARKET_CLOSE")
        self.assertIsNone(report["month_close_candidate_for_V56"])
        self.assertFalse(report["first_next_month_observation_proof_present"])

    def test_when_genuine_december_trade_exists_november_only_becomes_candidate(self):
        report=receipt(mocked_complete(),now=NOW_DEC)
        self.assertEqual(report["status"],"NEW_MONTH_CLOSE_SOURCE_CANDIDATE")
        x=report["month_close_candidate_for_V56"]
        self.assertEqual(x["month"],"2026-11")
        self.assertEqual(x["market_close_date"],"2026-11-30")
        self.assertEqual(x["sp500_close"],7000.50)
        self.assertEqual(x["source_uri"],SOURCE_URL)
        self.assertEqual(len(x["source_sha256"]),64)
        self.assertFalse(x["independently_verified_first_publication_PIT"])
        self.assertTrue(report["licensed_data_full_csv_must_not_be_committed"])
        self.assertIsNone(report["official_AICS"])

    def test_append_only_and_same_market_month_idempotent_when_csv_new_rows_added(self):
        r=receipt(mocked_complete(),now=NOW_DEC)
        a,changed=update_ledger(self.empty,r,mocked_complete())
        self.assertTrue(changed)
        self.assertEqual(len(a["observed_sp500_month_closes"]),1)
        self.assertEqual(len(self.empty["observed_sp500_month_closes"]),0)
        repeat,c=update_ledger(a,r,mocked_complete())
        self.assertFalse(c)
        self.assertEqual(repeat,a)
        extra=csv_test(("2026-11-30","7000.50"),
                       ("2026-12-01","7015.50"),("2026-12-02","7030.00"))
        new_capture=receipt(extra,now=dt.datetime(2026,12,3,17,0,tzinfo=UTC))
        self.assertNotEqual(r["original_csv_bytes_sha256"],
                            new_capture["original_csv_bytes_sha256"])
        b,changed=update_ledger(a,new_capture,extra)
        self.assertFalse(changed)
        self.assertEqual(b,a)

    def test_revised_original_month_close_does_not_rewrite_earlier_receipt(self):
        r=receipt(mocked_complete(),now=NOW_DEC)
        ledger,_=update_ledger(self.empty,r,mocked_complete())
        revised_raw=csv_test(("2026-11-30","7001.00"),
                             ("2026-12-01","7015.50"))
        revised=receipt(revised_raw,now=NOW_DEC)
        with self.assertRaisesRegex(ValueError,"revision"):
            update_ledger(ledger,revised,revised_raw)

    def test_truncated_non_utf8_and_future_dated_source_is_rejected(self):
        for content in (b"",b"\xff\xfe",b"Invalid source",
                        csv_test(("2026-11-30","7000.50"),("2026-12-05","7015.50"))):
            with self.assertRaises(ValueError):
                receipt(content,now=NOW_DEC)
        with self.assertRaises(ValueError):
            _parse_source(csv_test(("2026-12-01","7015"),
                                   ("2026-11-30","7000")),NOW_DEC)
        with self.assertRaises(ValueError):
            _parse_source(csv_test(("2026-11-30","nan")),NOW_DEC)

    def test_no_upstream_source_price_reinterpretation_or_boolean_trade_signal(self):
        rows,missing=_parse_source(csv_test(("2026-11-27","."),("2026-11-30","7000.50"),
                                            ("2026-12-01","7015.50")),NOW_DEC)
        self.assertEqual(missing,1)
        self.assertEqual(rows[0][1],Decimal("7000.50"))
        self.assertEqual(len(rows),2)
        self.assertEqual(_following_month("2026-12"),"2027-01")
        report=receipt(csv_test(("2026-11-30","7000.50"),("2026-12-01","7015.50")),
                       now=NOW_DEC)
        self.assertFalse(report["trades_created"])
        self.assertFalse(report["models_or_5_expert_signals_computed"])

    def test_missing_ledger_contract_and_altered_sha_metadata_are_rejected(self):
        r=receipt(mocked_complete(),now=NOW_DEC)
        bad=copy.deepcopy(self.empty)
        bad["original_11node_AICS"]=500
        with self.assertRaises(ValueError):
            update_ledger(bad,r,mocked_complete())
        altered=copy.deepcopy(r)
        altered["month_close_candidate_for_V56"]["source_sha256"]="0"*64
        with self.assertRaises(ValueError):
            update_ledger(self.empty,altered,mocked_complete())
        self.assertEqual(len(self.empty["observed_sp500_month_closes"]),0)

    def test_block_spurious_2024_source_backfill_and_wrong_date_receipt(self):
        old=receipt(csv_test(("2024-10-31","4000"),("2024-11-01","4020")),
                    now=dt.datetime(2024,11,2,13,0,tzinfo=UTC))
        self.assertIsNone(old["month_close_candidate_for_V56"])
        self.assertEqual(old["status"],"NOT_YET_ELIGIBLE_POST_FREEZE_MONTH")
        r=receipt(mocked_complete(),now=NOW_DEC)
        edited=copy.deepcopy(r)
        edited["month_close_candidate_for_V56"]["market_close_date"]="2026-11-22"
        with self.assertRaisesRegex(ValueError,"does not match original"):
            update_ledger(self.empty,edited,mocked_complete())

if __name__=="__main__":
    unittest.main()
