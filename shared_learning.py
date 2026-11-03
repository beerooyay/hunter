"""Exchange measured survivor evidence between searches with explicit domain gates."""
import json
import math
import re
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from calibration import atomic_json, fit, holdout

ROOT = Path(__file__).resolve().parent


def gain(rows, scale):
    return sum(e*math.log(scale)+(n-e)*(math.log1p(-scale*q)-math.log1p(-q))
               for q,n,e,h in rows if h)


def transfer(main, lab):
    """A common correction must improve heldout likelihood in BOTH domains."""
    pooled = fit(main+lab)
    scale = pooled['fitted_scale']
    gates = [sum(e for q,n,e,h in rows if not h)>=500 and
             sum(e for q,n,e,h in rows if h)>=100 and gain(rows,scale)>=2
             for rows in (main,lab)]
    return dict(scale=scale if all(gates) else 1., candidate=scale,
                main_gain=gain(main,scale), lab_gain=gain(lab,scale),
                main_ready=gates[0], lab_ready=gates[1], applied=all(gates))


def refresh(root=ROOT):
    root=Path(root);main=defaultdict(list);lab=defaultdict(list);bands={};seen=set()
    def band(key):
        return bands.setdefault(key,dict(tested=0,completed=0,best=0,
            tails={str(t):0 for t in (15,20,25,30,40,50)}))
    with (root/'gaps.tsv').open() as stream:
        for line in stream:
            try:
                f=line.rstrip('\n').split('\t');m=re.fullmatch(r'P(\d+)_d(\d+)_L1e9',f[0])
                if not m:continue
                p,d=map(int,m.groups());identity=(p,d,int(f[1]))
                if identity in seen:continue
                q=float(f[21] if len(f)>21 else f[18]);n=int(f[11]);e=int(int(f[7])>0)
                if not (0<q<.5 and n>=e and n>0):continue
                seen.add(identity);key=f'{p}:{d}'
                main[key].append((q,n,e,holdout(str(identity))))
                b=band(key);b['tested']+=1;b['completed']+=int(f[5]);merit=float(f[9]);b['best']=max(b['best'],merit)
                for t in b['tails']:b['tails'][t]+=int(merit>=int(t))
            except (ValueError,IndexError):continue
    dbpath=root/'learning/research.sqlite3'
    if dbpath.exists():
        with sqlite3.connect(f'file:{dbpath}?mode=ro',uri=True) as db:
            for p,d,m,q,nr,er,nl,el,h in db.execute('SELECT p,d,m,q,nr,er,nl,el,heldout FROM trials'):
                # Same center is not independent evidence if also tested by main.
                if (p,d,m) not in seen:lab[f'{p}:{d}'].append((q,nr+nl,er+el,bool(h)))
    keys=sorted(set(main)|set(lab));now=int(time.time())
    models={key:transfer(main[key],lab[key]) for key in keys}
    # Verified discoveries from either lane become the local comparison table.
    records={}
    for line in (root/'records.txt').read_text().splitlines():
        f=line.split()
        if len(f)>=2: records[int(f[0])]=float(f[1])
    verified={(f[0],f[2]) for line in (root/'VERIFIED.tsv').read_text().splitlines()
              if len(f:=line.split('\t'))>=4 and f[3]=='OK'}
    for line in (root/'FOUND.tsv').read_text().splitlines():
        f=line.split('\t')
        if len(f)>=3 and (f[0],f[2]) in verified:
            g=int(f[0]);records[g]=max(records.get(g,0),float(f[1]))
    if dbpath.exists():
        with sqlite3.connect(f'file:{dbpath}?mode=ro',uri=True) as db:
            for g,merit in db.execute('SELECT gap,merit FROM finds WHERE verified=1'):
                records[g]=max(records.get(g,0),merit)
    if len(records)>100000:
        temp=root/'learning/known-records.txt.tmp'
        temp.write_text(''.join(f'{g} {m:.8f}\n' for g,m in sorted(records.items())))
        temp.replace(root/'learning/known-records.txt')
    payload=dict(updated=now,expires=now+900,bands=bands,models=models,known_gap_sizes=len(records),
        note='Tail counts are observed lower bounds under the main stopping policy. Different exposure and sieve depths prevent raw cross-lane rate comparisons. Shared hazard corrections require heldout support in both domains.')
    atomic_json(root/'learning/shared.json',payload)
    temp=root/'learning/shared-scale.tsv.tmp'
    temp.write_text(''.join(f"{key.replace(':', ' ')} {now+900} {v['scale']:.12f}\n" for key,v in models.items()))
    temp.replace(root/'learning/shared-scale.tsv')
    return payload


def read(root=ROOT):
    try:
        value=json.loads((Path(root)/'learning/shared.json').read_text())
        return value if value.get('expires',0)>time.time() else {}
    except (OSError,ValueError):return {}


if __name__=='__main__':
    print(json.dumps(refresh(),indent=2))
