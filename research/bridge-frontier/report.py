#!/usr/bin/env python3
"""Aggregate fixed-policy counts; overlap prevents naive IID significance tests."""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).parent
PARTS=[('100k_to_4m','range_100k_4m.csv'),('4m_to_8m','range_4m_8m.csv'),
       ('8m_to_12m','range_8m_12m.csv'),('12m_to_30m','range_12m_30m.csv')]
FIELDS=('tuples','consecutive')

def summarize(filename):
    totals=defaultdict(lambda:defaultdict(int))
    paired=defaultdict(dict)
    with (ROOT/filename).open() as fp:
        for row in csv.DictReader(fp):
            for field in FIELDS: totals[row['policy']][field]+=int(row[field])
            paired[row['pair']][row['policy']]=row
    best='void_adjusted'
    comparisons={}
    for other in ('shortest','max_series'):
        differences=[int(p[best]['consecutive'])-int(p[other]['consecutive']) for p in paired.values()]
        comparisons[f'{best}_vs_{other}']={
            'better':sum(d>0 for d in differences),'equal':sum(d==0 for d in differences),
            'worse':sum(d<0 for d in differences)}
    return {'policies':{key:dict(value) for key,value in totals.items()},
            'matched_pairs':len(paired),'per_pair_comparison':comparisons,
            'consecutive_uplift_vs_shortest':totals[best]['consecutive']/totals['shortest']['consecutive']-1}

if __name__=='__main__':
    parts={label:summarize(filename) for label,filename in PARTS}
    import collections
    aggregate=collections.defaultdict(lambda:collections.defaultdict(int))
    for result in parts.values():
        for policy, values in result['policies'].items():
            for key,value in values.items(): aggregate[policy][key]+=value
    summary={'notes':['counted prime starts from 100003 to 30000000 inclusive in disjoint ranges',
                      'motifs overlap across candidate patterns; aggregate counts are not independent Bernoulli samples',
                      'bridge policy chosen without examining occurrence data',
                      'consecutive means exactly the six prescribed prime locations in the interval',
                      'not evidence of advantage for 1700-digit primorial searches'],
             'by_range':parts,'total':{k:dict(v) for k,v in aggregate.items()}}
    (ROOT/'bench_report.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary['total'],indent=2))