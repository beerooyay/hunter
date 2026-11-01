#!/usr/bin/env python3
"""Exact, finite singular-series comparisons for finite bridge choices.

For fixed |H|=k and maximum span <= B, the normalized singular series
of any two admissible tuples has exactly the ratio R_B(H1)/R_B(H2), where
R_B(H) = product_{p <= B} (p - |H mod p|).
This is NOT a theorem about occurrence of primes, which depends on conjectures.
"""
from functools import lru_cache
from itertools import product
from math import prod, log

@lru_cache(maxsize=None)
def primes_to(n):
    if n < 2: return ()
    sieve = bytearray(b'\x01') * (n+1)
    sieve[:2] = b'\x00\x00'
    for i in range(2, int(n**.5)+1):
        if sieve[i]: sieve[i*i:n+1:i]=b'\x00' * (((n-i*i)//i)+1)
    return tuple(i for i in range(2,n+1) if sieve[i])

def offsets(word):
    s=0; ans=[0]
    for x in word:
        if type(x)!=int or x<=0: raise ValueError('gaps must be positive integers')
        s+=x; ans.append(s)
    return tuple(ans)

def admissible(offs):
    if len(offs)!=len(set(offs)): return False
    return all(len({x%p for x in offs})<p for p in primes_to(len(offs)))

def combined(left, right, bridge):
    if type(bridge)!=int or bridge<=0: raise ValueError('positive bridge needed')
    return offsets(left+(bridge,)+right)

def exact_score(offs, bound):
    if offs[0]!=0 or offs[-1]>bound: raise ValueError('not inside bound')
    return prod(p-len({x%p for x in offs}) for p in primes_to(bound))

def pareto_frontier(candidates):
    """Discard candidates dominated in BOTH bridge length and exact series score.

    For objectives log(score) - bridge/T with T > 0, a dominated
    candidate cannot win. Input is (bridge, positive integer score).
    """
    out = []
    champion = 0
    for bridge, score in sorted(candidates):
        if score > champion:
            out.append((bridge, score))
            champion = score
    return tuple(out)


def best_bridge(left, right, max_gap, reference_n=10_000_000):
    if type(max_gap)!=int or max_gap<2:raise ValueError('max_gap must be >=2')
    if reference_n<=1:raise ValueError('reference_n must exceed 1')
    if any(g%2 for g in left+right):raise ValueError('this experiment requires even source gaps')
    a,b=offsets(left),offsets(right)
    if not admissible(a) or not admissible(b):raise ValueError('inadmissible source')
    B=a[-1]+max_gap+b[-1]
    valid=[]
    for g in range(2,max_gap+1,2):
        offs=combined(left,right,g)
        if admissible(offs):
            valid.append((g, exact_score(offs,B)))
    if not valid:return None
    shortest=valid[0]
    best=max(valid,key=lambda row:(row[1],-row[0]))
    # Simple independent-void heuristic for consecutive-prime motifs.
    # For fixed source words and k, only the inserted bridge length varies.
    # The expected number of unspecified primes in that extra span is
    # roughly bridge / log(reference_n). This is NOT a rigorous model.
    frontier=pareto_frontier(valid)
    adjusted=max(frontier,key=lambda row:(log(row[1])-row[0]/log(reference_n),-row[0]))
    return {'left':left,'right':right,'window':max_gap,'cutoff':B,
            'shortest':shortest,'best':best,'void_adjusted':adjusted,'count':len(valid),
            'pareto':frontier,'frontier_size':len(frontier),
            'improved':best[1]>shortest[1],
            'ratio':best[1]/shortest[1]}

def motifs(length,allowed=(2,4,6,8,10)):
    return tuple(w for w in product(allowed,repeat=length) if admissible(offsets(w)))

if __name__=='__main__':
    for n in (2,3):
        ws=motifs(n)
        reports=[best_bridge(a,b,96) for a in ws for b in ws]
        ranked=[r for r in reports if r]
        improved=[r for r in ranked if r['improved']]
        ratios=sorted(r['ratio'] for r in ranked)
        print({'n':n,'pairs':len(reports),'with_valid_bridge':len(ranked),
            'with_better_score':len(improved),'median_ratio':ratios[len(ratios)//2],
            'max_ratio':ratios[-1], 'best_example':max(improved,key=lambda r:r['ratio'])})