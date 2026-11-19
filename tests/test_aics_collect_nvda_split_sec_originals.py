"""Synthetic SEC submission fixtures validate provenance, not market observations."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import aics_collect_nvda_split_sec_originals as gate

CLOCK=dt.datetime(2026,11,19,9,0,tzinfo=dt.timezone.utc)


def fake_submission(item):
    if item["id"].endswith("20240522"):
        narrative = ("On May 22, 2024, the Company announced a "
                     "ten-for-one forward stock split. Each shareholder will receive "
                     "nine additional shares of common stock on June 7, 2024. "
                     "The record date is June 6, 2024 and trading begins June 10, 2024.")
    else:
        narrative = ("The ten-for-one forward stock split amendment "
                     "became effective at 4:01 p.m. Eastern Time on June 7, 2024. "
                     "Trading on a split-adjusted basis at market open on June 10, 2024.")
    head=("<SEC-DOCUMENT>research-parser-fixture\n"
          "<SEC-HEADER>\n"
          "ACCESSION NUMBER: " + item["accession"] + "\n"
          "CONFORMED SUBMISSION TYPE: 8-K\n"
          "CENTRAL INDEX KEY: 0001045810\n"
          "FILED AS OF DATE: " + item["filed_at"].replace("-","") + "\n"
          "</SEC-HEADER>\n")
    return (head + "<DOCUMENT>\n<TYPE>8-K\n"
            "<FILENAME>" + item["primary_filename"] +
            "\n<TEXT>\n<html><body>" + narrative +
            "</body></html>\n</TEXT>\n</DOCUMENT>").encode()


def fixtures_and_items():
    docs=[]
    for document in gate.DOCUMENTS:
        item={k:v for k,v in document.items() if not k.startswith("pinned_")}
        docs.append(item)
    originals={item["id"]: fake_submission(item) for item in docs}
    return tuple(docs),originals


class TestNVDASplitOriginalChronology(unittest.TestCase):
    def test_may_announcement_and_june_effectuation_are_distinct_events(self):
        docs,originals=fixtures_and_items()
        with patch.object(gate, "DOCUMENTS", docs), tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            data=gate.archive(root,originals,dt.date(2026,11,19),retrieved_at_utc=CLOCK)
            self.assertEqual(data["original_filings_rehashed"],2)
            self.assertEqual(data["announcement_sec_available_at"],"2024-06-05")
            self.assertEqual(data["effectuation_sec_available_at"],"2024-06-21")
            self.assertEqual(data["split_effective_date"],"2024-06-07")
            self.assertEqual(data["first_expected_split_basis_market_session"],"2024-06-10")
            self.assertEqual([s["accession"] for s in data["source_records"]],
                             ["0001045810-24-000113","0001045810-24-000144"])
            self.assertEqual(gate.verify_archive(root)["split_new_for_old"],[10,1])
            self.assertFalse(data["historical_constituency_attested"])
            self.assertFalse(data["independent_historical_release_time_attested"])
            self.assertIsNone(data["index_aics"])

    def test_immutable_june_8k_hash_rejects_valid_semantic_fake(self):
        expected=gate.DOCUMENTS[1]
        raw=fake_submission(expected)
        with self.assertRaisesRegex(ValueError,"independent receipt"):
            gate.verify_sec_original(raw, expected)

    def test_cross_issuer_accession_form_and_filing_date_rejected(self):
        item=gate.DOCUMENTS[0]
        raw=fake_submission(item)
        for before,after in (
            (b"0001045810",b"0007890190"),
            (b"CONFORMED SUBMISSION TYPE: 8-K",b"CONFORMED SUBMISSION TYPE: 10-Q"),
            (b"FILED AS OF DATE: 20240522",b"FILED AS OF DATE: 20240523"),
        ):
            with self.subTest(before=before):
                changed=raw.replace(before,after)
                with self.assertRaisesRegex(ValueError,"mismatch"):
                    gate.verify_sec_original(changed,item)

    def test_missing_company_event_or_wrong_primary_document_blocked(self):
        item=gate.DOCUMENTS[0]
        raw=fake_submission(item)
        for before,after in (
            (b"ten-for-one forward stock split",b"two-for-one reverse split"),
            (b"nine additional shares",b"two additional shares"),
            (item["primary_filename"].encode(),b"unrelated.htm"),
            (b"<TYPE>8-K",b"<TYPE>EX-99.1"),
        ):
            with self.subTest(before=before):
                with self.assertRaises(ValueError):
                    gate.verify_sec_original(raw.replace(before,after),item)

    def test_missing_first_filing_or_pre_pit_cutoff_blocked(self):
        docs,originals=fixtures_and_items()
        with patch.object(gate,"DOCUMENTS",docs), tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,"Incomplete"):
                gate.archive(Path(folder),{docs[1]["id"]:originals[docs[1]["id"]]},
                             dt.date(2026,11,19),retrieved_at_utc=CLOCK)
            with self.assertRaisesRegex(ValueError,"embargo"):
                gate.archive(Path(folder),originals,dt.date(2024,6,20),
                             retrieved_at_utc=CLOCK)
            with self.assertRaisesRegex(ValueError,"embargo"):
                gate.archive(Path(folder),originals,dt.date(2024,6,4),
                             retrieved_at_utc=CLOCK)

    def test_self_rehashed_manifest_cannot_promote_price_history(self):
        docs,originals=fixtures_and_items()
        with patch.object(gate,"DOCUMENTS",docs), tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            m=gate.archive(root,originals,dt.date(2026,11,19),retrieved_at_utc=CLOCK)
            original=(root/"manifest.json").read_bytes()
            for key,value in (
                ("historical_constituency_attested",True),
                ("historical_adjustment_factors_pit_attested",True),
                ("independent_historical_release_time_attested",True),
                ("node_stress_score",63),
                ("index_aics",503),
                ("announcement_sec_available_at","2024-05-22"),
            ):
                with self.subTest(key=key):
                    altered=copy.deepcopy(m);altered[key]=value
                    (root/"manifest.json").write_text(json.dumps(altered))
                    with self.assertRaisesRegex(ValueError,"promotion"):
                        gate.verify_archive(root)
            (root/"manifest.json").write_bytes(original)
            m["source_records"][1]["sha256"]="f"*64
            (root/"manifest.json").write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,"receipt mismatch"):
                gate.verify_archive(root)

    def test_fetch_requires_real_contact_and_no_redirect(self):
        item=gate.DOCUMENTS[0]
        with self.assertRaisesRegex(ValueError,"contact"):
            gate.fetch_source(item,"fake@example.com")
        with self.assertRaisesRegex(ValueError,"Unexpected"):
            gate.fetch_source({"id":"unknown"},"Research Person research@university.org")


if __name__=="__main__":
    unittest.main()
