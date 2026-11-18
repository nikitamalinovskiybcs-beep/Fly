"""Offline tests: Numerai credentials must never enter AICS reports/logs."""
import datetime as dt
import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from scripts.aics_numerai_readonly_probe import (
    API_URL, QUERY, check_credentials, make_report,
)


class FakeHTTP:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, *_):
        return self.body


class TestReadOnlyNumeraiProbe(unittest.TestCase):
    credentials = {
        "NUMERAI_PUBLIC_ID": "never-print-public",
        "NUMERAI_SECRET_KEY": "never-print-secret",
    }

    def test_missing_both_or_one_fails_closed(self):
        for values in ({}, {"NUMERAI_PUBLIC_ID": "present"},
                       {"NUMERAI_SECRET_KEY": "present"},
                       {"NUMERAI_PUBLIC_ID": "", "NUMERAI_SECRET_KEY": "a"}):
            with self.subTest(values=list(values)):
                self.assertEqual(check_credentials(values), "MISSING_CREDENTIALS")

    def test_auth_header_and_minimal_graphql_query(self):
        called = []

        def transport(request, timeout):
            called.append((request, timeout))
            return FakeHTTP(b'{"data":{"account":{"id":"PRIVATE-ACCOUNT-ID"}}}')

        result = check_credentials(self.credentials, transport)
        self.assertEqual(result, "CONNECTED_READ_ONLY")
        self.assertEqual(len(called), 1)
        request, timeout = called[0]
        self.assertEqual(request.full_url, API_URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(timeout, 20)
        self.assertEqual(request.get_header("Authorization"),
                         "Token never-print-public$never-print-secret")
        self.assertEqual(json.loads(request.data)["query"], QUERY)
        self.assertNotIn("mutation", QUERY.lower())
        self.assertNotIn("wallet", QUERY.lower())
        self.assertNotIn("models", QUERY.lower())

    def test_report_contains_no_secret_account_or_model_data(self):
        report = make_report(
            "CONNECTED_READ_ONLY", dt.datetime(2026, 11, 18, tzinfo=dt.timezone.utc)
        )
        serialized = json.dumps(report)
        for forbidden in ("never-print-public", "never-print-secret", "PRIVATE-ACCOUNT-ID"):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(report["credentials_stored"])
        self.assertFalse(report["account_id_stored"])
        self.assertEqual(report["market_observations_archived"], 0)
        self.assertIsNone(report["aics_node_score"])
        self.assertIsNone(report["certified_aics"])
        self.assertEqual(report["aics_promotion"], "BLOCKED")
        self.assertFalse(report["historical_pit_vintage_attested"])

    def test_authorization_rejected_is_sanitized(self):
        def reject(_request, _timeout):
            raise urllib.error.HTTPError(
                API_URL, 401, "TOKEN never-print-secret", hdrs=None, fp=None
            )
        result = check_credentials(self.credentials, reject)
        self.assertEqual(result, "AUTHENTICATION_REJECTED")
        self.assertNotIn("never-print-secret", result)

    def test_graphql_error_does_not_leak_details(self):
        def graphql_error(*_args, **_kwargs):
            return FakeHTTP(b'{"errors":[{"message":"never-print-secret"}]}')
        self.assertEqual(
            check_credentials(self.credentials, graphql_error), "API_GRAPHQL_ERROR"
        )

    def test_unexpected_exception_is_sanitized(self):
        def failing(*_args, **_kwargs):
            raise RuntimeError("secret key was never-print-secret")
        result = check_credentials(self.credentials, failing)
        self.assertEqual(result, "CLIENT_ERROR")
        self.assertNotIn("never-print-secret", result)

    def test_invalid_or_missing_account_response_fails(self):
        for body in (b'not-json', b'{}', b'{"data":{}}',
                     b'{"data":{"account":null}}',
                     b'{"data":{"account":{"id":""}}}',
                     b'{"data":{"account":{"id":123}}}'):
            with self.subTest(body=body):
                def transport(*_args, **_kwargs):
                    return FakeHTTP(body)
                self.assertNotEqual(
                    check_credentials(self.credentials, transport),
                    "CONNECTED_READ_ONLY",
                )

    def test_network_failure_is_sanitized(self):
        def failing(*_args, **_kwargs):
            raise urllib.error.URLError("never-print-secret")
        self.assertEqual(
            check_credentials(self.credentials, failing), "NETWORK_ERROR"
        )


if __name__ == "__main__":
    unittest.main()
