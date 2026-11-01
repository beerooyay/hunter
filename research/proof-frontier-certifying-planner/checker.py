"""Independent certificate checker. Does not import the solver or trust its results.

For each certificate it recomputes arithmetic from scratch, confirms feasibility,
re-enumerates all cheaper even bridge vectors, and validates every obstruction.
"""
from __future__ import annotations
import hashlib
import itertools
import json
import sys
from math import isqrt


def prime_list(n):
    return [k for k in range(2,n+1) if all(k%d for d in range(2,isqrt(k)+1))]


def reconstruct(spec):
    if spec['kind']=='gap-words':
        ans=[]
        for word in spec['words']:
            a=[0]
            for g in word:a.append(a[-1]+g)
            ans.append(a)
        return ans
    if spec['kind']=='crt-adversary':
        p=spec['p']
        if p<13 or p%3!=1 or p not in prime_list(p):raise ValueError('bad p')
        N=3*p-2
        Q=1
        for q in prime_list(N):
            if q!=p:Q*=q
        result=[]
        for missing in [{1,7},{p-1,3},{1}]:
            members=[0,p*Q]
            for t in range(1,p):
                if (t*Q)%p not in missing:members.append(t*Q)
            result.append(sorted(members))
        return result
    raise ValueError('unknown family')


def check_obstruction(patterns,g,h):
    n=sum(map(len,patterns))
    a,b=patterns[0][-1],patterns[1][-1]
    for p in prime_list(n):
        shifts=[0,a+g,a+g+b+h]
        seen=set()
        for motif,sh in zip(patterns,shifts):
            seen.update((x+sh)%p for x in motif)
        if len(seen)==p:return p
    return None


def check_pair(patterns,g):
    n=sum(map(len,patterns));shift=patterns[0][-1]+g
    for p in prime_list(n):
        residues={x%p for x in patterns[0]}
        residues.update((x+shift)%p for x in patterns[1])
        if len(residues)==p:return p
    return None


def check_receipt(receipt):
    if receipt['protocol']!='pfc-certificate-v1':raise ValueError('invalid protocol')
    a=reconstruct(receipt['problem'])
    if receipt['pattern_sizes'] != list(map(len,a)):raise ValueError('sizes')
    if hashlib.sha256(json.dumps(a,separators=(',',':')).encode()).hexdigest()!=receipt['offsets_sha256']:
        raise ValueError('motif digest')
    for s in a:
        if not s or s[0]!=0 or s!=sorted(set(s)) or any(x<0 or x%2 for x in s):raise ValueError('invalid motif')
    for p in prime_list(sum(map(len,a))):
        if any(len({x%p for x in s})>=p for s in a):raise ValueError('inadmissible input')
    for key in ['greedy','optimal']:
        bridges=receipt[key]['bridges']
        if len(bridges)!=2 or any(x<2 or x%2 for x in bridges):raise ValueError('bad bridges')
        if sum(bridges)!=receipt[key]['cost']:raise ValueError('wrong cost')
        if check_obstruction(a,*bridges) is not None:raise ValueError('candidate is obstructed')
    g,h=receipt['greedy']['bridges']
    if any(check_pair(a,i) is None for i in range(2,g,2)) or check_pair(a,g) is not None:
        raise ValueError('greedy first choice incorrect')
    if any(check_obstruction(a,g,i) is None for i in range(2,h,2)):
        raise ValueError('greedy second choice incorrect')
    best=receipt['optimal']['cost']
    expected={(x,cost-x) for cost in range(4,best,2) for x in range(2,cost-1,2)}
    actual={(x['g'],x['h']) for x in receipt['excluded_cheaper']}
    if actual!=expected or len(actual)!=len(receipt['excluded_cheaper']):raise ValueError('incomplete lower bound')
    for witness in receipt['excluded_cheaper']:
        p=check_obstruction(a,witness['g'],witness['h'])
        if p is None:raise ValueError('an alleged lower obstruction is feasible')
        # The given modulus itself must actually obstruct; not just *some* modulus.
        shifts=[0,a[0][-1]+witness['g'],a[0][-1]+witness['g']+a[1][-1]+witness['h']]
        seen={(x+sh)%witness['modulus'] for s,sh in zip(a,shifts) for x in s}
        if len(seen)!=witness['modulus'] or witness['modulus'] not in prime_list(sum(map(len,a))):
            raise ValueError('bad local modular witness')
    if receipt['scope'] != 'prime-pattern admissibility only; not actual prime occurrences':
        raise ValueError('scope altered')
    return True


def main():
    path=sys.argv[1] if len(sys.argv)>1 else 'certificates.json'
    with open(path) as f: receipts=json.load(f)
    for receipt in receipts:check_receipt(receipt)
    print('INDEPENDENT CERTIFICATE CHECK GREEN:',len(receipts),'cases')

if __name__=='__main__':main()