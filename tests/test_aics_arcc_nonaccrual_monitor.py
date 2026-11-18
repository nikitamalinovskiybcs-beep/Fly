"""Structural tests; synthetic modifications are unit test fixtures, never market series."""
import csv
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest

from scripts.aics_arcc_nonaccrual_monitor import read_checked,run
ROOT=Path(__file__).parent.parent
ORIGINAL=ROOT/'aics_data/research/arcc_primary_disclosures_2026-11-18.csv'

class TestARCCMonitor(unittest.TestCase):
    def test_four_quarters_real_disclosures(self):
        with tempfile.TemporaryDirectory() as d:
            r=run(ORIGINAL,'2026-11-18',Path(d)/'out.json')
        a=r['metric_stats']['nonaccrual_amortized_cost_pct']
        self.assertEqual(a['period_count'],4)
        self.assertEqual(a['latest_value_pct'],'2.4')
        self.assertEqual(a['change_percentage_points'],'0.6')
        self.assertEqual(r['index_aics'],None)
        self.assertFalse(r['independently_verified_pit'])

    def test_lagged_release_cutoff_not_backfilled(self):
        rows=read_checked(ORIGINAL,dt.date(2026,11,18))
        from scripts.aics_arcc_nonaccrual_monitor import summarize
        pre=summarize(rows,dt.date(2026,11,9))
        self.assertEqual(pre['metric_stats']['nonaccrual_amortized_cost_pct']['latest_period'],'2026-06-30')
        post=summarize(rows,dt.date(2026,11,10))
        self.assertEqual(post['metric_stats']['nonaccrual_amortized_cost_pct']['latest_period'],'2026-09-30')

    def mutate(self,edit):
        with ORIGINAL.open(newline='',encoding='utf-8') as fh:
            reader=csv.DictReader(fh);rows=list(reader);headers=reader.fieldnames
        edit(rows)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'modified.csv'
            with p.open('w',newline='',encoding='utf-8') as fh:
                w=csv.DictWriter(fh,fieldnames=headers);w.writeheader();w.writerows(rows)
            with self.assertRaises(ValueError):read_checked(p,dt.date(2026,11,18))

    def test_reject_short_sec_lag(self):self.mutate(lambda rows:rows[0].update(available_at='2026-02-05'))
    def test_reject_fabricated_source_hash(self):self.mutate(lambda rows:rows[0].update(raw_source_sha256='0'*64))
    def test_reject_autocertification(self):self.mutate(lambda rows:rows[0].update(score_eligible='true'))
    def test_reject_duplicate(self):
        self.mutate(lambda rows:rows.append(dict(rows[0])))
    def test_reject_future_filing(self):self.mutate(lambda rows:rows[0].update(filed_at='2026-12-01'))
    def test_reject_unrelated_source(self):self.mutate(lambda rows:rows[0].update(source_uri='https://example.com/news'))

if __name__=='__main__':unittest.main()
