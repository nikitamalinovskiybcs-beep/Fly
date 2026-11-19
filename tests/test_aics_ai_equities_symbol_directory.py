"""Offline-only exchange directory tests, using fictitious fixture tickers/rows."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.aics_collect_ai_equities_symbol_directory import (
    BASE, FILENAMES, RESEARCH_SYMBOLS, parse_directory, build_manifest, audit_directory
)

CLOCK=dt.datetime(2026,11,18,23,0,tzinfo=dt.timezone.utc)


def make_directory(filename):
    head = ("Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares"
            if filename=="nasdaqlisted.txt"
            else "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol")
    entries=[]
    for symbol in ("NVDA","MSFT","GOOGL","AMZN","META","MU") if filename=="nasdaqlisted.txt" else ("ORCL",):
        if filename=="nasdaqlisted.txt":
            entries.append(f"{symbol}|FICTIONAL {symbol} Common Stock|Q|N|N|100|N|N")
        else:
            entries.append(f"{symbol}|FICTIONAL {symbol} Common Stock|N|{symbol}|N|100|N|{symbol}")
    for i in range(101):
        symbol=f"ZZX{i:04}"
        if filename=="nasdaqlisted.txt":
            entries.append(f"{symbol}|TEST FIXTURE {symbol}|Q|N|N|100|N|N")
        else:
            entries.append(f"{symbol}|TEST FIXTURE {symbol}|N|{symbol}|N|100|N|{symbol}")
    footer = "File Creation Time: 1118202618:01|" + "|" * (len(head.split("|"))-2)
    return ("\n".join([head,*entries,footer])+"\n").encode()


def fixtures(url):
    return make_directory(url.rsplit("/",1)[-1])


class TestDirectoryCapture(unittest.TestCase):
    def setup_capture(self, root):
        original=build_manifest(root,clock=lambda:CLOCK,fetcher=fixtures)
        (root/"manifest.json").write_text(json.dumps(original),encoding="utf-8")
        return original

    def test_official_seven_synthetic_only_directory_fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            result=self.setup_capture(root)
            self.assertEqual(result["files_archived"],2)
            self.assertEqual(result["securities_observed"],7)
            self.assertEqual([x["symbol"] for x in result["observed_securities"]],
                             list(RESEARCH_SYMBOLS))
            self.assertFalse(result["historical_basket_membership_attested"])
            rehash=audit_directory(root)
            self.assertEqual(rehash["files_original_bytes_rehashed"],2)
            self.assertFalse(rehash["historical_pit_attested"])
            self.assertIsNone(rehash["index_aics"])

    def test_current_nasdaq_originals_external_rehash_receipt_not_historical(self):
        p=Path("aics_data/research/ai_equities_2026_11_19_nasdaq_current_directory_rehash.json")
        x=json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(x["github_workflow_run_id"],44496860842)
        self.assertEqual(x["github_artifact_id"],14516045430)
        self.assertEqual(x["downloaded_zip_sha256"],
                         "4df22b44e845a036801ad36702e86b90f0e6e7233533c4f80a5732850dae5a55")
        self.assertTrue(x["zip_crc_check_passed"])
        self.assertEqual(x["original_source_bytes_rehashed_independently_outside_actions"],2)
        sources=x["original_directories"]
        self.assertEqual([r["filename"] for r in sources], list(FILENAMES))
        self.assertEqual([(r["bytes"],r["sha256"]) for r in sources], [
            (348385,"5cda84ca84660408ecfcda5af7e8f8e8c5a519e754f33ad5a96d17f86e708b83"),
            (544575,"3cc52144bcd516be7dad8b668d91b84ff6b56751d5fdf78d74c6e08284d69234")])
        self.assertEqual([r["symbol"] for r in x["current_research_securities"]],list(RESEARCH_SYMBOLS))
        self.assertEqual(sum(r["directory"]=="nasdaqlisted.txt"
                             for r in x["current_research_securities"]),6)
        self.assertEqual(sum(r["directory"]=="otherlisted.txt"
                             for r in x["current_research_securities"]),1)
        self.assertFalse(x["historical_security_identity_attested"])
        self.assertFalse(x["historical_basket_constituency_attested"])
        self.assertFalse(x["original_file_generation_time_is_verified_utc"])
        self.assertFalse(x["provider_license_approved"])
        self.assertEqual(x["new_project_milestones_credited"],0)
        self.assertEqual(x["aics_total_technical_milestones_completed"],22)
        self.assertIsNone(x["node_stress_score"])
        self.assertIsNone(x["index_aics"])
        self.assertEqual(x["promotion"],"BLOCKED")

    def test_raw_bytes_modified_after_capture_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);m=self.setup_capture(root)
            p=Path(m["original_files"][0]["original_path"])
            p.write_bytes(p.read_bytes()+b"TAMPER")
            with self.assertRaisesRegex(ValueError,"SHA256"):
                audit_directory(root)

    def test_relabel_directory_as_historical_pit_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);m=self.setup_capture(root)
            m["historical_basket_membership_attested"]=True
            (root/"manifest.json").write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,"promotion"):
                audit_directory(root)

    def test_changed_symbol_market_status_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);m=self.setup_capture(root)
            m["observed_securities"][0]["market_code"]="NYSE"
            (root/"manifest.json").write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,"relabeled"):
                audit_directory(root)

    def test_missing_or_duplicate_symbol_fails(self):
        orig=make_directory("nasdaqlisted.txt")
        with self.assertRaisesRegex(ValueError,"duplicate"):
            parse_directory(orig.replace(b"\nFile Creation Time:",b"\n"+orig.splitlines()[1]+b"\nFile Creation Time:"),"nasdaqlisted.txt")
        no_msft=orig.replace(b"MSFT|FICTIONAL MSFT Common Stock|Q|N|N|100|N|N\n",b"")
        with tempfile.TemporaryDirectory() as temp:
            def fetch(url):
                return no_msft if url.endswith("nasdaqlisted.txt") else fixtures(url)
            with self.assertRaisesRegex(ValueError,"missing"):
                build_manifest(Path(temp),clock=lambda:CLOCK,fetcher=fetch)

    def test_missing_footer_and_truncated_file_fail_closed(self):
        raw=make_directory("nasdaqlisted.txt")
        with self.assertRaisesRegex(ValueError,"creation"):
            parse_directory(raw.rsplit(b"\n",2)[0]+b"\n","nasdaqlisted.txt")
        with self.assertRaisesRegex(ValueError,"lacks"):
            parse_directory((raw.splitlines()[0]+b"\n"+raw.splitlines()[-1]+b"\n"),
                            "nasdaqlisted.txt")

    def test_stale_file_creation_timestamp_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            def stale(url):
                return fixtures(url).replace(b"1118202618:01",b"1010202618:01")
            with self.assertRaisesRegex(ValueError,"Stale"):
                build_manifest(Path(temp),clock=lambda:CLOCK,fetcher=stale)

    def test_symbol_roster_does_not_generate_aics_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);m=self.setup_capture(root)
            for key in ("index_aics","node_stress_score","predictive_skill_score"):
                self.assertIsNone(m[key])
            self.assertFalse(m["historical_security_identity_attested"])
            self.assertFalse(m["corporate_action_pit_attested"])
            self.assertEqual(m["promotion"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
