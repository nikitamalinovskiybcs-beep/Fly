"""Check durable 24 genuine source-derived Repo rates are internally coherent.

No fake source rows or stress-score promotion. Full original ZIP reconciliation
is performed in GitHub Actions by a separate workflow step.
"""
import datetime as dt
import json
import unittest
from decimal import Decimal
from pathlib import Path

DATA = Path("aics_data/research/repo_24_month_observed_research_2026-11-18.json")


class TestDurableObservedRepoPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(DATA.read_text(encoding="utf-8"))

    def test_exact_24_months_and_unchanged_fixed_research_label(self):
        rows = self.data["monthly_observations"]
        self.assertEqual(len(rows), 24)
        self.assertEqual(len({r["as_of"] for r in rows}), 24)
        self.assertEqual(rows[0]["as_of"], "2024-11-30")
        self.assertEqual(rows[-1]["as_of"], "2026-10-31")
        self.assertEqual(self.data["fixed_node"], "Repo")
        self.assertEqual(self.data["fixed_node_weight"], 100)
        self.assertEqual(self.data["synthetic_market_rows"], 0)
        self.assertIsNone(self.data["stress_score"])
        self.assertIsNone(self.data["index_aics"])
        self.assertEqual(self.data["promotion"], "BLOCKED")
        self.assertFalse(self.data["source_release_timestamp_pit_attested"])
        self.assertFalse(self.data["contemporaneous_alfred_snapshots_attested"])
        self.assertFalse(self.data["independent_24_month_oos"])

    def test_each_source_spread_is_exact_decimal_arithmetic(self):
        spreads = []
        for row in self.data["monthly_observations"]:
            self.assertLess(row["market_effective_date"], row["as_of"])
            self.assertLessEqual(
                (dt.date.fromisoformat(row["as_of"]) - dt.date.fromisoformat(
                    row["market_effective_date"])).days, 7
            )
            a = (Decimal(row["sofr_pct"]) - Decimal(row["iorb_pct"])) * 100
            b = (Decimal(row["sofr_pct"]) - Decimal(row["bgcr_pct"])) * 100
            self.assertEqual(a, Decimal(row["sofr_minus_iorb_bps"]))
            self.assertEqual(b, Decimal(row["sofr_minus_bgcr_bps"]))
            spreads.append(a)
        self.assertEqual(sum(spreads), Decimal("-7"))
        self.assertEqual(min(spreads), Decimal("-8"))
        self.assertEqual(max(spreads), Decimal("22"))
        self.assertEqual(sum(x <= 0 for x in spreads), 18)

    def test_requires_original_source_archive_hashes(self):
        hashes = self.data["raw_provider_archive_sha256"]
        self.assertEqual(set(hashes), {"nyfed", "alfred"})
        self.assertTrue(all(isinstance(s, str) and len(s) == 64 for s in hashes.values()))
        self.assertEqual(self.data["observed_months"], 24)
        self.assertEqual(self.data["missing_months"], 0)


if __name__ == "__main__":
    unittest.main()
