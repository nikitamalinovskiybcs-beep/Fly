"""Offline only: synthetic parser fixtures are not insurer market observations."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import aics_insurers_pru_credit_asof as gate


def fixture_xml():
    contexts = [
        ('c7', '2026-09-30'), ('c8', '2025-12-31'),
    ]
    facts = [
        ('pru:Commercialmortgageandotherloans', '1100', '1000'),
        ('us-gaap:Assets', '10000', '9500'),
        ('us-gaap:FinancingReceivableAllowanceForCreditLosses', '11', '10'),
    ]
    parts = [
        '<root xmlns:x="http://www.xbrl.org/2003/instance" '
        'xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">',
        '<x:unit id="usd"><x:measure>iso4217:USD</x:measure></x:unit>',
    ]
    for context, date in contexts:
        parts.append(
            f'<x:context id="{context}"><x:entity>'
            '<x:identifier>0001137774</x:identifier></x:entity>'
            f'<x:period><x:instant>{date}</x:instant></x:period></x:context>')
    for tag, now, prior in facts:
        for context, value in [('c7', now), ('c8', prior)]:
            parts.append(
                f'<ix:nonFraction name="{tag}" contextRef="{context}" '
                f'unitRef="usd" scale="6">{value}</ix:nonFraction>')
    parts.append(
        '<div>Loans on non-accrual status that did not have a related '
        'allowance for credit losses were $ 21 million and $ 13 million '
        'as of September 30, 2026 and December 31, 2025, respectively</div>')
    parts.append('</root>')
    return ''.join(parts).encode()


class TestFrozenInsurersPRUAsOf(unittest.TestCase):
    def test_real_source_registry_and_unavailable_met_filing(self):
        pru, met = gate.safe_dates()
        self.assertEqual(pru["available_at"], "2026-11-18")
        self.assertEqual(pru["accession"], "0001137774-26-000221")
        self.assertEqual(met["accession"], "0001099219-26-000062")
        self.assertEqual(met["available_at"], "2026-11-20")
        self.assertFalse(met["eligible_at_frozen_cutoff"])
        self.assertIsNone(met["net_mortgage_loans_usd"])
        self.assertIsNone(met["credit_allowance_usd"])

    def test_frozen_date_guard_for_both_sides(self):
        for value in (dt.date(2026,11,18), dt.date(2026,11,20),
                      dt.date(2027,1,1)):
            with self.subTest(cutoff=value), self.assertRaisesRegex(ValueError,"only"):
                gate.safe_dates(value)

    def test_sec_lag_changed_or_filed_date_forgery_rejected(self):
        source = json.loads(gate.REGISTRY.read_text(encoding="utf-8"))
        for key,value in (("filed_at","2026-11-03"),("available_at","2026-11-17"),
                          ("cik","1099219"),("accession","0001137774-26-000222")):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temp:
                changed = copy.deepcopy(source)
                changed["sources"]["pru"][key] = value
                p=Path(temp)/"registry.json"
                p.write_text(json.dumps(changed))
                with patch.object(gate,"REGISTRY",p):
                    with self.assertRaisesRegex(ValueError,"PRU original"):
                        gate.safe_dates()

    def test_real_rootless_fixture_calculates_without_model_score(self):
        facts = gate.parse_pru_credit(fixture_xml())
        self.assertEqual(facts["loan_net_change_millions"],100)
        self.assertEqual(facts["loan_net_change_pct"],"10.00")
        self.assertEqual(facts["loan_pct_total_assets"]["2025-12-31"],"10.53")
        self.assertEqual(facts["loan_pct_total_assets"]["2026-09-30"],"11.00")
        self.assertEqual(facts["loan_credit_loss_allowance_millions"]["2026-09-30"],11)
        self.assertEqual(facts["allowance_over_net_loan_plus_allowance_pct_proxy"]["2026-09-30"],"0.99")
        self.assertEqual(facts["nonaccrual_no_related_allowance_change_millions"],8)
        self.assertEqual(facts["nonaccrual_no_related_allowance_change_pct"],"61.54")
        self.assertIsNone(facts["all_nonaccrual_loans_total_millions"])
        self.assertIsNone(facts["ai_related_loan_exposure_millions"])
        self.assertFalse(facts["naic_risk_classification_attested"])

    def test_conflicting_facts_invalid_issuer_and_untagged_nonaccrual_fail_closed(self):
        raw=fixture_xml()
        for altered in (
            raw.replace(b'0001137774',b'0001099219'),
            raw.replace(b'iso4217:USD',b'iso4217:EUR'),
            raw.replace(b'allowance for credit losses were',b'allowance not relevant'),
            raw.replace(b'<ix:nonFraction name="pru:Commercialmortgageandotherloans"',
                        b'<ix:nonFraction name="untrusted:ForgedLoanBalance"'),
        ):
            with self.subTest(altered=altered[:70]), self.assertRaises(ValueError):
                gate.parse_pru_credit(altered)

    def test_registry_primary_exact_sec_sha(self):
        pru, _ = gate.safe_dates()
        self.assertEqual(pru["original"]["bytes"],56_649_032)
        self.assertEqual(pru["original"]["sha256"],
                         "49947c62bc026ff11df94e2c157ac67c18a073c7ec2f4e87f95f7c1645d59b41")
        self.assertEqual(pru["document_text_sha256"],
                         "82e0dff4a16a095626ad12b4882f35a405041578d63aca98e2584cdaded08a81")
        self.assertEqual(pru["filed_at"],"2026-11-04")
        self.assertEqual(gate.MET_Q3["filed_at"],"2026-11-06")


if __name__=="__main__":
    unittest.main()
