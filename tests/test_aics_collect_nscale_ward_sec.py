"""Synthetic HTML parser fixtures; no fabricated financial research observations."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_collect_nscale_ward_sec import (
    AVAILABLE, DOCUMENTS, FIXED, FLOATING, LIMIT,
    SourceError, archive, fetch_original, validate_source, verify_archive,
)

AGENT = "AICS Research independent-contact@research-institute.org"
WARD = b"""<!DOCTYPE html><html><body>
CREDIT AGREEMENT dated as of August 27, 2026 by and among
Nscale Ward County Borrower SPV, LLC as borrower and
Nscale Ward County, LLC as affiliate guarantor.
The lenders provide Delayed Draw Loan Commitments
in an aggregate amount not in excess of $1,850,000,000.
</body></html>"""
NARRATIVE = b"""<!DOCTYPE html><html><body>
Nscale Ward County Borrower SPV, LLC.
The Ward County GPU Credit Agreement provides for delayed draw term loan
commitments in an aggregate principal amount up to $1.85 billion,
consisting of $630.0 million of fixed-rate commitments and $1.22 billion
of floating-rate commitments.
The Ward County GPU Facility is guaranteed by Nscale Ward County, LLC,
supported by limited guarantees from Nscale Limited.
</body></html>"""


def samples():
    return {"ward_ex10_23": WARD, "nscale_s1_narrative": NARRATIVE}


class MockResponse:
    def __init__(self, url, *, mime="text/html", redirect=None):
        self.target = redirect or url
        self.headers = {"Content-Type": mime}
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def geturl(self): return self.target
    def read(self, maximum): return WARD[:maximum]


class TestNscaleWardSEC(unittest.TestCase):
    def test_fixed_contractual_components_are_not_drawn_balances(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = archive(root, samples(), dt.date(2026, 11, 19))
            verify_archive(root, report)
            self.assertEqual(report["source_count"], 2)
            self.assertEqual(report["original_sec_html_rehashed_now"], 2)
            self.assertEqual(report["facility_commitment_ceiling_usd"], LIMIT)
            self.assertEqual(FIXED + FLOATING, LIMIT)
            self.assertEqual(report["distinct_two_facility_commitment_ceiling_sum_usd"], 3_050_000_000)
            self.assertIsNone(report["parent_guaranteed_amount_usd"])
            self.assertIsNone(report["actual_drawn_principal_usd"])
            self.assertIsNone(report["cross_facility_debt_sum_usd"])
            self.assertIsNone(report["spv_node_score"])
            self.assertIsNone(report["index_aics"])
            self.assertEqual(report["promotion"], "BLOCKED")

    def test_durable_independent_original_rehash_receipt_is_not_pit(self):
        p = Path("aics_data/research/nscale_ward_original_sec_independent_rehash_2026-11-19.json")
        record = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(record["source_run_id"], 44472197069)
        self.assertEqual(record["source_artifact_id"], 14505066061)
        self.assertEqual(record["zip_sha256"],
                         "784af25b39401b95700a91f0ac0047a2548f950e6d07b043ff07abbc1b5954b2")
        self.assertEqual(record["manifest_sha256"],
                         "287226cfd5d828858a21f48abc4c8e22dd8423d841f1dcbe77392b3f31570fff")
        self.assertEqual(
            [(row["source_id"],row["bytes"],row["sha256"]) for row in record["source_originals"]],
            [
              ("ward_ex10_23",2063726,
               "9f2c58438f85705ea9cd69180c38e2c54ddb3979ee8d47f03218464f7a298ba6"),
              ("nscale_s1_narrative",7958866,
               "82ca06374fb97f55f66e334679103e8153b9686a44a86dae425ab0bfc1074020"),
            ]
        )
        self.assertEqual(record["fixed_delayed_draw_commitment_usd"],630_000_000)
        self.assertEqual(record["floating_delayed_draw_commitment_usd"],1_220_000_000)
        self.assertEqual(record["facility_commitment_ceiling_usd"],1_850_000_000)
        self.assertEqual(record["distinct_two_facility_commitments_total_usd"],3_050_000_000)
        self.assertIsNone(record["drawn_principal_for_either_facility_usd"])
        self.assertIsNone(record["parent_guarantee_amount_usd"])
        self.assertIsNone(record["additive_economic_risk_usd"])
        self.assertFalse(record["independent_historical_provider_pit_attestation"])
        self.assertFalse(record["independently_certified_spv_node"])
        self.assertFalse(record["untouched_24_month_oos"])
        self.assertEqual(record["synthetic_historical_observations"],0)
        self.assertIsNone(record["spv_node_score"])
        self.assertIsNone(record["index_aics"])
        self.assertEqual(record["promotion"],"BLOCKED")

    def test_sec_embargo_exactly_fourteen_calendar_days(self):
        self.assertEqual(AVAILABLE.isoformat(), "2026-10-02")
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(SourceError, "SEC \\+14"):
                archive(Path(folder), samples(), dt.date(2026, 10, 1))
        with tempfile.TemporaryDirectory() as folder:
            x=archive(Path(folder), samples(), dt.date(2026, 10, 2))
            self.assertEqual(x["source_receipts"][0]["available_at"], "2026-10-02")

    def test_wrong_exhibit_or_contract_ceiling_is_not_evidence(self):
        for fragment in (b"Nscale Ward County Borrower SPV, LLC",
                         b"Nscale Ward County, LLC",
                         b"$1,850,000,000",
                         b"August 27, 2026"):
            with self.subTest(fragment=fragment):
                with self.assertRaises(SourceError):
                    validate_source("ward_ex10_23", WARD.replace(fragment,b"WRONG"))

    def test_narrative_fixed_float_and_parent_guarantee_required(self):
        for fragment in (b"$630.0 million", b"$1.22 billion",
                         b"limited guarantees from Nscale Limited"):
            with self.subTest(fragment=fragment):
                with self.assertRaises(SourceError):
                    validate_source("nscale_s1_narrative", NARRATIVE.replace(fragment,b"UNKNOWN"))

    def test_corrupted_local_original_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = archive(root, samples(), dt.date(2026, 11, 19))
            raw = Path(report["source_receipts"][0]["raw_path"])
            raw.write_bytes(raw.read_bytes().replace(b"$1,850,000,000",b"$1,850,000,001"))
            with self.assertRaises(SourceError):
                verify_archive(root, report)

    def test_receipt_sha_substitution_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = archive(root, samples(), dt.date(2026, 11, 19))
            report["source_receipts"][0]["sha256"] = "f"*64
            with self.assertRaisesRegex(SourceError, "receipt mismatch"):
                verify_archive(root, report)

    def test_timestamp_provenance_is_utc_offset_aware(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = archive(root, samples(), dt.date(2026, 11, 19))
            self.assertIn("retrieved_at_utc", report["source_receipts"][0])
            changed = copy.deepcopy(report)
            changed["source_receipts"][0]["retrieved_at_utc"] = "2026-09-20T00:00:00Z"
            with self.assertRaisesRegex(SourceError, "chronology"):
                verify_archive(root, changed)
            changed = copy.deepcopy(report)
            changed["source_receipts"][0]["retrieved_at_utc"] = "2026-11-19T06:24:00"
            with self.assertRaisesRegex(SourceError, "chronology"):
                verify_archive(root, changed)

    def test_filing_identity_and_lag_not_alterable_in_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = archive(root, samples(), dt.date(2026, 11, 19))
            for k,v in (("issuer_cik","0000000"),("accession","0001193125-26-395476"),
                        ("available_at","2026-09-19"),("filed_at","2026-09-17"),
                        ("archived_retrospectively",False)):
                with self.subTest(field=k):
                    changed = copy.deepcopy(report)
                    changed["source_receipts"][1][k] = v
                    with self.assertRaisesRegex(SourceError, "chronology|status"):
                        verify_archive(root, changed)

    def test_contact_required_url_and_redirect_fail_closed(self):
        url = DOCUMENTS["ward_ex10_23"]
        with self.assertRaises(SourceError):
            fetch_original(url, "not-a-contact")
        with self.assertRaises(SourceError):
            fetch_original("https://fake.invalid/contract.htm", AGENT)
        def redirected(req, timeout):
            return MockResponse(req.full_url, redirect="https://untrusted.example/contract")
        with self.assertRaisesRegex(SourceError, "redirect"):
            fetch_original(url, AGENT, opener=redirected)
        def bad_type(req, timeout):
            return MockResponse(req.full_url, mime="application/pdf")
        with self.assertRaisesRegex(SourceError, "not HTML"):
            fetch_original(url, AGENT, opener=bad_type)

    def test_manifest_cannot_promote_drawn_or_spv_score(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = archive(root, samples(), dt.date(2026, 11, 19))
            for field,value in (("index_aics",503),("spv_node_score",70),
                                ("actual_drawn_principal_usd",1_850_000_000),
                                ("parent_guaranteed_amount_usd",1_850_000_000),
                                ("effective_economic_recourse_usd",630_000_000),
                                ("cross_facility_debt_sum_usd",3_050_000_000),
                                ("distinct_two_facility_commitment_ceiling_sum_usd",3_800_000_000),
                                ("source_pit_independently_attested",True),
                                ("promotion","CERTIFIED")):
                with self.subTest(field=field):
                    changed = copy.deepcopy(report)
                    changed[field]=value
                    with self.assertRaises(SourceError):
                        verify_archive(root, changed)


if __name__ == "__main__":
    unittest.main()
