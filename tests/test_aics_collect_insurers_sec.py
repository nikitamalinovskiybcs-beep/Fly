"""SEC PIT tests use arithmetic-only fixtures, never claimed market observations."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aics_verify_insurers_sec_evidence import verify_bundle

from scripts.aics_collect_insurers_sec import (
    ISSUERS, COLUMNS, archive_payload, extract_candidates, recent_accessions,
    require_contact, retrieve_json, run, sec_url,
    historical_submissions_url, history_page_names,
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
            self.assertIn("current sec companyfacts", " ".join(report["limitations"]).lower())
            integrity=verify_bundle(p,p)
            self.assertEqual(integrity["checked_issuers"],2)
            self.assertEqual(integrity["checked_files"],4)
            self.assertEqual(integrity["checked_candidate_rows"],2)
            self.assertIsNone(integrity["index_aics"])
            self.assertFalse(integrity["independently_verified_pit"])
            # A locally stored altered JSON must never pass evidence checking.
            victim=next((p/"raw").glob("met_submissions_*.json"))
            victim.write_bytes(b"tampered archival bytes")
            with self.assertRaises(ValueError):verify_bundle(p,p)



    def test_official_historical_index_filename_allowlist(self):
        name = "CIK0001099219-submissions-001.json"
        self.assertEqual(historical_submissions_url(ISSUERS["MET"], name),
                         "https://data.sec.gov/submissions/" + name)
        for bad in ("../../bad.json", "CIK0001137774-submissions-001.json",
                    "https://malicious.invalid/CIK0001099219-submissions-001.json",
                    "CIK0001099219-submissions-abc.json"):
            with self.assertRaises(ValueError):
                historical_submissions_url(ISSUERS["MET"], bad)

    def test_history_pages_respect_declared_research_window(self):
        sub = dummy_submission()
        sub["filings"]["files"] = [
            {"name": "CIK0001099219-submissions-001.json",
             "filingFrom": "2018-01-01", "filingTo": "2020-12-31"},
            {"name": "CIK0001099219-submissions-002.json",
             "filingFrom": "2009-01-01", "filingTo": "2010-12-31"}
        ]
        self.assertEqual(
            history_page_names(sub, ISSUERS["MET"], dt.date(2018, 1, 1), ASOF),
            ["CIK0001099219-submissions-001.json"]
        )
        self.assertEqual(
            history_page_names(sub, ISSUERS["MET"], dt.date(2021, 1, 1), ASOF),
            []
        )

    def test_historical_xbrl_accession_retained_with_appendix_sha(self):
        accession = "0001099219-19-000011"
        old_fact = dummy_fact(accn=accession, filed="2019-02-01",
                              end="2018-12-31")
        appendix = {
            "form": ["10-K"], "accessionNumber": [accession],
            "filingDate": ["2019-02-01"],
            "primaryDocument": ["met-2018.htm"]
        }
        old_fact["facts"]["us-gaap"]["Assets"]["units"]["USD"][0]["form"] = "10-K"
        rows, stats = extract_candidates(
            "MET", old_fact, dummy_submission(), ASOF,
            "companyfacts-sha", "main-submissions-sha",
            first_period=dt.date(2018, 1, 1),
            historical_pages=[(appendix, "historic-file-sha")]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["available_at"], "2019-02-15")
        self.assertEqual(rows[0]["accession_index_raw_sha256"],
                         "historic-file-sha")
        self.assertEqual(rows[0]["submissions_raw_sha256"],
                         "main-submissions-sha")
        self.assertEqual(rows[0]["score_eligible"], "false")

    def test_missing_historical_page_fails_issuer_closed(self):
        sub = dummy_submission()
        sub["filings"]["files"] = [{
            "name": "CIK0001099219-submissions-001.json",
            "filingFrom": "2018-01-01",
            "filingTo": "2025-12-31",
        }]
        def opener(req, timeout):
            if "CIK0001099219-submissions-001.json" in req.full_url:
                raise RuntimeError("SEC appendix unavailable")
            if "/submissions/" in req.full_url:
                cik = req.full_url.split("CIK")[1].split(".json")[0]
                if cik == ISSUERS["MET"]:
                    return Response(req.full_url, sub)
                return Response(req.full_url, dummy_submission(
                    cik=ISSUERS["PRU"],accn="0001137774-26-000050"
                ))
            cik = req.full_url.split("CIK")[1].split(".json")[0]
            return Response(req.full_url,
                            dummy_fact(cik=cik,
                                       accn=(ACCESSION if cik == ISSUERS["MET"]
                                       else "0001137774-26-000050")))
        with tempfile.TemporaryDirectory() as directory:
            result = run(Path(directory), ASOF, SEC_UA, opener=opener,
                         first_period=dt.date(2018, 1, 1))
        self.assertEqual(result["successful_issuers"], 1)
        met = next(x for x in result["issuers"] if x["issuer"] == "MET")
        self.assertEqual(met["status"], "collection_error")
        self.assertEqual(met["error"], "RuntimeError")
        self.assertFalse(result["independently_verified_pit"])
        self.assertIsNone(result["index_aics"])

    def test_historical_index_duplicate_filenames_rejected(self):
        sub = dummy_submission()
        row = {"name": "CIK0001099219-submissions-001.json",
               "filingFrom": "2018-01-01", "filingTo": "2020-01-01"}
        sub["filings"]["files"] = [row, dict(row)]
        with self.assertRaises(ValueError):
            history_page_names(sub, ISSUERS["MET"], dt.date(2018, 1, 1), ASOF)

    def test_conflicting_original_accession_never_accepted(self):
        appendix = {
            "form": ["10-Q"], "accessionNumber": [ACCESSION],
            "filingDate": ["2026-08-01"], "primaryDocument": ["different.htm"]
        }
        with self.assertRaises(ValueError):
            extract_candidates("MET", dummy_fact(), dummy_submission(), ASOF,
                               "facts", "main", historical_pages=[(appendix, "history")])

    def test_sec_historical_appendix_endpoint_no_redirect(self):
        url = historical_submissions_url(
            ISSUERS["MET"], "CIK0001099219-submissions-001.json")
        def opener(req, timeout):
            return Response(req.full_url, {
                "form": [], "accessionNumber": [],
                "filingDate": [], "primaryDocument": []
            })
        raw, decoded = retrieve_json(url, SEC_UA, opener=opener)
        self.assertEqual(decoded["form"], [])
        self.assertGreater(len(raw), 0)

if __name__ == "__main__":
    unittest.main()
