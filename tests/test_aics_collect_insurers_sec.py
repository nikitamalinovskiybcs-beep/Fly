"""SEC PIT tests use arithmetic-only fixtures, never claimed market observations."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_collect_insurers_sec import (
    ISSUERS, COLUMNS, archive_payload, extract_candidates, recent_accessions,
    require_contact, retrieve_json, run, sec_url,
)

ASOF = dt.date(2026, 11, 18)
SEC_UA = "AICS Research named_contact@research-institute.org"
ACCESSION = "0001099219-26-000050"


def dummy_submission(cik="0001099219", accn=ACCESSION, filed="2026-08-01"):
    return {
        "cik": int(cik),
        "filings": {"recent": {
            "form": ["10-Q"], "accessionNumber": [accn],
            "filingDate": [filed], "primaryDocument": ["met-quarter.htm"]
        }}
    }


def dummy_fact(cik="0001099219", accn=ACCESSION, filed="2026-08-01",
               end="2026-06-30", value=100, start=None):
    row = {"accn": accn, "form": "10-Q", "filed": filed,
           "end": end, "val": value, "fy": 2026, "fp": "Q2"}
    if start is not None:
        row["start"] = start
    return {
        "cik": int(cik),
        "facts": {"us-gaap": {"Assets": {"units": {"USD": [row]}}}}
    }


class Response:
    def __init__(self, url, data):
        self.url = url
        self.headers = {"Content-Type": "application/json"}
        self.raw = json.dumps(data).encode()
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def geturl(self): return self.url
    def read(self, amount): return self.raw[:amount]


class TestInsurerSECPIT(unittest.TestCase):
    def test_fixed_universe(self):
        self.assertEqual(ISSUERS, {"MET": "0001099219", "PRU": "0001137774"})

    def test_source_allowlist_rejects_other_entity(self):
        with self.assertRaises(ValueError): sec_url("0000000000", "submissions")
        with self.assertRaises(ValueError): sec_url(ISSUERS["MET"], "anything")

    def test_requires_contact_without_fake_default(self):
        for ua in ("", "fake@example.com", "no-contact-here"):
            with self.assertRaises(ValueError): require_contact(ua)
        self.assertEqual(require_contact(SEC_UA), SEC_UA)

    def test_sec_14_day_lag_and_provenance(self):
        rows, stats = extract_candidates(
            "MET", dummy_fact(), dummy_submission(), ASOF, "facthash", "subhash"
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["filed_at"], "2026-08-01")
        self.assertEqual(rows[0]["available_at"], "2026-08-15")
        self.assertEqual(rows[0]["accession"], ACCESSION)
        self.assertEqual(rows[0]["value"], "100")
        self.assertEqual(rows[0]["pit_verified"], "false")
        self.assertEqual(rows[0]["score_eligible"], "false")
        self.assertEqual(rows[0]["candidate_node"], "Insurers")
        self.assertIn("000109921926000050/met-quarter.htm", rows[0]["sec_filing_url"])
        self.assertGreater(len(stats["missing_tags"]), 0)

    def test_no_future_sec_facts(self):
        s = dummy_submission(filed="2026-11-10")
        f = dummy_fact(filed="2026-11-10")
        rows, stats = extract_candidates("MET", f, s, ASOF, "f", "s")
        self.assertEqual(rows, [])
        self.assertEqual(stats["excluded"]["unavailable_sec_14d"], 1)

    def test_reject_duration_from_balance_sheet(self):
        f = dummy_fact(start="2026-04-01")
        rows, stats = extract_candidates("MET", f, dummy_submission(),
                                         ASOF, "f", "s")
        self.assertEqual(rows, [])
        self.assertEqual(stats["excluded"]["not_instant"], 1)

    def test_unmatched_accession_is_not_promoted(self):
        rows, stats = extract_candidates("MET", dummy_fact(),
                                         dummy_submission(accn="0001099219-26-000051"),
                                         ASOF, "f", "s")
        self.assertEqual(rows, [])
        self.assertEqual(stats["excluded"]["unmatched_accession"], 1)

    def test_reject_mismatched_issuer_cik(self):
        with self.assertRaises(ValueError):
            extract_candidates("MET", dummy_fact(cik="0001137774"),
                               dummy_submission(), ASOF, "f", "s")

    def test_retains_distinct_original_and_amended_accessions(self):
        accession2 = "0001099219-26-000060"
        sub = dummy_submission()
        recent = sub["filings"]["recent"]
        for key, entry in (
            ("form", "10-Q/A"), ("accessionNumber", accession2),
            ("filingDate", "2026-08-20"), ("primaryDocument", "met-amended.htm")
        ):
            recent[key].append(entry)
        facts = dummy_fact()
        vals = facts["facts"]["us-gaap"]["Assets"]["units"]["USD"]
        vals.append({"accn": accession2, "form": "10-Q/A", "filed": "2026-08-20",
                     "end": "2026-06-30", "val": 105})
        rows, _ = extract_candidates("MET", facts, sub, ASOF, "f", "s")
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["value"] for r in rows], ["100", "105"])
        self.assertEqual([r["available_at"] for r in rows],
                         ["2026-08-15", "2026-09-03"])

    def test_invalid_numeric_never_written(self):
        facts = dummy_fact(value=float("nan"))
        rows, stats = extract_candidates("MET", facts, dummy_submission(),
                                         ASOF, "f", "s")
        self.assertEqual(rows, [])
        self.assertEqual(stats["excluded"]["invalid_observation"], 1)

    def test_response_and_archive_byte_authenticity(self):
        raw = json.dumps(dummy_submission()).encode()
        def opener(req, timeout):
            self.assertEqual(timeout, 50)
            return Response(req.full_url, dummy_submission())
        returned, parsed = retrieve_json(sec_url(ISSUERS["MET"], "submissions"),
                                         SEC_UA, opener=opener)
        self.assertEqual(returned, raw)
        self.assertEqual(parsed["cik"], 1099219)
        with tempfile.TemporaryDirectory() as directory:
            sha, p = archive_payload(Path(directory), "MET", "submissions", raw)
            self.assertEqual(sha, hashlib.sha256(raw).hexdigest())
            self.assertEqual(Path(p).read_bytes(), raw)
            Path(p).write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                archive_payload(Path(directory), "MET", "submissions", raw)

    def test_end_to_end_never_certifies_numerical_index(self):
        def opener(req, timeout):
            if "submissions/" in req.full_url:
                cik = req.full_url.split("CIK")[1].split(".json")[0]
                if cik == ISSUERS["MET"]:
                    return Response(req.full_url, dummy_submission())
                return Response(req.full_url, {
                    **dummy_submission(cik=cik, accn="0001137774-26-000050"),
                    "filings": {"recent": {
                        "form": ["10-Q"],
                        "accessionNumber": ["0001137774-26-000050"],
                        "filingDate": ["2026-08-01"],
                        "primaryDocument": ["pru-quarter.htm"]
                    }}
                })
            cik = req.full_url.split("CIK")[1].split(".json")[0]
            return Response(req.full_url,
                            dummy_fact(cik=cik, accn=("0001099219-26-000050"
                                if cik == ISSUERS["MET"] else "0001137774-26-000050")))
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)
            result=run(p, ASOF, SEC_UA, opener=opener)
            self.assertEqual(result["successful_issuers"], 2)
            self.assertEqual(result["candidate_observations"], 2)
            self.assertIsNone(result["insurers_node_score"])
            self.assertIsNone(result["index_aics"])
            self.assertFalse(result["independently_verified_pit"])
            self.assertEqual(result["promotion"], "BLOCKED")
            report=json.loads((p/"manifest.json").read_text())
            self.assertEqual(report["candidate_observations"], 2)
            self.assertIn("current SEC companyfacts", " ".join(report["limitations"]).lower())


if __name__ == "__main__":
    unittest.main()
