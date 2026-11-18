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
