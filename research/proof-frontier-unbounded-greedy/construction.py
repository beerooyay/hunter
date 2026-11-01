"""Constructive adversary for sequential greedy prime-pattern bridging.

Standard library only; the constructed tuples are admissible offset patterns,
NOT certified simultaneous occurrences among actual primes.
"""
from __future__ import annotations
import json
from math import gcd


def primes_up_to(n: int) -> list[int]:
    sieve = bytearray(b'\x01')*(n+1)
    sieve[:2] = b'\x00\x00'
    for p in range(2, int(n**0.5)+1):
        if sieve[p]:
            sieve[p*p:n+1:p] = b'\x00'*(((n-p*p)//p)+1)
    return [i for i in range(n+1) if sieve[i]]


def construct(p: int):
    if p < 13 or p%3 != 1 or p not in primes_up_to(p):
        raise ValueError('p must be a prime >= 13 with p ≡ 1 (mod 3)')
    N=3*p-2
    primes=primes_up_to(N)
    Q=1
    for q in primes:
        if q !=p: Q *= q
    inverse=pow(Q,-1,p)
    def motif(missing):
        used=set(range(p))-set(x%p for x in missing)
        assert 0 in used
        seq=[0]+[(r*inverse%p)*Q for r in used-{0}]+[p*Q]
        return tuple(sorted(seq))
    A=motif([1,7]);B=motif([-1,3]);C=motif([1])
    assert [len(A),len(B),len(C)] == [p-1,p-1,p]
    return (A,B,C),primes,Q


def materialize(patterns, bridges):
    if len(bridges)!=len(patterns)-1:raise ValueError('arity')
    delta=0;out=[]
    for i,pattern in enumerate(patterns):
        out.extend(delta+x for x in pattern)
        if i<len(bridges):delta+=max(pattern)+bridges[i]
    return tuple(sorted(out))


def verify_admissible(offsets, primes):
    return [q for q in primes if len({x%q for x in offsets})>=q]


def optimize(p):
    motifs,small,Q=construct(p)
    best1=next(g for g in range(2,2*p+7,2)
               if not verify_admissible(materialize(motifs[:2],(g,)),small))
    best2=next(g for g in range(2,2*p+7,2)
               if not verify_admissible(materialize(motifs,(best1,g)),small))
    # Verify a lower bound (4 is the only possible total below 6).
    assert verify_admissible(materialize(motifs,(2,2)),small)
    assert not verify_admissible(materialize(motifs,(4,2)),small)
    assert (best1,best2)==(2,2*p-2)
    return {
        'p':p,'pattern_sizes':[len(t) for t in motifs],
        'N':sum(map(len,motifs)), 'Q_digits':len(str(Q)),
        'greedy':[best1,best2], 'greedy_cost':best1+best2,
        'optimal':[4,2], 'optimal_cost':6,
        'approximation_ratio':f'{p}/3',
        'obstruction_2_2':verify_admissible(materialize(motifs,(2,2)),small),
        'all_offsets_even':all(x%2==0 for t in motifs for x in t),
        'p_residue_missing':[[r for r in range(p) if r not in {x%p for x in s}] for s in motifs],
    }


def main():
    ps=[13,19,31,37,43,61,67,73,97,103]
    results=[optimize(p) for p in ps]
    print(json.dumps(results,indent=2))
    return results

if __name__=='__main__':main()