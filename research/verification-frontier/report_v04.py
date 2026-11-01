#!/usr/bin/env python3
"""Rebuild benchmark comparison from v0.3 CSVs (if present) + new v0.4 CSVs."""
from collections import defaultdict
import csv,json
from pathlib import Path
here=Path(__file__).resolve().parent
prev=here.parent/'bridge-frontier'
if not prev.exists():
    prev=here.parent/'frontier_audit/bridge/praetor_bridge_lab_v03'
if not prev.exists():
    prev=here
mapping=[('100k_4m','range_100k_4m.csv'),('4m_8m','range_4m_8m.csv'),('8m_12m','range_8m_12m.csv'),('12m_30m','range_12m_30m.csv')]
agg=defaultdict(lambda:defaultdict(int));perrange={}
for tag,old in mapping:
    new=here/f'conditional_{tag}.csv'
    oldfile=prev/old
    if not oldfile.exists():
        continue
    vals=defaultdict(lambda:defaultdict(int))
    for file in [oldfile,new]:
        for row in csv.DictReader(file.open()):
            p=row['policy']
            for key in ('tuples','consecutive'):
                vals[p][key]+=int(row[key]);agg[p][key]+=int(row[key])
    perrange[tag]={k:dict(v) for k,v in vals.items()}
result={'by_range':perrange,'total':{k:dict(v) for k,v in agg.items()},
        'note':'conditional scoring was not fitted on observed counts; not an independent primorial gap test. case overlaps preclude iid inference.'}
(here/'benchmark_summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result['total'],indent=2))