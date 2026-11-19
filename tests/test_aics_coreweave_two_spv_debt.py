"""Offline accounting reconciliation tests; fixtures do not enter AICS history."""
import copy
import json
import unittest
from pathlib import Path

from scripts.aics_coreweave_two_spv_debt import reconcile, _rate


def fixtures():
    source = json.loads(Path("aics_data/source_registry/neocloud_cash_h1_sec.json").read_text())["crwv_26_h1"]
    report = json.loads(Path("aics_data/research/neocloud_cash_coverage_2026_h1.json").read_text())
    return copy.deepcopy(report["coreweave_facilities"]["facilities"]), report, source


class TestCoreWeaveDDTLRecourse(unittest.TestCase):
    def test_real_research_facility_balances_and_different_recourse(self):
        rows, reviewed, registry = fixtures()
        report = reconcile(rows, reviewed, registry)
        self.assertEqual(report["two_distinct_contract_reported_debt_usd_m"], 3938)
        self.assertEqual(report["two_distinct_contract_ceiling_usd_m"], 11600)
        self.assertEqual(report["two_contract_balance_to_ceiling_pct"], "33.95")
        self.assertEqual(report["nonrecourse_with_limited_exceptions_reported_debt_usd_m"], 2837)
        self.assertEqual(report["unconditional_parent_guaranteed_facility_reported_debt_usd_m"], 1101)
        self.assertEqual([r["balance_to_ceiling_pct"] for r in report["facilities"]], ["33.38", "35.52"])
        self.assertEqual(report["sec_available_at"],"2026-08-26")
        self.assertEqual(report["economic_balance_as_of"],"2026-06-30")
        self.assertEqual([r["borrower"] for r in report["facilities"]], [
            "CoreWeave Compute Acquisition Co. VIII, LLC",
            "CoreWeave Financing DDTL V, LLC",
        ])
        self.assertIsNone(report["effective_economic_parent_recourse_usd_m"])
        self.assertIsNone(report["cash_drawn_2026_11_usd_m"])
        self.assertIsNone(report["remaining_undrawn_borrowing_capacity_usd_m"])
        self.assertFalse(report["independent_historical_pit_attested"])
        self.assertFalse(report["separately_reported_nscale_group_fundings_are_additive"])
        self.assertIsNone(report["spv_node_score"])
        self.assertIsNone(report["index_aics"])
        self.assertEqual(report["promotion"],"BLOCKED")

    def test_balance_to_ceiling_not_unlimited_or_rounded_up(self):
        self.assertEqual(_rate(2837,8500), "33.38")
        self.assertEqual(_rate(1101,3100), "35.52")
        for debt, ceiling in ((100,0), (100,50), (True,200), (-1,100), (0.5,100)):
            with self.subTest(debt=debt,ceiling=ceiling), self.assertRaises(ValueError):
                _rate(debt,ceiling)

    def test_forged_debt_principal_or_ceiling_rejected(self):
        for name, field, new_value in (
            ("DDTL 4.0","reported_debt_usd_m",2838),
            ("DDTL 5.0","reported_debt_usd_m",1100),
            ("DDTL 4.0","facility_ceiling_usd_m",8501),
            ("DDTL 5.0","facility_ceiling_usd_m",3101),
        ):
            with self.subTest(name=name,field=field):
                rows, checked, reg = fixtures()
                next(r for r in rows if r["facility"]==name)[field] = new_value
                with self.assertRaisesRegex(ValueError,"research differ"):
                    reconcile(rows,checked,reg)

    def test_wrong_parent_guarantee_or_borrower_rejected(self):
        for row_index,key,value in (
            (0,"recourse","Unconditional parent guarantee"),
            (1,"recourse","Non-recourse except for customary limited guarantees"),
            (0,"borrower","CoreWeave Financing DDTL V, LLC"),
            (1,"borrower","CoreWeave Compute Acquisition Co. VIII, LLC"),
        ):
            with self.subTest(row=row_index,key=key):
                rows, checked, reg = fixtures()
                rows[row_index][key] = value
                checked["coreweave_facilities"]["facilities"] = rows
                with self.assertRaisesRegex(ValueError,"borrower, recourse"):
                    reconcile(rows,checked,reg)

    def test_untrusted_sec_issuer_and_plus14_date_rejected(self):
        for key,value in (("available_at","2026-08-25"),
                          ("filed_at","2026-08-13"),
                          ("cik","1045810"),
                          ("form","8-K"),
                          ("accession","0001769628-26-000367")):
            with self.subTest(key=key):
                rows,checked,reg = fixtures()
                reg[key]=value
                with self.assertRaisesRegex(ValueError,"chronology"):
                    reconcile(rows,checked,reg)

    def test_review_or_pit_score_forgery_rejected(self):
        for group,key,value in (("top","node_score",67),
                                ("top","index_aics",505),
                                ("top","trades_created",True),
                                ("top","production_weights_changed",True),
                                ("core","as_of","2026-11-19"),
                                ("core","source","crwv_26_q1")):
            with self.subTest(key=key):
                rows,checked,reg=fixtures()
                target=checked if group=="top" else checked["coreweave_facilities"]
                target[key]=value
                with self.assertRaisesRegex(ValueError,"Research cross-check"):
                    reconcile(rows,checked,reg)

    def test_duplicate_facility_or_cross_issuer_is_not_double_counted(self):
        rows,checked,reg=fixtures()
        rows[1] = copy.deepcopy(rows[0])
        checked["coreweave_facilities"]["facilities"] = rows
        with self.assertRaisesRegex(ValueError,"Missing, duplicate"):
            reconcile(rows,checked,reg)


if __name__=="__main__":
    unittest.main()
