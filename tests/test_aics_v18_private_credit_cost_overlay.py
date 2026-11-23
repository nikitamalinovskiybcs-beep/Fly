"""AICS V18 original OBDC cost provenance, 7 dated breadth events and null index."""
import copy
import json
import unittest
from datetime import date, timedelta

from scripts.aics_v18_private_credit_cost_overlay import (
    SRC, OUT, read, build, source_events,
)


class OriginalBdcCostSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger=read(SRC)
        cls.events=source_events(cls.ledger)
        cls.overlay=build(ledger=cls.ledger)

    def test_three_issuer_eight_original_quarters(self):
        data=self.ledger
        self.assertEqual(len(data["original_issuer_quarter_observations"]),24)
        self.assertEqual(len(data["quarter_roster"]),8)
        self.assertEqual(len(self.events),7)
        self.assertEqual(data["issuer_ciks"],{"ARCC":"1287750","BXSL":"1736035","OBDC":"1655888"})
        for row in data["original_issuer_quarter_observations"]:
            self.assertEqual(date.fromisoformat(row["research_available_date_only_proxy"]),
                             date.fromisoformat(row["filed_at"])+timedelta(days=1))
            self.assertEqual(date.fromisoformat(row["legacy_sec_plus14_available_at"]),
                             date.fromisoformat(row["filed_at"])+timedelta(days=14))
            self.assertIsNone(row["raw_original_document_sha256"])

    def test_obdc_original_2025_debt_cost_not_confused_with_fair(self):
        rows={r["quarter"]:r for r in self.ledger["original_issuer_quarter_observations"]
              if r["issuer"]=="OBDC"}
        self.assertEqual([rows[k]["nonaccrual_amortized_cost_pct"]
                          for k in ("2025-Q1","2025-Q2","2025-Q3")],["1.6","1.8","3.2"])
        self.assertEqual([rows[k]["nonaccrual_fair_value_pct"]
                          for k in ("2025-Q1","2025-Q2","2025-Q3")],["0.8","0.7","1.3"])
        self.assertEqual([rows[k]["original_debt_cost_table_usd_thousands"]["non_accrual"]
                          for k in ("2025-Q1","2025-Q2","2025-Q3")],
                         [243490,259382,457864])

    def test_seven_source_dated_score_events_replay(self):
        self.assertEqual([r["score"] for r in self.events],
                         ["0.00","100.00","0.00","66.67","33.33","33.33","66.67"])
        self.assertEqual([r["research_available_at_proxy"] for r in self.events],
                         ["2024-11-13","2025-02-27","2025-05-08","2025-08-07",
                          "2025-11-11","2026-02-26","2026-05-08"])
        self.assertTrue(all(not r["pre_registered_historical_formula"]
                            and not r["historically_contemporaneous_pit_attested"]
                            for r in self.events))

    def test_reject_tampered_issuer_source_and_obdc_cost(self):
        bad=copy.deepcopy(self.ledger)
        for row in bad["original_issuer_quarter_observations"]:
            if row["issuer"]=="OBDC" and row["quarter"]=="2025-Q2":
                row["nonaccrual_amortized_cost_pct"]="0.7"  # fair value: wrong input
                break
        with self.assertRaises(ValueError):
            source_events(bad)
        bad=copy.deepcopy(self.ledger)
        bad["original_issuer_quarter_observations"][0]["research_available_date_only_proxy"]="2020-01-01"
        with self.assertRaises(ValueError):
            source_events(bad)
        bad=copy.deepcopy(self.ledger)
        bad["original_issuer_quarter_observations"].pop()
        with self.assertRaises(ValueError):
            source_events(bad)

    def test_24month_calendar_coverage_grows_but_no_index(self):
        x=self.overlay
        self.assertEqual(x["calendar_source_weight_months"],12825)
        self.assertEqual(x["market_weekday_proxy_source_weight_months"],12600)
        self.assertEqual(x["calendar_research_source_coverage_pct"],"50.89")
        self.assertEqual(x["market_weekday_proxy_source_coverage_pct"],"50.00")
        self.assertEqual(x["additional_calendar_source_weight_months"],3150)
        self.assertEqual(x["additional_market_source_weight_months"],3150)
        self.assertEqual(len(x["monthly_calendar_end_research"]),24)
        self.assertEqual(len(x["monthly_last_weekday_market_proxy"]),24)
        self.assertTrue(x["scores_are_expost_not_preregistered"])
        self.assertFalse(x["historical_pit_source_bytes_independently_attested"])
        self.assertEqual(x["full_11node_index_months"],0)
        self.assertEqual(x["aics_sp500_spread_months"],0)
        self.assertFalse(x["production_index_changed"])
        self.assertFalse(x["trades_created"])

    def test_research_scope_and_age_no_lookahead(self):
        for key in ("monthly_calendar_end_research","monthly_last_weekday_market_proxy"):
            for row in self.overlay[key]:
                self.assertIsNone(row["full_aics"])
                self.assertIsNone(row["aics_sp500_spread"])
                self.assertFalse(row["historical_pit_certified"])
                self.assertEqual(len(row["node_scores"])+len(row["missing_nodes"]),11)
                self.assertEqual(sum(self.overlay["source_events"][0]["node"]==
                                    "Private Credit" for _ in range(1)),1)
                if row["node_scores"].get("Private Credit"):
                    credit=row["node_scores"]["Private Credit"]
                    self.assertLessEqual(credit["research_eligible_date"],row["cutoff_date"])
                    if "source_age_days" in credit:
                        self.assertLessEqual(credit["source_age_days"],90)
                        self.assertGreaterEqual(credit["source_age_days"],0)
                self.assertEqual(len(set(row["node_scores"]) & set(row["missing_nodes"])),0)
        may={row["month"]:row for row in self.overlay["monthly_calendar_end_research"]}["2025-05"]
        self.assertEqual(may["node_scores"]["Private Credit"]["score"],"0.00")
        oct={row["month"]:row for row in self.overlay["monthly_last_weekday_market_proxy"]}["2026-10"]
        self.assertEqual(oct["known_node_count"],8)
        self.assertEqual(oct["partial_weighted_points_not_full_aics"],"268.39")

    def test_exact_checked_in_json_replay(self):
        self.assertEqual(self.overlay,read(OUT))


if __name__=="__main__":
    unittest.main()
