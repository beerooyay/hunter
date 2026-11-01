#!/usr/bin/env python3
"""Research-only candidate scoring; exact local modular facts, heuristic global prime likelihood."""
from functools import lru_cache
from itertools import product
from math import log, exp
from bridge_rank import primes_to, motifs, combined, offsets, admissible, exact_score

REF_X = 10_000_000
MAX_BRIDGE = 96

@lru_cache(maxsize=None)
def tail_ratio(k, B, cutoff=100_000):
    """Universal p>B conditional singular-series ratio factor for k -> k+1 tuple."""
    acc=0.0
    for p in primes_to(cutoff):
        if p>B:
            acc += log(p*(p-k-1)/((p-k)*(p-1)))
    return exp(acc)

@lru_cache(maxsize=None)
def conditional_ratio(H, b, B):
    """Hardy-Littlewood singular-series S(H+{b}) / S(H), approximate only in p>B tail.
    All pattern-sensitive factors up to global B are included exactly as rational factors.
    """
    k=len(H)
    a=1.0
    for p in primes_to(B):
        h=len({x%p for x in H})
        hh=len({x%p for x in H+(b,)})
        if h==p: raise ValueError('nonadmissible base H')
        if hh==p:return 0.0
        a *= ((p-hh)/(p-h)) * p/(p-1)
    return a*tail_ratio(k,B)

def forced_composite(H,b):
    """Small-prime p such that adding b fills all residues p: if all H values are prime >p,
    then n+b is necessarily composite. This is an unconditional logical fact.
    """
    for p in primes_to(len(H)+1):
        if len({x%p for x in H})<p and len({x%p for x in H+(b,)})==p:
            return p
    return None

def score(H,B,ref=REF_X):
    k=len(H)
    omitted=[b for b in range(1,H[-1]) if b not in H and b%2==0]
    mu=sum(conditional_ratio(H,b,B) for b in omitted)/log(ref)
    return log(exact_score(H,B))-mu, mu, sum(forced_composite(H,b) is not None for b in omitted),len(omitted)

def evaluate(max_bridge=MAX_BRIDGE):
    ws=motifs(2)
    B=max(offsets(a)[-1]+max_bridge+offsets(b)[-1] for a in ws for b in ws)
    rows=[];summary=[]
    for i,left in enumerate(ws):
        for j,right in enumerate(ws):
            options=[]
            for g in range(2,max_bridge+1,2):
                H=combined(left,right,g)
                if not admissible(H):continue
                val,mu,forced,nmissing=score(H,B)
                options.append((val,g,mu,forced,nmissing,H))
            if not options:continue
            best=max(options,key=lambda v:(v[0],-v[1]))
            pair=f'2-{i}-{j}'
            rows.append((f'{pair}-conditional',pair,'conditional',*best[-1]))
            summary.append({'pair':pair,'bridge':best[1],'mu':best[2], 'forced':best[3],'missing':best[4], 'scores_tested':len(options)})
    return rows,summary,B

if __name__=='__main__':
    import json, csv
    from pathlib import Path
    root=Path(__file__).resolve().parent
    rows,summary,B=evaluate()
    with (root/'conditional_candidates.tsv').open('w') as f:
        for id,pair,policy,*offs in rows:
            f.write('\t'.join(map(str,[id,pair,policy,len(offs),*offs]))+'\n')
    with (root/'conditional_selection.json').open('w') as f:
        json.dump({'B':B,'reference_x':REF_X,'candidate_count':len(rows),'rows':summary},f,indent=2)
    print({'B':B,'candidates':len(rows),'mean_forced_fraction':sum(r['forced'] for r in summary)/max(1,sum(r['missing'] for r in summary)), 'fully_forced':sum(r['forced']==r['missing'] for r in summary)})