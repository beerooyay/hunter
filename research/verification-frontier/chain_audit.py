#!/usr/bin/env python3
"""Demonstrate non-PoW predictability in proof-frontier v0.3.
Not a forged valid chain: evidence remains required by its bundle verifier.
"""
import sys, json
from pathlib import Path
source=Path(__file__).resolve().parent
sys.path.insert(0,str(source))
from frontier_v03 import manifest, header_for, check_manifest

m=manifest([[113,127],[127,131],[131,137]],1)
check_manifest(m)
parent=m['id'];chain=[]
for epoch in (1,2,3):
    h=header_for(m,epoch,parent)
    chain.append(h['id']);parent=h['id']
assert len(set(chain))==3
print(json.dumps({'finding':'all future epoch IDs are predictable from the public manifest with zero mathematical certificates',
                  'manifest_id':m['id'],'future_epoch_ids':chain,
                  'scope':'v0.3 fixed-manifest prototype; this is NOT a forged valid evidence bundle'},indent=2))