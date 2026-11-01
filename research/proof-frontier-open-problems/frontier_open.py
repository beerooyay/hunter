#!/usr/bin/env python3
"""A scope-preserving audit ledger, NOT an automated proof search or consensus system."""
import hashlib, json
from pathlib import Path
from math import isqrt
from itertools import product

HERE=Path(__file__).resolve().parent


def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def digest(x): return hashlib.sha256(canon(x).encode()).hexdigest()

def prime(n):
    if n < 2: return False
    return all(n%d for d in range(2,isqrt(n)+1))

def collatz(n): return n//2 if n%2 == 0 else 3*n+1

def verify_collatz_family(limit=250):
    assert all(collatz(collatz(collatz(4*k+1))) == 3*k+1 and 3*k+1<4*k+1 for k in range(1,limit+1))
    # A nearby tempting stronger statement is false: odd 4k+3 does not generally descend in three steps.
    witness=3
    assert collatz(collatz(collatz(witness))) >= witness
    return {'tested_k':limit,'counterexample_to_bad_extension':witness,'counterexample_3_steps':collatz(collatz(collatz(witness)))}

def verify_goldbach(bound=30):
    witnesses={}
    for n in range(4,bound+1,2):
        found=next(((p,n-p) for p in range(2,n) if prime(p) and prime(n-p)),None)
        assert found is not None
        witnesses[str(n)] = list(found)
    return {'bound':bound,'witnesses':witnesses}

def verify_euler():
    n=40; value=n*n+n+41
    assert value==41*41 and not prime(value)
    assert all(prime(k*k+k+41) for k in range(40))
    return {'failed_n':40,'value':1681,'factorization':[41,41], 'finite_restriction_tested':'0 <= n < 40'}

def make_node(key,kind,statement,scope,truth_status,proof_file=None,lean_name=None):
    n={'key':key,'kind':kind,'statement':statement,'scope':scope,'status':truth_status,
       'proof_file':proof_file,'lean_name':lean_name}
    n['id']=digest(n)
    return n

def make_graph():
    # "kernel-checked" is NEVER emitted by this script: CI must separately verify Lean.
    nodes=[
      make_node('collatz_all','open_conjecture','forall n>0, some iterate of T reaches 1','all positive integers','open'),
      make_node('collatz_four_k_one','restricted_lemma','T^3(4k+1)=3k+1<4k+1 for all k>0','k>0','lean_pending','lean/OpenProblems.lean','collatz_four_k_one_descends'),
      make_node('collatz_four_k_three','open_branch','no uniform three-step descent from 4k+3','k>=0','example_refuted'),
      make_node('goldbach_all','open_conjecture','all even n>=4 are sums of two primes','all even n>=4','open'),
      make_node('goldbach_30','finite_lemma','all even 4<=n<=30 have two prime summands','4<=n<=30 even','lean_pending','lean/OpenProblems.lean','goldbach_up_to_30'),
      make_node('goldbach_100','instance_lemma','100=3+97, both prime','n=100','lean_pending','lean/OpenProblems.lean','goldbach_at_100'),
      make_node('euler_every_n','false_conjecture','n^2+n+41 is prime for all natural n','all n>=0','refuted'),
      make_node('euler_counterexample','counterexample','n=40 yields 1681=41*41','n=40','lean_pending','lean/OpenProblems.lean','euler_polynomial_counterexample'),
      make_node('euler_repair','restricted_claim','n^2+n+41 is prime for 0<=n<40','0<=n<40','experiment_only'),
    ]
    edges=[
      ('collatz_all','collatz_four_k_one','restricted_subgoal'),
      ('collatz_all','collatz_four_k_three','unresolved_obligation'),
      ('goldbach_all','goldbach_30','restricted_subgoal'),
      ('goldbach_all','goldbach_100','verified_instance_pending_kernel'),
      ('euler_every_n','euler_counterexample','refuted_by'),
      ('euler_every_n','euler_repair','domain_restriction'),
    ]
    idmap={n['key']:n['id'] for n in nodes}
    graphs=[{'from':idmap[a],'to':idmap[b],'relation':rel} for a,b,rel in edges]
    result={
      'schema':'praetor.scope-frontier.v1',
      'trust_model':{'cryptographic_hash':'integrity only','python_evidence':'test not formal proof',
                     'formal_proof':'pending until external Lean job succeeds','novelty':'unassessed'},
      'nodes':nodes,'edges':graphs,
      'evidence':{'collatz':verify_collatz_family(),'goldbach':verify_goldbach(), 'euler':verify_euler()},
    }
    result['root']=digest(result)
    validate(result)
    return result

def validate(g):
    assert g['schema']=='praetor.scope-frontier.v1'
    assert all(n['id']==digest({k:v for k,v in n.items() if k!='id'}) for n in g['nodes'])
    ids={n['id'] for n in g['nodes']}
    assert len(ids)==len(g['nodes'])
    assert all(e['from'] in ids and e['to'] in ids for e in g['edges'])
    # no restricted statement may be promoted to a proof of a universal conjecture
    assert all(n['status']=='open' for n in g['nodes'] if n['kind']=='open_conjecture')
    assert all(n['status']!='kernel_checked' for n in g['nodes'])
    assert g['root']==digest({k:v for k,v in g.items() if k!='root'})
    assert g['evidence']['euler']['value']==41*41
    assert all(prime(p) and prime(q) and p+q==int(n) for n,(p,q) in g['evidence']['goldbach']['witnesses'].items())
    return True

def main():
    graph=make_graph()
    path=HERE/'open_problem_frontier.json'
    path.write_text(json.dumps(graph,sort_keys=True,indent=2)+'\n')
    print(f"[PASS] {len(graph['nodes'])} scoped nodes, {len(graph['edges'])} typed edges, sha256 root {graph['root'][:16]}")
    for n in graph['nodes']:
        print(f"  {n['key']:<25} {n['status']:<14} {n['scope']}")
    print('[PASS] Goldbach 4..30, Collatz 4k+1 for k<=250, false Euler conjecture refuted')
    print('[UNRESOLVED] Full Collatz and full binary Goldbach; no global theorem claimed')
    print('[PENDING] Lean kernel status until CI completes')

if __name__=='__main__':main()