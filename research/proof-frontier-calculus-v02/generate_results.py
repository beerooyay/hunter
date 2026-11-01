#!/usr/bin/env python3
import json,subprocess, pathlib,sys
from certificates import bridge_receipt,path_receipt,verify_bridge_receipt,verify_path_receipt
from bridge_lab import words
DIR=pathlib.Path(__file__).resolve().parent

def run(*argv):return subprocess.check_output(argv,text=True).strip()

results=[]
for k in range(2,8):
    w=DIR/f'words_{k}.txt';bound=30030 if k>=6 else 2310
    w.write_text(''.join(' '.join(map(str,m))+'\n' for m in words(k)))
    lines=run(str(DIR/'independent_bridges'),str(k),str(w),str(bound)).splitlines()
    head=lines[0].split(); kv=dict(v.split('=') for v in head)
    extremizers=[line[11:].strip() for line in lines[1:] if line.startswith('extremizer:')]
    hist={int(a):int(b) for l in lines[1:] if not l.startswith('extremizer:') for a,b in [l.split()]}
    row={'k':k,'motifs':int(kv['motifs']),'ordered_pairs':int(kv['pairs']),'sharp_bridge':int(kv['best']),'extremizers':extremizers,'histogram':hist}
    assert sum(hist.values())==row['ordered_pairs']
    results.append(row)
    print(f'k={k}: {row["ordered_pairs"]} pairs, bound {row["sharp_bridge"]}',flush=True)
    if k>=5:
        diff=run(str(DIR/'difference_bridges'),str(k),str(w),str(bound)).splitlines()
        if [l for l in lines if not l.startswith('extremizer:')]!=diff:raise AssertionError('independent implementations disagreed '+str(k))

out={'two_way_survey':results,'three_way_survey':[]}
for k in (2,3):
    v=run(str(DIR/'three_way_full'),str(k),str(DIR/f'words_{k}.txt')).splitlines()
    head=v[0].split();record={head[i]:head[i+1] for i in range(0,len(head),2)}
    record['worst_motifs']=v[1];record['worst_bridges']=v[2]
    out['three_way_survey'].append(record)
    print('k3 blocks, source k=',k,':',record['global_better'],'globally improved',flush=True)

cert=bridge_receipt((6,10,8,10,2,4,8),(8,4,2,10,8,10,6))
path=path_receipt((2,4),(2,4),(4,6))
assert verify_bridge_receipt(cert) and verify_path_receipt(path)
(DIR/'sharp_k7_receipt.json').write_text(json.dumps(cert,indent=2)+'\n')
(DIR/'greedy_failure_receipt.json').write_text(json.dumps(path,indent=2)+'\n')
(DIR/'results.json').write_text(json.dumps(out,indent=2)+'\n')
print('all receipts and summaries generated')