#!/usr/bin/env python3
"""Praetor proof frontier v0.3: order-invariant, deterministic epochs of verified finite arithmetic facts.

This is a toy mathematical registry, NOT permissionless consensus, a cryptocurrency,
or a Lean-checked library. Certificates use deterministic 64-bit arithmetic.
"""
from __future__ import annotations
import argparse
import copy
import json
import random
import sqlite3
from pathlib import Path

from legacy_v02 import (canonical, sha, H, statement, make_certificate, check_certificate,
                        proof_cid, merkle_root, membership_proof, verify_membership,
                        consecutive_gaps, valid_int)

VERSION = "praetor.frontier.v0.3"
MAX_TASKS = 2000
MAX_EPOCH = 128


def manifest(tasks, epoch_size):
    if type(tasks) is not list or not 1 <= len(tasks) <= MAX_TASKS:
        raise ValueError("invalid manifest task count")
    if not valid_int(epoch_size, 1, MAX_EPOCH):
        raise ValueError("invalid epoch size")
    keys = []
    for pair in tasks:
        if type(pair) is not list or len(pair) != 2:
            raise ValueError("task not [p,q]")
        keys.append(statement(*pair))
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate tasks")
    keys.sort()
    base = {"version": VERSION, "keys": keys, "epoch_size": epoch_size}
    return {**base, "id": H({"kind": "pfrontier-manifest-v03", **base})}


def check_manifest(m):
    if type(m) is not dict or set(m) != {"version", "keys", "epoch_size", "id"}:
        raise ValueError("bad manifest fields")
    if m["version"] != VERSION or not valid_int(m["epoch_size"], 1, MAX_EPOCH):
        raise ValueError("unsupported manifest")
    keys=m["keys"]
    if type(keys) is not list or not 1<=len(keys)<=MAX_TASKS or keys != sorted(set(keys)):
        raise ValueError("noncanonical or repeated tasks")
    pairs=[]
    for k in keys:
        if type(k) is not str or not k.startswith("prime-gap:"):
            raise ValueError("bad task key")
        parts=k.split(":")
        if len(parts)!=3:
            raise ValueError("bad task key")
        try:
            p, q = int(parts[1]), int(parts[2])
        except ValueError as e:
            raise ValueError("bad task integers") from e
        if statement(p,q)!=k:
            raise ValueError("noncanonical key")
        pairs.append([p,q])
    if manifest(pairs, m["epoch_size"]) != m:
        raise ValueError("manifest digest mismatch")
    return True


def epoch_keys(m, number):
    size=m["epoch_size"]
    if not valid_int(number, 1, (len(m["keys"])+size-1)//size):
        raise ValueError("bad epoch number")
    return m["keys"][(number-1)*size:number*size]


def header_for(m, epoch, parent):
    """Identity is a function of fixed manifest + epoch number + accumulated set,
    never of submission order, witness choice, wall-clock time, nonce or miner ID.
    """
    if type(parent) is not str or len(parent)!=64:
        raise ValueError("bad parent")
    a=epoch*m["epoch_size"]
    completed=m["keys"][:a]
    remaining=m["keys"][a:]
    h={"version":VERSION,"manifest_id":m["id"],"epoch":epoch,
       "parent":parent,"claims":epoch_keys(m,epoch),
       "knowledge_root":merkle_root(completed),"frontier_root":merkle_root(remaining)}
    h["id"]=H({"kind":"pfrontier-epoch-v03","header":h})
    return h


def new_bundle(tasks, epoch_size=8):
    b={"manifest":manifest(tasks,epoch_size), "epochs":[], "bindings":{}, "proofs":{}}
    verify_bundle(b)
    return b


def submit(b, certificate):
    """Arbitrary arrival order accepted. Sealing uses canonical tasks.
    The certificate is checked even when its statement has been checked before.
    """
    if type(b) is not dict or set(b)!={"manifest","epochs","bindings","proofs"}:
        raise ValueError("bad bundle")
    check_manifest(b["manifest"])
    checked=check_certificate(certificate)
    k=checked["key"]
    if k not in b["manifest"]["keys"]:
        raise ValueError("unassigned mathematical fact")
    cid=proof_cid(certificate)
    if k in b["bindings"]:
        # Alternative valid proof allowed, but keep the lexicographically smallest CID.
        # This rule is *not* cryptographic finality: evidence is not consensus identity.
        prior=b["bindings"][k]
        if cid >= prior:
            return prior
        b["proofs"].pop(prior, None)
    b["bindings"][k]=cid
    b["proofs"][cid]=copy.deepcopy(certificate)
    return cid


def seal(b):
    m=b["manifest"]
    check_manifest(m)
    e=len(b["epochs"])+1
    if (e-1)*m["epoch_size"]>=len(m["keys"]):
        raise ValueError("all tasks finalized")
    required=epoch_keys(m,e)
    if not all(k in b["bindings"] for k in required):
        raise ValueError("epoch is incomplete: cannot commit a subset")
    parent=b["epochs"][-1]["id"] if b["epochs"] else m["id"]
    h=header_for(m,e,parent)
    b["epochs"].append(h)
    return h


def verify_bundle(b):
    if type(b) is not dict or set(b)!={"manifest","epochs","bindings","proofs"}:
        raise ValueError("bundle schema")
    m=b["manifest"]
    check_manifest(m)
    if type(b["epochs"]) is not list or type(b["bindings"]) is not dict or type(b["proofs"]) is not dict:
        raise ValueError("ledger collections invalid")
    if len(b["epochs"])>(len(m["keys"])+m["epoch_size"]-1)//m["epoch_size"]:
        raise ValueError("too many epochs")
    parent=m["id"]
    for epoch, actual in enumerate(b["epochs"],1):
        expected=header_for(m,epoch,parent)
        if actual!=expected:
            raise ValueError("noncanonical epoch, incorrect ordering, or corrupted roots")
        parent=expected["id"]
    if any(k not in m["keys"] for k in b["bindings"]):
        raise ValueError("unassigned proof binding")
    seen_cids=set()
    prime_cache=set()
    for k, cid in b["bindings"].items():
        if type(k) is not str or type(cid) is not str or len(cid)!=64:
            raise ValueError("invalid binding")
        if cid not in b["proofs"] or cid in seen_cids:
            raise ValueError("missing/reused certificate")
        cert=b["proofs"][cid]
        if cid != proof_cid(cert):
            raise ValueError("proof content address mismatch")
        if check_certificate(cert, prime_cache)["key"]!=k:
            raise ValueError("statement and proof mismatch")
        seen_cids.add(cid)
    if set(b["proofs"])!=seen_cids:
        raise ValueError("orphan or hidden evidence")
    committed=len(b["epochs"])*m["epoch_size"]
    for key in m["keys"][:committed]:
        if key not in b["bindings"]:
            raise ValueError("finalized fact without available proof")
    n=min(committed,len(m["keys"]))
    return {"epochs":len(b["epochs"]),"finalized":n,"pending":len(b["bindings"])-n,
            "remaining":len(m["keys"])-n,
            "knowledge_root":merkle_root(m["keys"][:n]),
            "tip":parent, "verified_distinct_prime_endpoints":len(prime_cache)}


def derived_prime_count(b, first, last):
    """Finite derived theorem: if k adjacent certified gaps connect first to last,
    exactly k-1 primes lie strictly between those endpoints.
    Reuses validated gap facts; no second primality test in the derivation.
    """
    state=verify_bundle(b)
    keys=set(b["manifest"]["keys"][:state["finalized"]])
    if not(valid_int(first,2) and valid_int(last,3) and first<last):
        raise ValueError("invalid interval")
    edges={}
    for k in keys:
        _,s,t=k.split(':')
        p,q=int(s),int(t)
        if p in edges and edges[p]!=q:
            raise ValueError("conflicting certified successors")
        edges[p]=q
    x=first
    chain=[]
    while x<last:
        if x not in edges or len(chain)>=len(keys):
            raise ValueError("no complete proof chain")
        q=edges[x]
        chain.append(statement(x,q))
        x=q
    if x!=last or not chain:
        raise ValueError("interval does not match certified chain")
    result={"type":"prime-count-open-v1","first":first,"last":last,
            "interior_prime_count":len(chain)-1,"depends_on":chain}
    result['claim_id']=H({"kind":"derived-fact-v03", "statement":{k:v for k,v in result.items() if k not in ("depends_on","claim_id")}})
    return result


def write_atomic(b, path):
    verify_bundle(b)
    path=Path(path)
    p=path.with_suffix(path.suffix+'.tmp')
    p.write_bytes(canonical(b)+b'\n')
    p.replace(path)


def init_db(path, b):
    """SQLite is a durable local evidence store, not distributed finality."""
    verify_bundle(b)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS snapshot (name TEXT PRIMARY KEY, json TEXT NOT NULL)')
        db.execute('INSERT OR REPLACE INTO snapshot VALUES (?,?)',('registry',canonical(b).decode()))
        db.commit()


def read_db(path):
    with sqlite3.connect(path) as db:
        row=db.execute('SELECT json FROM snapshot WHERE name=?',('registry',)).fetchone()
    if row is None:
        raise ValueError('missing registry snapshot')
    b=json.loads(row[0]);verify_bundle(b)
    return b


def demo(n=200,epoch_size=10,seed=42,output=None):
    tasks=consecutive_gaps(1_000_000,n)
    b=new_bundle(tasks,epoch_size)
    rng=random.Random(seed)
    rng.shuffle(tasks)
    for p,q in tasks:
        submit(b,make_certificate(p,q,31))
    while len(b['epochs'])*epoch_size<n:
        seal(b)
    state=verify_bundle(b)
    if output: write_atomic(b,output)
    return b,state


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    sub=cli.add_subparsers(dest='cmd', required=True)
    p=sub.add_parser('demo');p.add_argument('--blocks',type=int,default=200);p.add_argument('--epoch-size',type=int,default=10);p.add_argument('--output',default='epoch_chain_200.json')
    p=sub.add_parser('verify');p.add_argument('file')
    p=sub.add_parser('derive');p.add_argument('file');p.add_argument('first',type=int);p.add_argument('last',type=int)
    args=cli.parse_args()
    if args.cmd=='demo':
        b,result=demo(args.blocks,args.epoch_size,output=args.output)
    else:
        b=json.loads(Path(args.file).read_text())
        result=verify_bundle(b) if args.cmd=='verify' else derived_prime_count(b,args.first,args.last)
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()