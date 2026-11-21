"""Tests for real-source historical cash-imbalance shadow. No synthetic research data."""
from __future__ import annotations
import copy
import datetime as dt
import unittest

from scripts.aics_early_imbalance_cashflow_shadow import (
    Y2025,Q42025,Q22026,Q32026,build,read,ISSUERS
)

class HyperscalerPrecrisisImbalanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals=(read(Y2025),read(Q42025),read(Q22026),read(Q32026))
        cls.result=build(*cls.originals,as_of=dt.date(2026,11,22))

    def test_quarter_panel_only_original_sources(self):
        r=self.result
        self.assertEqual(len(r["quarterly_original_issuer_records"]),24)
        self.assertEqual([x["period"] for x in r["complete_or_partial_quarters"]],
                         ["2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q2","2026-Q3"])
        self.assertEqual(r["missing_quarters_not_imputed"],["2026-Q1"])
        self.assertTrue(all(x["four_issuer_complete"]
                            and x["issuer_count"]==4 for x in r["complete_or_partial_quarters"]))
        self.assertTrue(all(x["issuer"] in ISSUERS
                            and not x["independent_historical_provider_receipt_attested"]
                            for x in r["quarterly_original_issuer_records"]))
        self.assertEqual(r["fixed_original_aics_node_weights_total"],1050)
        self.assertFalse(r["extra_index_node_created"])
        self.assertIsNone(r["full_11_node_aics"])
        self.assertIsNone(r["precrisis_crisis_prediction_probability"])

    def test_monetary_q3_yoy_matches_named_original_filings(self):
        r=self.result
        periods={x["period"]:x for x in r["complete_or_partial_quarters"]}
        self.assertEqual(periods["2025-Q3"]["four_issuer_ocf_usd_m"],"158995")
        self.assertEqual(periods["2025-Q3"]["four_issuer_cash_ppe_usd_m"],"97271")
        self.assertEqual(periods["2025-Q3"]["four_issuer_cash_gap_usd_m"],"61724")
        self.assertEqual(periods["2025-Q3"]["cash_ppe_over_ocf_pct"],"61.18")
        self.assertEqual(periods["2026-Q3"]["four_issuer_ocf_usd_m"],"175498")
        self.assertEqual(periods["2026-Q3"]["four_issuer_cash_ppe_usd_m"],"201923")
        self.assertEqual(periods["2026-Q3"]["four_issuer_cash_gap_usd_m"],"-26425")
        self.assertEqual(periods["2026-Q3"]["cash_ppe_over_ocf_pct"],"115.06")
        y=r["same_issuer_yoy_q3"]
        self.assertEqual(y["cash_gap_deterioration_usd_m"],"-88149")
        self.assertEqual(y["cash_ppe_over_ocf_change_percentage_points"],"53.88")
        self.assertEqual(y["cash_ppe_growth_pct"],"107.59")
        self.assertEqual(y["asof_after_all_four_2026_original_sec_plus14"],"2026-11-13")
        self.assertEqual(len(periods["2026-Q3"]["observed_negative_cash_gap_issuers"]),3)
        self.assertEqual(len(periods["2025-Q3"]["observed_negative_cash_gap_issuers"]),0)

    def test_before_q3_2026_original_filing_no_yoy_and_no_future_source(self):
        r=build(*self.originals,as_of=dt.date(2026,10,30))
        self.assertNotIn("2026-Q3",[x["period"] for x in r["complete_or_partial_quarters"]])
        self.assertIsNone(r["same_issuer_yoy_q3"])
        self.assertFalse(r["2026_10_30_marketclose_q3_2026_available"])
        self.assertEqual(len(r["quarterly_original_issuer_records"]),20)

    def test_partial_2026_q3_before_all_four_sec_available(self):
        r=build(*self.originals,as_of=dt.date(2026,11,11))
        latest=[x for x in r["complete_or_partial_quarters"] if x["period"]=="2026-Q3"][0]
        self.assertFalse(latest["four_issuer_complete"])
        self.assertIsNone(latest["four_issuer_ocf_usd_m"])
        self.assertIsNone(r["same_issuer_yoy_q3"])
        self.assertEqual(latest["missing_issuers"],["Amazon"])

    def test_no_conflation_of_2025_2026_original_prior_comparative(self):
        a,b,c,d=copy.deepcopy(self.originals)
        d["rows"][0]["prior"]["cash_ppe"]=999
        with self.assertRaises(ValueError):
            build(a,b,c,d,as_of=dt.date(2026,11,22))

    def test_sec_plus14_timestamp_and_original_doc_required(self):
        a,b,c,d=copy.deepcopy(self.originals)
        b["issuer_rows"][0]["available_at"]="2026-02-10"
        with self.assertRaises(ValueError):
            build(a,b,c,d,as_of=dt.date(2026,11,22))
        a,b,c,d=copy.deepcopy(self.originals)
        d["rows"][0]["source"]="https://example.com/false-data"
        with self.assertRaises(ValueError):
            build(a,b,c,d,as_of=dt.date(2026,11,22))

    def test_stated_q2_cash_gap_matches_original(self):
        r=self.result
        periods={x["period"]:x for x in r["complete_or_partial_quarters"]}
        self.assertEqual(periods["2026-Q2"]["four_issuer_cash_gap_usd_m"],"6709")
        self.assertEqual(periods["2026-Q2"]["source_eligible_at"],"2026-08-14")
        self.assertTrue(r["separate_imbalance_layer_not_aics_score"])

if __name__=="__main__":
    unittest.main()
