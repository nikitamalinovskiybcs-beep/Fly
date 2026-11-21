#!/usr/bin/env python3
"""Research-only ARCC non-accrual monitor from transcribed issuer/SEC disclosures.

Only arithmetic after verifying metadata; input is NOT raw-source authenticated.
AICS and node scores are deliberately never produced.
"""
import argparse
import csv
import datetime as dt
import decimal
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

METRICS = frozenset({'nonaccrual_amortized_cost_pct','nonaccrual_fair_value_pct'})
FIELDS = ('entity','metric_id','period_end','filed_at','available_at','value_pct',
          'denominator','source_type','source_uri','raw_source_sha256',
          'verification_status','score_eligible')


def read_checked(path: Path, as_of: dt.date):
    """Fail closed on metadata, dates, duplicate periods, or unsafe certification."""
    with path.open(newline='',encoding='utf-8') as fh:
        reader=csv.DictReader(fh)
        if reader.fieldnames != list(FIELDS):
            raise ValueError('unexpected CSV schema')
        rows=list(reader)
    if not rows:
        raise ValueError('no observations')
    parsed=[]
    keys=set()
    for row in rows:
        if row['entity'] != 'ARCC' or row['metric_id'] not in METRICS:
            raise ValueError('unknown entity or metric')
        key=(row['entity'], row['metric_id'], row['period_end'])
        if key in keys:raise ValueError('duplicate entity-metric-period')
        keys.add(key)
        period=dt.date.fromisoformat(row['period_end'])
        filed=dt.date.fromisoformat(row['filed_at'])
        available=dt.date.fromisoformat(row['available_at'])
        if not period <= filed <= as_of or available != filed + dt.timedelta(days=14):
            raise ValueError('SEC PIT chronology or 14-day availability violation')
        if row['score_eligible'].lower()!='false':
            raise ValueError('manual research evidence cannot certify AICS')
        if row['raw_source_sha256']:
            # This importer has not independently inspected original payload bytes.
            raise ValueError('unexpected source hash in manual disclosure input')
        if row['verification_status'] != 'MANUAL_PRIMARY_SOURCE_REVIEW_NO_RAW_SHA':
            raise ValueError('unrecognized verification state')
        if row['source_type'] not in {'ISSUER_RELEASE_AND_SEC_10K','SEC_10Q_EXHIBIT_991'}:
            raise ValueError('unrecognized primary source type')
        u=urlparse(row['source_uri'])
        if u.scheme!='https' or u.hostname not in {'www.sec.gov','arcc.ares.com'}:
            raise ValueError('not a configured issuer or SEC primary URL')
        value=decimal.Decimal(row['value_pct'])
        if not value.is_finite() or not 0<=value<=100:raise ValueError('invalid rate')
        parsed.append({**row,'period_end_dt':period,'available_at_dt':available,'rate':value})
    # The two denominators must not be mixed or silently imputed.
    return sorted(parsed,key=lambda x:(x['metric_id'],x['period_end']))


def summarize(rows, as_of):
    eligible=[r for r in rows if r['available_at_dt']<=as_of]
    grouped=defaultdict(list)
    for r in eligible:grouped[r['metric_id']].append(r)
    stats={}
    for metric in sorted(METRICS):
        series=sorted(grouped[metric],key=lambda x:x['period_end_dt'])
        if not series:continue
        first,last=series[0],series[-1]
        delta=last['rate']-first['rate']
        stats[metric]={
            'period_count':len(series),'first_period':first['period_end'],
            'latest_period':last['period_end'],
            'first_value_pct':str(first['rate']),'latest_value_pct':str(last['rate']),
            'change_percentage_points':str(delta),
            'relative_change_pct':str((delta/first['rate']*100).quantize(decimal.Decimal('0.01'))) if first['rate'] else None,
            'sequential_quarter_changes_pp':[
                {'period_end':r['period_end'],'change_pp':str(r['rate']-series[i-1]['rate'])}
                for i,r in enumerate(series) if i>0],
        }
    return {'as_of':as_of.isoformat(),'label':'PRIMARY_ISSUER_DISCLOSURE_RESEARCH_ONLY',
            'observations_used':len(eligible),'issuer_count':1,
            'periods':sorted({r['period_end'] for r in eligible}),
            'metric_stats':stats,'source_raw_payloads_archived':False,
            'independently_verified_pit':False,'private_credit_node_score':None,
            'index_aics':None,'predictive_skill_score':None,'trading_signal':None,
            'notes':['Original source figures transcribed from issuer press releases/SEC exhibits; raw HTML could not be archived here.',
                     'PIT cutoff is based on issuer-described SEC filing date +14 calendar days.',
                     'Current period comparison is not a calibrated node stress score.',
                     'No values are backfilled to earlier historical evaluation dates.']}


def run(csv_path: Path,as_of,output: Path):
    cutoff=dt.date.fromisoformat(as_of)
    checked=read_checked(csv_path,cutoff)
    report=summarize(checked,cutoff)
    report['input_csv_sha256']=hashlib.sha256(csv_path.read_bytes()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('input_csv',type=Path)
    p.add_argument('--as-of',default='2026-11-18')
    p.add_argument('--output',type=Path,default=Path('aics_data/research_arcc_nonaccrual.json'))
    a=p.parse_args()
    r=run(a.input_csv,a.as_of,a.output)
    print(json.dumps({'observations_used':r['observations_used'],
                      'index_aics':None,'private_credit_node_score':None}))

if __name__=='__main__':main()
