#!/usr/bin/env python3
"""Generate a fixed benchmark corpus. No prime occurrence data enter construction."""
from bridge_rank import best_bridge, motifs, combined
from pathlib import Path
import csv, json

ROOT = Path(__file__).resolve().parent

def produce(length=2, max_gap=96):
    ws = motifs(length)
    records=[]
    for i, a in enumerate(ws):
        for j,b in enumerate(ws):
            x=best_bridge(a,b,max_gap)
            if not x: continue
            for policy, field in [('shortest','shortest'),('max_series','best'),('void_adjusted','void_adjusted')]:
                bridge, score=x[field]
                records.append({'id':f'{length}-{i}-{j}-{policy}', 'pair':f'{length}-{i}-{j}',
                   'policy':policy, 'left':a,'right':b,'gap':bridge,'score':score,
                   'offsets':combined(a,b,bridge), 'ratio':x['ratio']})
    return records

if __name__=='__main__':
    records=produce()
    with (ROOT/'candidates.tsv').open('w') as f:
        for r in records:
            fields=[r['id'],r['pair'],r['policy'],str(len(r['offsets']))]
            fields += [str(x) for x in r['offsets']]
            f.write('\t'.join(fields)+'\n')
    (ROOT/'candidate_report.json').write_text(json.dumps({'num_patterns':len(records),
        'unique_pairs':len(records)//3,'window':96,
        'pairs_with_better_candidate':sum(r['ratio']>1 for r in records if r['policy']=='shortest'),
        'median_ratio':sorted(r['ratio'] for r in records if r['policy']=='shortest')[len(records)//6],
        'largest_ratio':max(r['ratio'] for r in records)},indent=2)+'\n')
    print('created',len(records),'candidate rows for',len(records)//3,'fixed motif pairs')