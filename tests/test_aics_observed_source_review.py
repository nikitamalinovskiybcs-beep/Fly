"""Policies and real disclosure arithmetic for the frozen primary-source review."""

import copy
import hashlib
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from scripts.aics_audit_company_attachments import RECEIPT as ATTACHMENTS
from scripts.aics_audit_company_attachments import pdf_pages
from scripts.aics_observed_source_review import (
    FROZEN_DATE,
    REGISTRY,
    REPORT,
    SOURCES,
    captures,
    checked_original,
    dollars,
    source_documents,
)
from scripts.aics_reconcile_company_universe import (
    REGISTRY as COMPANIES,
)
from scripts.aics_reconcile_company_universe import (
    TELEGRAM_CLAIMS,
    telegram_membership,
)


class ObservedReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY.read_text())
        cls.report = json.loads(REPORT.read_text())
        cls.rows = cls.report["observations"]

    def test_source_lineage_and_scope(self):
        self.assertEqual(self.report["registry_sha256"], hashlib.sha256(REGISTRY.read_bytes()).hexdigest())
        self.assertEqual(set(self.registry["sources"]), SOURCES)
        self.assertEqual({k for x in self.rows.values() for k in x["sources"]}, SOURCES)
        for key, item in self.registry["sources"].items():
            if key != "fed_3344":
                filed = date.fromisoformat(item["filed_at"])
                available = date.fromisoformat(item["available_at"])
                self.assertEqual(available, filed + timedelta(days=14))
                self.assertLessEqual(available, FROZEN_DATE)
        self.assertFalse(self.report["independently_attested_historical_pit"])
        self.assertIsNone(self.report["index_aics"])

    def test_cutoff_and_embargo_before_reading_any_files(self):
        registry = copy.deepcopy(self.registry)
        with tempfile.TemporaryDirectory() as directory:
            registry["evidence_cutoff"] = "2026-11-19"
            with self.assertRaisesRegex(ValueError, "fixed information cutoff"):
                source_documents(registry, Path(directory), False)
            registry["evidence_cutoff"] = FROZEN_DATE.isoformat()
            first = next(iter(registry["sources"].values()))
            first["available_at"] = first["filed_at"]
            with patch("scripts.aics_observed_source_review.read_original") as reader:
                with self.assertRaisesRegex(ValueError, "availability"):
                    source_documents(registry, Path(directory), False)
                reader.assert_not_called()

    def test_hash_and_conflicting_disclosures_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            checked_original(b"altered", self.registry["sources"]["nscale"]["original"])
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            captures(r"amount ([0-9]+)", "amount 1 amount 2")

    def test_dimensions_units_and_duplicate_xbrl(self):
        # Parser fixtures exercise context identity only. They never enter the report.
        snippet = """<root xmlns:x="http://www.xbrl.org/2003/instance"
                           xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
            <x:context id="c"><x:entity><x:identifier>0001137774</x:identifier></x:entity>
              <x:period><x:instant>2026-09-30</x:instant></x:period></x:context>
            <x:unit id="u"><x:measure>iso4217:USD</x:measure></x:unit>
            <ix:nonFraction name="us-gaap:Assets" contextRef="c" unitRef="u" scale="6">771,378</ix:nonFraction>
            </root>"""
        args = ("us-gaap:Assets", "1137774", ("2026-09-30",))
        self.assertEqual(dollars(ET.fromstring(snippet), *args), Decimal(771378000000))
        for before, after in [
            ("</x:entity>", "<x:segment/></x:entity>"), ("iso4217:USD", "iso4217:EUR"),
            ("0001137774", "0001045810"), ("2026-09-30", "2026-06-30"),
            ("</root>", '<ix:nonFraction name="us-gaap:Assets" contextRef="c" unitRef="u">0</ix:nonFraction></root>'),
        ]:
            with self.subTest(change=after), self.assertRaisesRegex(ValueError, "Missing or conflicting"):
                dollars(ET.fromstring(snippet.replace(before, after)), *args)

    def test_disclosed_quantities_and_unknown_balances(self):
        loan = self.rows["nscale_nc_gpu_credit"]
        self.assertEqual(loan["fixed_commitment_usd"] + loan["floating_commitment_usd"], 1_200_000_000)
        self.assertEqual(loan["contractual_ceiling_usd"], 1_200_000_000)
        self.assertIsNone(loan["drawn_principal_from_this_agreement_usd"])
        capex = self.rows["microsoft_cash_capex"]
        self.assertEqual(capex["current_usd"] - capex["prior_usd"], capex["change_usd"])
        ar = self.rows["nvidia_net_receivables"]
        self.assertEqual(ar["current_usd"] - ar["prior_usd"], 22_349_000_000)
        nvda = self.rows["nvidia_guarantees"]
        self.assertEqual(Decimal(nvda["sb_energy_max_usd_bn"]) + Decimal(nvda["land_power_shell_max_usd_bn"]),
                         Decimal(nvda["total_max_gross_usd_bn"]))
        self.assertEqual(nvda["sb_energy_signed_month"], "2026-08")
        self.assertIsNone(nvda["drawn_or_paid_usd_bn"])
        self.assertIsNone(self.rows["oracle_company_wide_rpo"]["ai_specific_paid_revenue_usd"])
        self.assertEqual(self.rows["fed_naics_3344_utilization"]["change_within_release_pp"], "0.9")

    def test_all_37_company_references_trace_to_the_supplied_attachments(self):
        receipt = json.loads(ATTACHMENTS.read_text())
        companies = json.loads(COMPANIES.read_text())["companies"]
        self.assertEqual([c["name"] for c in companies], [r["name"] for r in receipt["companies"]])
        for company, checked in zip(companies, receipt["companies"], strict=True):
            if company["original_pdf_pages"]:
                self.assertEqual(company["original_pdf_pages"], checked["physical_pdf_pages"])
            else:
                self.assertEqual(company["telegram_image_ids"], checked["registered_transcription_images"])
        self.assertEqual(receipt["omi_company_page_references_matched"], 51)
        self.assertEqual(receipt["screenshot_hashes_matched_to_registry_and_zip_manifest"], 11)
        self.assertFalse(receipt["contractual_exposures_verified_by_attachments"])
        with self.assertRaisesRegex(ValueError, "Wrong edition"):
            pdf_pages(b"not the original PDF")

    def test_telegram_names_reconcile_without_expanding_the_company_roster(self):
        companies = json.loads(COMPANIES.read_text())["companies"]
        claims = json.loads(TELEGRAM_CLAIMS.read_text())
        match = telegram_membership(companies, claims)
        self.assertEqual((len(companies), match["transcript_names"], match["in_fixed_roster"]), (37, 23, 17))
        self.assertEqual(match["outside_fixed_roster"],
                         ["Blackstone", "Brookfield", "Macquarie", "Magnetar", "Synopsys", "Valor Equity"])
        claims["extracted_company_names"].append({"name": "Crusoe Energy"})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            telegram_membership(companies, claims)
