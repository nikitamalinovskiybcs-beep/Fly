"""Offline synthetic parser tests; no fixtures enter the AICS market evidence archive."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.aics_collect_public_chain_sec_filings import CIKS, collect, audit, interpret

CLOCK = dt.datetime(2026,11,18,23,0,tzinfo=dt.timezone.utc)
ASOF = CLOCK.date()

def example(url, _):
    symbol = next(t for t,cik in CIKS.items() if f"CIK{cik}" in url)
    body = {
        "cik":int(CIKS[symbol]),"tickers":[symbol],
        "filings":{"recent":{
            "form":["8-K","10-Q","8-K"],
            "filingDate":["2026-10-15","2026-11-12","2023-01-01"],
            "accessionNumber":["0000000001-26-000001","0000000001-26-000002","0000000001-23-000003"],
            "primaryDocument":["eightk.htm","tenq.htm","older.htm"],
            "items":["1.01,9.01","","8.01"]
        }}
    }
    return json.dumps(body).encode()


def staged(root):
    data=collect(root,as_of=ASOF,contact="AICS Research audit@example.org",
                 fetcher=example,clock=lambda:CLOCK)
    return data


class TestPublicChainSEC(unittest.TestCase):
    def test_nine_originals_and_real_date_lag_logic(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            x=staged(root)
            self.assertEqual(len(CIKS),9)
            self.assertEqual(x["raw_original_issuers"],9)
            for row in x["issuers"]:
                self.assertEqual(row["candidate_filings_eligible_sec_14d"],1)
                self.assertEqual(row["excluded_due_sec_14d"],1)
                self.assertEqual(row["possible_8k_item_review_count"],1)
                self.assertFalse(row["eligible_filing_metadata"][0]["actual_corporate_action_verified"])
            report=audit(root)
            self.assertEqual(report["original_sec_issuers_rehashed"],9)
            self.assertEqual(report["sec_14d_eligible_filing_metadata_records"],9)
            self.assertFalse(report["historical_pit_attested"])
            self.assertIsNone(report["index_aics"])

    def test_tampered_sec_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);x=staged(root)
            p=Path(x["issuers"][0]["raw_path"])
            p.write_bytes(p.read_bytes()+b" ")
            with self.assertRaisesRegex(ValueError,"SHA"):
                audit(root)

    def test_malformed_original_issuer_identity_rejected(self):
        raw=example("https://data.sec.gov/submissions/CIK0001045810.json",None)
        obj=json.loads(raw);obj["tickers"]=["OTHER"]
        with self.assertRaisesRegex(ValueError,"identity"):
            interpret(json.dumps(obj).encode(),"NVDA",ASOF)
        obj=json.loads(raw);obj["cik"]=23
        with self.assertRaisesRegex(ValueError,"CIK"):
            interpret(json.dumps(obj).encode(),"NVDA",ASOF)

    def test_missing_issuer_cannot_be_passed_as_full_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);x=staged(root)
            x["issuers"]=x["issuers"][:-1]
            (root/"manifest.json").write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError,"roster"):
                audit(root)

    def test_forged_pit_and_score_claims_rejected(self):
        for key,value in [("historical_sec_vintages_attested",True),("index_aics",451),
                          ("sec_8k_item_hint_is_action_proof",True)]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temp:
                root=Path(temp);x=staged(root);x[key]=value
                (root/"manifest.json").write_text(json.dumps(x))
                with self.assertRaisesRegex(ValueError,"promoted"):
                    audit(root)

    def test_synthetic_future_filing_not_used_as_research_history(self):
        x=json.loads(example("https://data.sec.gov/submissions/CIK0001045810.json",None))
        x["filings"]["recent"]["filingDate"][0]="2026-11-20"
        q=interpret(json.dumps(x).encode(),"NVDA",ASOF)
        self.assertEqual(q["candidate_filings_eligible_sec_14d"],0)

    def test_future_backdating_and_clock_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,"future"):
                collect(Path(temp),as_of=dt.date(2026,11,19),
                        contact="AICS Research audit@example.org",
                        fetcher=example,clock=lambda:CLOCK)

    def test_source_metadata_cannot_relabel_8k_as_verified_action(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);x=staged(root)
            x["issuers"][0]["eligible_filing_metadata"][0]["actual_corporate_action_verified"]=True
            (root/"manifest.json").write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError,"disagrees"):
                audit(root)

if __name__=="__main__":
    unittest.main()
