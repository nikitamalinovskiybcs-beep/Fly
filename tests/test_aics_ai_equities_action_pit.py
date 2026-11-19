"""Synthetic-only tests of the AI Equities action provenance gate, never market input."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.aics_audit_ai_equities_action_pit import audit_action_registry
from scripts.aics_collect_ai_equities_prices import RESEARCH_SYMBOLS


def template():
    return {
        "schema_version":"aics-ai-equities-historical-action-evidence-v1",
        "node":"AI Equities",
        "research_symbols":list(RESEARCH_SYMBOLS),
        "mandatory_facets":["corporate_action_history","security_identity_history",
                            "historical_constituency"],
        "original_evidence_records":[],
        "all_absence_of_actions_assertions":False,
        "historical_membership_verified":False,
        "split_dividend_adjustment_pit_verified":False,
        "corporate_action_history_pit_verified":False,
        "independently_certified_pit":False,
        "node_stress_score":None,"index_aics":None,"predictive_skill_score":None,
        "promotion":"BLOCKED","trades_created":False,
    }


def doc_record(tmp, *, source="EXCHANGE_BULLETIN"):
    path = tmp / "aics_data/source_evidence/ai_equities_action_originals/receipt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = b'{"not_market_data":"test_only"}'
    path.write_bytes(body)
    record = {
        "symbol":"NVDA","facet":"corporate_action_history",
        "source":source,
        "url":"https://www.nasdaqtrader.com/content/marketRegulation/dailylist/2026-11-17.html",
        "published_at_utc":"2026-11-17T12:00:00Z",
        "retrieved_at_utc":"2026-11-18T12:00:00+00:00",
        "coverage_start":"2026-11-01",
        "coverage_end":"2026-11-17",
        "original_path":str(path.relative_to(tmp)),
        "sha256":hashlib.sha256(body).hexdigest(),"bytes":len(body),
        "historical_pit_attested":False,
        "independent_publication_release_attested":False,
        "licensed_for_model_use":False,
    }
    if source=="SEC_EDGAR":
        record["url"]="https://www.sec.gov/Archives/edgar/data/1045810/000123456726000001/filing.htm"
        record["filed_at"]="2026-11-01"
        record["available_at"]="2026-11-15"
    return record,path


def run(tmp, doc):
    registry=tmp/"registry.json"
    registry.write_text(json.dumps(doc),encoding="utf-8")
    with patch("scripts.aics_audit_ai_equities_action_pit.Path.cwd", return_value=tmp):
        return audit_action_registry(registry)


class TestActionsPIT(unittest.TestCase):
    def test_missing_sources_remain_21_blocked_facets(self):
        with tempfile.TemporaryDirectory() as d:
            x=run(Path(d),template())
            self.assertEqual(x["facets_missing_original_sources"],21)
            self.assertEqual(x["local_original_rehashes"],0)
            self.assertFalse(x["absence_of_event_proven"])
            self.assertFalse(x["membership_pit_verified"])
            self.assertIsNone(x["index_aics"])

    def test_original_document_hash_does_not_certify_pit(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d); row,_=doc_record(tmp)
            document=template();document["original_evidence_records"]=[row]
            x=run(tmp,document)
            self.assertEqual(x["source_facets_with_local_originals"],1)
            self.assertEqual(x["facets_missing_original_sources"],20)
            self.assertEqual(x["promotion"],"BLOCKED")

    def test_tampered_document_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,path=doc_record(tmp);path.write_bytes(b"tampered")
            document=template();document["original_evidence_records"]=[row]
            with self.assertRaisesRegex(ValueError,"Tampered"):
                run(tmp,document)

    def test_forged_historical_availability_and_event_absence_rejected(self):
        for key in ("independently_certified_pit","all_absence_of_actions_assertions",
                    "historical_membership_verified","corporate_action_history_pit_verified"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as d:
                document=template();document[key]=True
                with self.assertRaisesRegex(ValueError,"promotion"):
                    run(Path(d),document)

    def test_earlier_capture_than_release_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp)
            row["published_at_utc"]="2026-11-20T00:00:00Z"
            document=template();document["original_evidence_records"]=[row]
            with self.assertRaisesRegex(ValueError,"chronology"):
                run(tmp,document)

    def test_sec_plus_14_calendar_days_required(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp,source="SEC_EDGAR")
            row["available_at"]="2026-11-14"
            document=template();document["original_evidence_records"]=[row]
            with self.assertRaisesRegex(ValueError,"14-day"):
                run(tmp,document)

    def test_sec_original_matching_cik_is_still_not_pit(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp,source="SEC_EDGAR")
            document=template();document["original_evidence_records"]=[row]
            result=run(tmp,document)
            self.assertEqual(result["source_facets_with_local_originals"],1)
            self.assertFalse(result["historical_pit_verified"])
            self.assertFalse(result["score_eligible"])
            self.assertIsNone(result["index_aics"])

    def test_sec_cross_issuer_original_rejected_even_with_valid_hash(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp,source="SEC_EDGAR")
            # 789019 is Microsoft, not the NVDA row's CIK 1045810.
            row["url"]="https://www.sec.gov/Archives/edgar/data/789019/000123456726000001/filing.htm"
            document=template();document["original_evidence_records"]=[row]
            with self.assertRaisesRegex(ValueError,"issuer CIK"):
                run(tmp,document)

    def test_sec_noncanonical_accession_path_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp,source="SEC_EDGAR")
            row["url"]="https://www.sec.gov/Archives/edgar/data/1045810/123/filing.htm"
            document=template();document["original_evidence_records"]=[row]
            with self.assertRaisesRegex(ValueError,"accession-specific"):
                run(tmp,document)

    def test_sec_publication_before_filing_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp,source="SEC_EDGAR")
            row["published_at_utc"]="2026-10-31T23:59:00Z"
            document=template();document["original_evidence_records"]=[row]
            with self.assertRaisesRegex(ValueError,"predates filing"):
                run(tmp,document)

    def test_escapes_source_archive_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp)
            row["original_path"]="../escape.json"
            document=template();document["original_evidence_records"]=[row]
            with self.assertRaisesRegex(ValueError,"archive"):
                run(tmp,document)

    def test_duplicate_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp)
            document=template();document["original_evidence_records"]=[row,row]
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                run(tmp,document)

    def test_incomplete_research_roster_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            document=template();document["research_symbols"].remove("MU")
            with self.assertRaisesRegex(ValueError,"roster"):
                run(Path(d),document)

    def test_format_specification_is_not_evidence_of_an_action(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp,source="NASDAQ_DAILY_LIST_SPEC")
            document=template();document["original_evidence_records"]=[row]
            with self.assertRaisesRegex(ValueError,"Format specification"):
                run(tmp,document)

    def test_exchange_portals_are_not_dated_originals(self):
        for portal in ("https://www.nasdaqtrader.com/Trader.aspx?id=DailyListPD",
                       "https://www.nasdaq.com/products/data/equities/corporate-action-solutions",
                       "https://www.nyse.com/"):
            with self.subTest(portal=portal), tempfile.TemporaryDirectory() as d:
                tmp=Path(d);row,_=doc_record(tmp)
                row["url"]=portal
                document=template();document["original_evidence_records"]=[row]
                with self.assertRaisesRegex(ValueError,"portal"):
                    run(tmp,document)

    def test_sec_search_portal_is_not_an_archived_filing(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp,source="SEC_EDGAR")
            row["url"]="https://www.sec.gov/edgar/search/"
            document=template();document["original_evidence_records"]=[row]
            with self.assertRaisesRegex(ValueError,"accession-specific"):
                run(tmp,document)

    def test_mislabeled_sec_evidence_host_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp,source="SEC_EDGAR")
            row["url"]="https://www.nasdaq.com/Archives/edgar/data/1234567/000123456726000001/filing.htm"
            document=template();document["original_evidence_records"]=[row]
            with self.assertRaisesRegex(ValueError,"mislabeled"):
                run(tmp,document)

    def test_mislabeled_nasdaq_daily_list_host_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp,source="NASDAQ_DAILY_LIST")
            row["url"]="https://www.sec.gov/Archives/edgar/data/1234567/000123456726000001/filing.htm"
            document=template();document["original_evidence_records"]=[row]
            with self.assertRaisesRegex(ValueError,"mislabeled"):
                run(tmp,document)

    def test_nonprimary_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);row,_=doc_record(tmp)
            row["url"]="http://example.org/attack"
            document=template();document["original_evidence_records"]=[row]
            with self.assertRaisesRegex(ValueError,"HTTPS"):
                run(tmp,document)


if __name__ == "__main__":
    unittest.main()
