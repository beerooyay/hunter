#!/usr/bin/env python3
"""Praetor Proof Frontier v0.2: proof-carrying append-only *research registry*.

No distributed consensus, monetary tokens, Lean kernel attestation, or secure PoW.
Proof-invariant statement/block identity; proof artifacts are detached and content-addressed.
Integer primality deterministic only for [2,2^64), via published 7-base MR set.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

VERSION = 'praetor.frontier.v0.2'
MAX64 = 2**64
MAX_GAP = 10_000
MAX_SIEVE = 1_000
MAX_TASKS = 256
BASES = (2, 325, 9375, 28178, 450775, 9780504, 1795265022)
SMALL = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)


def valid_int(n, lo=0, hi=None):
    return type(n) is int and n >= lo and (hi is None or n <= hi)


def canonical(obj):
    return json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def H(obj):
    return sha(canonical(obj))


def is_prime64(n):
    if not valid_int(n, 2, MAX64 - 1):
        return False
    for p in SMALL:
        if n % p == 0:
            return n == p
    d = n - 1
    s = 0
    while not d & 1:
        d >>= 1
        s += 1
    for a in BASES:
        a %= n
        if a == 0:
            continue
        x = pow(a, d, n)
        if x in (1, n-1):
            continue
        for _ in range(s-1):
            x = x*x % n
            if x == n-1:
                break
        else:
            return False
    return True


def sieve_divisors(limit):
    # Divisors need not be prime for soundness, but primes make the certificate compact.
    if not valid_int(limit, 2, MAX_SIEVE):
        raise ValueError('sieve_limit out of bounds')
    sieve = bytearray(b'\x01')*(limit+1)
    sieve[0:2] = b'\x00\x00'
    for p in range(2, math.isqrt(limit)+1):
        if sieve[p]:
            sieve[p*p:limit+1:p] = b'\x00' * len(sieve[p*p:limit+1:p])
    return [p for p in range(2,limit+1) if sieve[p]]


def covered_interior(p, q, limit):
    cover = bytearray(q-p-1)
    for d in sieve_divisors(limit):
        first = (p+1 + d-1)//d*d
        for n in range(first,q,d):
            if n != d:
                cover[n-p-1] = 1
    return cover


def least_factor(n):
    if n % 2 == 0:
        return 2
    for k in range(3, math.isqrt(n)+1, 2):
        if n % k == 0:
            return k
    raise ValueError('encountered interior prime; endpoints not consecutive')


def statement(p, q):
    if not (valid_int(p,2,MAX64-1) and valid_int(q,3,MAX64-1) and p<q and q-p<=MAX_GAP):
        raise ValueError('statement out of bounds')
    return f'prime-gap:{p}:{q}'


def make_certificate(p, q, sieve_limit=31):
    statement(p,q)
    if not (is_prime64(p) and is_prime64(q)):
        raise ValueError('composite endpoint')
    cover = covered_interior(p,q,sieve_limit)
    residuals=[]
    for i, hit in enumerate(cover):
        if not hit:
            n=p+1+i
            residuals.append([n,least_factor(n)])
    result={'type':'gap-cover-v1','p':p,'q':q,'sieve_limit':sieve_limit,'residuals':residuals}
    check_certificate(result)
    return result


def check_certificate(c, prime_cache=None):
    if type(c) is not dict or set(c) != {'type','p','q','sieve_limit','residuals'} or c['type']!='gap-cover-v1':
        raise ValueError('invalid certificate shape')
    p,q = c['p'],c['q']
    statement(p,q)
    for x in (p, q):
        if prime_cache is None or x not in prime_cache:
            if not is_prime64(x):
                raise ValueError('endpoint not certified prime in supported 64-bit domain')
    cover=covered_interior(p,q,c['sieve_limit'])
    expected=[n for n in range(p+1,q) if not cover[n-p-1]]
    r=c['residuals']
    if type(r) is not list or len(r)!=len(expected):
        raise ValueError('missing/extra residual witnesses')
    for n,row in zip(expected,r):
        if type(row) is not list or len(row)!=2 or type(row[0]) is not int or type(row[1]) is not int:
            raise ValueError('malformed residual')
        x,d=row
        if n != x or not (1<d<n) or n%d:
            raise ValueError('invalid residual composite witness')
    if prime_cache is not None:
        prime_cache.update((p,q))  # only after the entire gap certificate has passed
    return {'key':statement(p,q),'gap':q-p,'covered':len(cover)-len(expected),'residuals':len(expected)}


def merkle_root(keys):
    # Domain-separated, deterministic sorted-set Merkle root; no claim of zero-knowledge.
    keys=sorted(keys)
    nodes=[bytes.fromhex(sha(b'\x00'+s.encode('ascii'))) for s in keys]
    if not nodes:
        return sha(b'frontier-empty-v02')
    while len(nodes)>1:
        if len(nodes)&1:
            nodes.append(nodes[-1])
        nodes=[hashlib.sha256(b'\x01'+nodes[i]+nodes[i+1]).digest() for i in range(0,len(nodes),2)]
    return nodes[0].hex()


def membership_proof(keys, key):
    keys=sorted(keys)
    if key not in keys:
        raise ValueError('not a member')
    pos=keys.index(key)
    nodes=[bytes.fromhex(sha(b'\x00'+s.encode('ascii'))) for s in keys]
    proof=[]
    while len(nodes)>1:
        if len(nodes)&1:
            nodes.append(nodes[-1])
        proof.append({'side': 'left' if pos&1 else 'right', 'hash':nodes[pos^1].hex()})
        nodes=[hashlib.sha256(b'\x01'+nodes[i]+nodes[i+1]).digest() for i in range(0,len(nodes),2)]
        pos//=2
    return proof


def verify_membership(root,key,proof):
    if type(root) is not str or type(key) is not str or type(proof) is not list:
        return False
    try:
        a=bytes.fromhex(sha(b'\x00'+key.encode('ascii')))
        for step in proof:
            if set(step)!={'side','hash'} or step['side'] not in ('left','right'):
                return False
            b=bytes.fromhex(step['hash'])
            if len(b)!=32:
                return False
            a=hashlib.sha256(b'\x01'+(b+a if step['side']=='left' else a+b)).digest()
        return a.hex()==root
    except (TypeError,ValueError):
        return False


def genesis(tasks):
    if type(tasks) is not list or not 1<=len(tasks)<=MAX_TASKS:
        raise ValueError('bad task manifest')
    normalized=[]
    for pair in tasks:
        if type(pair) is not list or len(pair)!=2:
            raise ValueError('task must be [p,q]')
        normalized.append(statement(*pair))
    if len(set(normalized))!=len(normalized):
        raise ValueError('duplicate tasks')
    return {'version':VERSION,'tasks':sorted(normalized),'genesis_id':H({'version':VERSION,'tasks':sorted(normalized)})}


def proof_cid(c):
    return sha(b'praetor-proof-v02\x00'+canonical(c))


def apply(block, proof, height, prev_id, accepted, tasks, prime_cache=None):
    if type(block) is not dict or set(block)!={'height','parent','key','knowledge_root','frontier_root','id'}:
        raise ValueError('invalid block')
    key=block['key']
    if type(key) is not str or key not in tasks or key in accepted:
        raise ValueError('replayed/unassigned claim')
    if type(block['height']) is not int or block['height']!=height or block['parent']!=prev_id:
        raise ValueError('parent/height mismatch')
    expected_id=H({k:v for k,v in block.items() if k!='id'})
    if block['id']!=expected_id:
        raise ValueError('header commitment mismatch')
    checked=check_certificate(proof, prime_cache)
    if checked['key']!=key:
        raise ValueError('proof statement mismatch')
    new=accepted|{key}
    if block['knowledge_root']!=merkle_root(new) or block['frontier_root']!=merkle_root(tasks-new):
        raise ValueError('knowledge/frontier root mismatch')
    return new


def build_block(gen, blocks, accepted, key, cert):
    height=len(blocks)+1
    parent=blocks[-1]['id'] if blocks else gen['genesis_id']
    new=accepted|{key}
    block={'height':height,'parent':parent,'key':key,'knowledge_root':merkle_root(new),
           'frontier_root':merkle_root(set(gen['tasks'])-new)}
    block['id']=H(block)
    apply(block,cert,height,parent,accepted,set(gen['tasks']))
    return block


def verify_chain(bundle, *, cache_primes=True):
    if type(bundle) is not dict or set(bundle)!={'genesis','blocks','proofs'}:
        raise ValueError('bad bundle shape')
    g=bundle['genesis']
    if type(g) is not dict or set(g)!={'version','tasks','genesis_id'} or g['version']!=VERSION:
        raise ValueError('bad genesis')
    # Recompute genesis from canonical task strings, preventing injected tasks.
    keys=g['tasks']
    if type(keys) is not list or not keys or len(keys)>MAX_TASKS or keys!=sorted(set(keys)):
        raise ValueError('bad ordered task registry')
    for key in keys:
        if type(key) is not str or not key.startswith('prime-gap:') or len(key)>65:
            raise ValueError('invalid task')
        try:
            p,q=map(int,key.split(':')[1:])
        except (ValueError,TypeError):
            raise ValueError('invalid task key')
        if key!=statement(p,q):
            raise ValueError('noncanonical task key')
    if g['genesis_id']!=H({'version':VERSION,'tasks':keys}):
        raise ValueError('bad genesis commitment')
    tasks=set(keys)
    if type(bundle['blocks']) is not list or type(bundle['proofs']) is not dict:
        raise ValueError('bad ledger fields')
    if len(bundle['blocks'])>len(tasks):
        raise ValueError('too many blocks')
    accepted=set()
    prime_cache=set() if cache_primes else None
    parent=g['genesis_id']
    for height,row in enumerate(bundle['blocks'],1):
        if type(row) is not dict or set(row)!={'header','proof_cid'} or type(row['proof_cid']) is not str:
            raise ValueError('bad block envelope')
        if row['proof_cid'] not in bundle['proofs']:
            raise ValueError('missing proof object')
        cert=bundle['proofs'][row['proof_cid']]
        if row['proof_cid']!=proof_cid(cert):
            raise ValueError('content address mismatch')
        accepted=apply(row['header'],cert,height,parent,accepted,tasks,prime_cache)
        parent=row['header']['id']
    return {'blocks':len(bundle['blocks']),'verified_gaps':len(accepted),
            'unique_cached_prime_endpoints':len(prime_cache) if prime_cache is not None else None,
            'remaining':len(tasks-accepted),'knowledge_root':merkle_root(accepted),
            'frontier_root':merkle_root(tasks-accepted),'tip':parent}


def add_gap(bundle,p,q,limit=31):
    verify_chain(bundle)
    cert=make_certificate(p,q,limit)
    key=statement(p,q)
    accepted={row['header']['key'] for row in bundle['blocks']}
    if key in accepted:
        raise ValueError('duplicate accepted gap')
    b=build_block(bundle['genesis'],[row['header'] for row in bundle['blocks']],accepted,key,cert)
    cid=proof_cid(cert)
    bundle['proofs'][cid]=cert
    bundle['blocks'].append({'header':b,'proof_cid':cid})
    verify_chain(bundle)
    return b


def new_bundle(tasks):
    b={'genesis':genesis(tasks),'blocks':[],'proofs':{}}
    verify_chain(b)
    return b


def consecutive_gaps(start,n):
    if not valid_int(start,2,10**10) or not valid_int(n,1,MAX_TASKS):
        raise ValueError('bad demo parameters')
    x=start
    while not is_prime64(x):
        x+=1
    result=[]
    for _ in range(n):
        y=x+1
        while not is_prime64(y):
            y+=1
        result.append([x,y])
        x=y
    return result


def demo(path,n=30,start=1_000_000):
    tasks=consecutive_gaps(start,n)
    bundle=new_bundle(tasks)
    for p,q in tasks:
        add_gap(bundle,p,q,31)
    Path(path).write_text(json.dumps(bundle,indent=2,sort_keys=True)+'\n')
    result=verify_chain(bundle)
    result['artifact']=str(path)
    result['certificate_bytes']=sum(len(canonical(v)) for v in bundle['proofs'].values())
    result['block_bytes']=sum(len(canonical(v)) for v in bundle['blocks'])
    return result


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    sub=cli.add_subparsers(dest='mode',required=True)
    a=sub.add_parser('demo');a.add_argument('--blocks',type=int,default=30);a.add_argument('--start',type=int,default=1_000_000);a.add_argument('--output',default='chain_v02.json')
    a=sub.add_parser('verify');a.add_argument('bundle')
    a=sub.add_parser('membership');a.add_argument('bundle');a.add_argument('key')
    args=cli.parse_args()
    if args.mode=='demo':
        result=demo(args.output,args.blocks,args.start)
    else:
        bundle=json.loads(Path(args.bundle).read_text())
        result=verify_chain(bundle)
        if args.mode=='membership':
            keys=[r['header']['key'] for r in bundle['blocks']]
            proof=membership_proof(keys,args.key)
            result={'root':merkle_root(keys),'key':args.key,'proof':proof,'valid':verify_membership(merkle_root(keys),args.key,proof)}
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()