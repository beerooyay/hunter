"""Proof-frontier calculus: exact minimum bridge overhead plus obstruction receipts.

No assumption that admissible prime constellations ever occur as actual primes.
"""
from __future__ import annotations
import hashlib
import itertools
import json
from pathlib import Path
from math import prod


def primes_le(n):
    isprime = bytearray([1]) * (n + 1)
    isprime[:2] = b'\x00\x00'
    for p in range(2, int(n ** .5) + 1):
        if isprime[p]:
            isprime[p*p:n+1:p] = b'\x00' * ((n-p*p)//p + 1)
    return [p for p in range(2, n+1) if isprime[p]]


def adversary(p):
    if p < 13 or p % 3 != 1 or p not in primes_le(p):
        raise ValueError('p must be prime >=13, p=1 (mod 3)')
    N = 3*p-2
    Q = prod(q for q in primes_le(N) if q != p)
    inv = pow(Q, -1, p)
    def motif(missing):
        residues = set(range(p)) - {r % p for r in missing}
        return sorted([0, p*Q] + [(r*inv%p)*Q for r in residues-{0}])
    return [motif({1,7}),motif({-1,3}),motif({1})]


def motifs_from_words(words):
    return [[0]+list(itertools.accumulate(w)) for w in words]


def prepare(patterns):
    assert len(patterns)==3
    for a in patterns:
        assert a == sorted(set(a)) and a[0]==0 and all(x%2==0 and x>=0 for x in a)
    N=sum(map(len,patterns))
    primes=primes_le(N)
    masks=[tuple(frozenset(x%p for x in a) for a in patterns) for p in primes]
    return primes,masks


def obstruction(patterns,prepared,g,h):
    primes,masks=prepared
    a,b=patterns[0][-1],patterns[1][-1]
    for p,states in zip(primes,masks):
        sh1=(a+g)%p;sh2=(a+g+b+h)%p
        covered=states[0] | {(v+sh1)%p for v in states[1]} | {(v+sh2)%p for v in states[2]}
        if len(covered)==p:return p
    return None


def pair_obstruction(patterns,prepared,g):
    primes,masks=prepared
    a=patterns[0][-1]
    for p,states in zip(primes,masks):
        sh=(a+g)%p
        if len(states[0]|{(v+sh)%p for v in states[1]})==p:return p
    return None


def greedy(patterns,prepared,limit=10000):
    g=next((g for g in range(2,limit+1,2) if pair_obstruction(patterns,prepared,g) is None),None)
    if g is None:raise ValueError('no feasible first bridge in limit')
    h=next((h for h in range(2,limit+1,2) if obstruction(patterns,prepared,g,h) is None),None)
    if h is None:raise ValueError('no feasible second bridge in limit')
    return [g,h]


def exact_minimum(patterns,prepared,upper):
    for cost in range(4,upper+1,2):
        for g in range(2,cost-1,2):
            h=cost-g
            if obstruction(patterns,prepared,g,h) is None:return [g,h]
    raise ValueError('upper bound invalid')


def make_receipt(patterns,problem,limit=10000):
    prepared=prepare(patterns)
    bad=[q for q in prepared[0] if any(len({x%q for x in a})==q for a in patterns)]
    if bad:raise ValueError(f'not individually admissible: {bad}')
    baseline=greedy(patterns,prepared,limit)
    best=exact_minimum(patterns,prepared,sum(baseline))
    optimum=sum(best)
    rejected=[]
    for cost in range(4,optimum,2):
        for g in range(2,cost-1,2):
            h=cost-g
            q=obstruction(patterns,prepared,g,h)
            assert q is not None
            rejected.append({'g':g,'h':h,'modulus':q})
    root=hashlib.sha256(json.dumps(patterns,separators=(',',':')).encode()).hexdigest()
    receipt={'protocol':'pfc-certificate-v1','problem':problem,
             'pattern_sizes':list(map(len,patterns)), 'offsets_sha256':root,
             'greedy':{'bridges':baseline,'cost':sum(baseline)},
             'optimal':{'bridges':best,'cost':optimum},
             'excluded_cheaper':rejected,
             'scope':'prime-pattern admissibility only; not actual prime occurrences'}
    return receipt


def main():
    out=Path(__file__).parent
    cases=[]
    for p in [13,19,31,43,67,103]:
        patterns=adversary(p)
        r=make_receipt(patterns,{'kind':'crt-adversary','p':p},limit=2*p+10)
        cases.append(r)
    # Five heterogeneous non-adversarial examples with local/global mismatch.
    alphabet=[2,4,6,8,10]
    words=[(2,4),(4,6),(2,6),(6,2),(4,2)]
    for i,ws in enumerate([(words[0],words[0],words[1]),(words[2],words[1],words[3]),(words[4],words[3],words[2])]):
        r=make_receipt(motifs_from_words(ws),{'kind':'gap-words','words':ws})
        cases.append(r)
    (out/'certificates.json').write_text(json.dumps(cases,indent=2)+'\n')
    print(json.dumps([{'case':r['problem'],'greedy':r['greedy']['cost'],'optimal':r['optimal']['cost'],
                       'rejection_witnesses':len(r['excluded_cheaper'])} for r in cases],indent=2))

if __name__=='__main__':main()