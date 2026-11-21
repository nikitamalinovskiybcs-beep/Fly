"""Quarter and half-year columns from Nebius' June 2026 cash-flow statement."""
import unittest
from decimal import Decimal

from scripts.aics_neocloud_cash_coverage import column


class FinancingColumnsTest(unittest.TestCase):
    def test_reported_nil_in_quarter_with_positive_half_year(self):
        label = "Proceeds from issuance of convertible notes"
        table = [label + " 1,000.0 — 1,000.0 4,337.5"]
        self.assertEqual(column(table, label, 1, 4, reported_nil=True), Decimal(0))
        self.assertEqual(column(table, label, 3, 4, reported_nil=True), Decimal("4337.5"))
        with self.assertRaises(ValueError):
            column([], label, 1, 4, reported_nil=True)
