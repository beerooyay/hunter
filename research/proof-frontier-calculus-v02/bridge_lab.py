#!/usr/bin/env python3
"""Exact unused-residue difference bridge experiment. No theorem is inferred from tests."""
from itertools import product
from collections import Counter
from math import prod, isqrt
import json

ALPHABET=(2,4,6,8,10)

def primes_up_to(n):return tuple(i for i in range(2,n+1) if all(i%j for j in range(2,isqrt(i)+1)))
def offsets(w):
 a=[0]
 for g in w:a.append(a[-1]+g)
 return tuple(a)
def admissible(A):
 return all(len({a%p for a in A})<p for p in primes_up_to(len(A)))
def words(k):return tuple(w for w in product(ALPHABET,repeat=k) if admissible(offsets(w)))
def local_shift_residues(A,B,p):
 ma={i for i in range(p)} - {a%p for a in A}
 mb={i for i in range(p)} - {b%p for b in B}
 return frozenset((x-y-A[-1])%p for x in ma for y in mb)
def direct_good(A,B,g):return admissible(A+tuple(A[-1]+g+b for b in B))
def min_bridge_fast(A,B,limit=2310):
 pp=primes_up_to(len(A)+len(B)); allowed=[(p,local_shift_residues(A,B,p)) for p in pp]
 for g in range(2,limit+1,2):
  if all(g%p in ok for p,ok in allowed):return g
 return None

def independently_check(k, ids, table):
 W=words(k)
 for i,j in ids:
  g=table[i*len(W)+j]
  A=offsets(W[i]); B=offsets(W[j])
  if not direct_good(A,B,g):raise AssertionError(('invalid',i,j,g))
  for h in range(2,g,2):
   if direct_good(A,B,h):raise AssertionError(('not minimum',i,j,g,h))
 return True

if __name__=='__main__':
 for k in (2,3,4,5):
  W=words(k); values=[]; hist=Counter();extremizers=[];maxg=0
  for i,w in enumerate(W):
   A=offsets(w)
   for j,v in enumerate(W):
    g=min_bridge_fast(A,offsets(v));assert g is not None
    values.append(g);hist[g]+=1
    if g>maxg:maxg=g;extremizers=[(i,j)]
    elif g==maxg:extremizers.append((i,j))
  candidates=sorted(set([(i,i) for i in range(len(W))]+extremizers+[(i,j) for i in range(0,len(W),max(1,len(W)//11)) for j in range(0,len(W),max(1,len(W)//11))]))
  independently_check(k,candidates,values)
  result={'k':k,'source_motifs':len(W),'pairs':len(values),'max_min_bridge':maxg,'extremizers':[[list(W[i]),list(W[j])] for i,j in extremizers], 'independently_checked_pairs':len(candidates),'histogram':dict(sorted(hist.items()))}
  open(f'/mnt/data/pfc_frontier_v02/bridge_k{k}.json','w').write(json.dumps(result,indent=2)+'\n')
  print(k,len(W),len(values),maxg,len(extremizers),len(candidates),flush=True)