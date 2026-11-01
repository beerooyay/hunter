#!/usr/bin/env python3
"""Proof Frontier Calculus v0.1: inspectable, finite arithmetic research synthesis.

No NLP/LLM is invoked. Input is a typed mathematical claim, and all receipts
are verified by exact integer arithmetic. No large-prime or Lean claims.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
import hashlib, json, math

DOMAIN = b'praetor.proof-frontier-calculus.v01\0'


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(obj):
    return hashlib.sha256(DOMAIN + canonical(obj)).hexdigest()


def primes_upto(n):
    return tuple(x for x in range(2,n+1) if all(x%d for d in range(2,math.isqrt(x)+1)))


def require_offsets(H):
    if not isinstance(H,(tuple,list)) or not (2<=len(H)<=24):
        raise ValueError('need 2..24 offsets')
    if any(type(x) is not int or x<0 for x in H) or tuple(H)!=tuple(sorted(set(H))) or H[0]!=0 or H[-1]>10000:
        raise ValueError('offsets must be sorted, distinct, start at 0 and <=10000')
    return tuple(H)


def admissible(H):
    H=require_offsets(H)
    return all(len({h%p for h in H})<p for p in primes_upto(len(H)))


def crt(remainders):
    """Non-negative CRT representative, pairwise coprime moduli; no probabilistic arithmetic."""
    Q=math.prod(p for p,_ in remainders)
    x=0
    for p,r in remainders:
        M=Q//p
        x=(x+r*M*pow(M,-1,p))%Q
    return x,Q


def verify_modular_receipt(r):
    if type(r)!=dict or set(r)!={'statement','claim_id','certificate','kind'}:raise ValueError('bad receipt fields')
    H=require_offsets(r['statement']['offsets']);b=r['statement']['candidate']
    P=r['statement']['primes'];
    if type(b) is not int or b<0 or b in H or b>10000:raise ValueError('bad missing position')
    if type(P)!=list or not P or P!=sorted(set(P)) or any(type(x)!=int for x in P) or any(p>97 for p in P):raise ValueError('bad prime basis')
    if any(p not in primes_upto(97) for p in P):raise ValueError('not prime moduli')
    if any(len({h%p for h in H})==p for p in P):raise ValueError('invalid source (not locally admissible)')
    statement={'offsets':list(H),'candidate':b,'primes':P}
    if r['statement']!=statement or r['claim_id']!=digest(statement):raise ValueError('claim changed')
    cert=r['certificate']
    if r['kind']=='forced':
        if type(cert)!=dict or set(cert)!={'modulus','witness_offsets'}:raise ValueError('bad forced certificate')
        p=cert['modulus'];W=cert['witness_offsets']
        if p not in P or type(W)!=list or len(W)!=p-1 or any(type(x)!=int for x in W):raise ValueError('bad witnesses')
        if len(set(W))!=len(W) or not set(W).issubset(H):raise ValueError('witnesses not selected offsets')
        if len({h%p for h in W})!=p-1 or len({h%p for h in W+[b]})!=p:raise ValueError('bad residue cover')
    elif r['kind']=='open_modular':
        if type(cert)!=dict or set(cert) != {'base_residue','period','local_residues'}:raise ValueError('bad open certificate')
        x=cert['base_residue'];Q=cert['period'];rr=cert['local_residues']
        if type(x)!=int or type(Q)!=int or type(rr)!=list or len(rr)!=len(P):raise ValueError('bad CRT')
        if Q!=math.prod(P) or not (0<=x<Q):raise ValueError('bad CRT modulus')
        if any(type(v)!=int or v<0 or v>=p or x%p!=v for p,v in zip(P,rr)):raise ValueError('bad CRT residues')
        if any(any((x+t)%p==0 for t in H+(b,)) for p in P):raise ValueError('claimed survivor excluded')
    else:raise ValueError('unknown kind')
    return True


def modular_frontier(H,b,P=None):
    """Complete finite modular implication test; if open, returns a CRT witness.

    A forced claim means: if all n+h are prime and >p, n+b is composite.
    An open claim means ONLY a residue-class survivor, never existence of primes.
    """
    H=require_offsets(H)
    if type(b)!=int or not (0<=b<=10000) or b in H:raise ValueError('bad b')
    if P is None:P=primes_upto(max(2,len(H)+1))
    P=tuple(P)
    if not P or tuple(sorted(set(P)))!=P or any(p not in primes_upto(97) for p in P):raise ValueError('unsupported prime basis')
    if any(len({h%p for h in H})==p for p in P):raise ValueError('source not locally admissible')
    statement={'offsets':list(H),'candidate':b,'primes':list(P)}
    for p in P:
        if len({t%p for t in H+(b,)})==p:
            residues={}
            for h in H:residues.setdefault(h%p,h)
            W=sorted(residues.values())
            r={'kind':'forced','statement':statement,'claim_id':digest(statement),'certificate':{'modulus':p,'witness_offsets':W}}
            verify_modular_receipt(r);return r
    rs=[]
    for p in P:
        good=[v for v in range(p) if all((v+t)%p for t in H+(b,))]
        if not good:raise AssertionError('non-forcing p lost all residues')
        rs.append((p,min(good)))
    x,Q=crt(rs)
    r={'kind':'open_modular','statement':statement,'claim_id':digest(statement),'certificate':{'base_residue':x,'period':Q,'local_residues':[v for _,v in rs]}}
    verify_modular_receipt(r);return r


def word_offsets(word):
    if not word or any(type(v)!=int or v<2 or v%2 for v in word):raise ValueError('positive even gaps only')
    a=[0]
    for g in word:a.append(a[-1]+g)
    return tuple(a)


def min_bridge(A,B,limit=160):
    """Search even bridging gaps; finite, exact small-modulus certificate."""
    A=require_offsets(A);B=require_offsets(B)
    if not admissible(A) or not admissible(B):raise ValueError('input must be admissible')
    for g in range(2,limit+1,2):
        H=A+tuple(A[-1]+g+b for b in B)
        if admissible(H):return g
    return None


def verify_bridge(A,B,g,limit=160):
    if not isinstance(g,int) or g%2 or g<2 or g>limit:raise ValueError('bad proposed bridge')
    if min_bridge(A,B,g)!=g:raise ValueError('not minimal bridge')
    for prev in range(2,g,2):
        H=A+tuple(A[-1]+prev+b for b in B)
        bad=next((p for p in primes_upto(len(H)) if len({h%p for h in H})==p),None)
        if bad is None:raise ValueError('missing obstruction')
    return True


def typed_repair_lab():
    """Four typed hypotheses and distinct repair semantics, with no fabricated universal proofs."""
    # 1: a universal primality claim that is false; finite-range restriction is explicitly bounded.
    def euler(n):return n*n+n+41
    failures=[n for n in range(0,200) if not trial_prime(euler(n))]
    assert failures[0]==40 and euler(40)==41*41
    verified=[{'n':n,'value':euler(n),'smallest_divisor':smallest_divisor(euler(n))} for n in range(40)]
    assert all(row['smallest_divisor']==row['value'] for row in verified)
    # 2: a false integer identity, with symbolic rather than statistical repair.
    import sympy as sp
    n=sp.symbols('n',integer=True,positive=True)
    summation=n*n
    proposed=n*n+1
    assert sp.simplify(summation-proposed)==-1
    assert sp.simplify(sp.summation(2*sp.Symbol('j')-1,(sp.Symbol('j'),1,n))-n*n)==0
    # 3: direct motif join false; minimal bridge exists, only modular admissibility is guaranteed.
    A=word_offsets((2,4));B=word_offsets((2,6))
    assert not admissible(A+tuple(A[-1]+b for b in B[1:]))
    g=min_bridge(A,B)
    assert g==6 and verify_bridge(A,B,g)
    # 4: conditional prime constellations; modular consequences, not prime existence.
    H=(0,2,6,12,14,20)
    forced=[modular_frontier(H,b) for b in range(1,20) if b not in H]
    assert len(forced)==15 and all(v['kind']=='forced' for v in forced)
    return [
        {'type':'counterexample_and_bounded_repair','original':'forall n >= 0: n^2+n+41 is prime','counterexample':{'n':40,'value':1681,'factors':[41,41]},'repair':'for 0<=n<=39, n^2+n+41 prime','verified_small_domain':verified,'universal_proof':False},
        {'type':'algebraic_repair','original':'sum_{j=1}^n (2j-1) = n^2+1','counterexample':{'n':1,'left':1,'right':2},'repair':'sum_{j=1}^n (2j-1) = n^2','symbolic_proof':'sum(2j-1)=2*n(n+1)/2-n=n^2','universal_proof':'elementary algebra and induction, not Lean checked'},
        {'type':'constructive_modular_repair','original':'concatenation (2,4)+(2,6) is admissible','obstruction':5,'repair':'insert gap 6 to obtain (2,4,6,2,6)','minimal_bridge':g,'scope':'prime-tuple admissibility, not prime occurrence'},
        {'type':'finite_modular_implications','original':'six required primes at offsets [0,2,6,12,14,20] may have interior primes','repair':'each of the fifteen nonselected offsets is forced composite under required-prime assumptions','witnesses':forced,'scope':'universal conditional implication; prime endpoints not certified here'}]


def smallest_divisor(n):
    return next((p for p in range(2,math.isqrt(n)+1) if n%p==0),n)


def trial_prime(n):return n>=2 and smallest_divisor(n)==n


def theorem_stress(exhaustive_bound=32):
    """Independent full enumeration of modular local-vs-global equivalence."""
    cases=forced=open_count=0
    for pset in [(2,3),(2,3,5),(3,5),(2,5,7)]:
        Q=math.prod(pset)
        for h1 in range(2,exhaustive_bound,2):
            for h2 in range(h1+2,exhaustive_bound+2,2):
                H=(0,h1,h2)
                if any(len({h%p for h in H})==p for p in pset):continue
                for b in range(0,h2+1):
                    if b in H:continue
                    r=modular_frontier(H,b,pset)
                    independent_open=any(all((x+t)%p for t in H+(b,) for p in pset) for x in range(Q))
                    if (r['kind']=='open_modular')!=independent_open:raise AssertionError((H,b,pset))
                    cases+=1
                    forced+=r['kind']=='forced';open_count+=r['kind']=='open_modular'
    return {'cases':cases,'forced':forced,'open_modular':open_count}


@lru_cache(None)
def admissible_words(k,alphabet=(2,4,6,8,10)):
    return tuple(w for w in product(alphabet,repeat=k) if admissible(word_offsets(w)))


def sharp_bridge_survey(k=4,limit=160):
    """Exact finite extremal survey; all admissible source words in fixed alphabet."""
    ws=admissible_words(k)
    # Precompute local allowed shift sets for speed; minimum using independent simple checker.
    counts={};examples=[];max_bridge=0;max_pairs=[];missing=[]
    for i,w in enumerate(ws):
        A=word_offsets(w)
        for j,v in enumerate(ws):
            B=word_offsets(v)
            g=min_bridge(A,B,limit)
            if g is None:
                missing.append((i,j));continue
            counts[g]=counts.get(g,0)+1
            if g>max_bridge:max_bridge=g;max_pairs=[(w,v)]
            elif g==max_bridge:max_pairs.append((w,v))
    if missing:raise AssertionError('unrepaired pairs '+str(missing[:3]))
    assert sum(counts.values())==len(ws)**2
    for w,v in max_pairs:assert verify_bridge(word_offsets(w),word_offsets(v),max_bridge,limit)
    return {'gap_length_alphabet':list((2,4,6,8,10)),'source_word_length':k,'admissible_source_motifs':len(ws),'pairs':len(ws)**2,'sharp_maximum_shortest_bridge':max_bridge,'extremizers':[{'left':list(a),'right':list(b)} for a,b in max_pairs], 'distribution':dict(sorted(counts.items())),'scope':'finite exhaustive theorem only, no global novelty claim'}


def make_graph(typed,stress,survey):
    nodes={};edges=[]
    def add(kind,data):
        obj={'kind':kind,'data':data};id=digest(obj);nodes[id]=obj;return id
    for e in typed:
        parent=add('informal_claim',{'statement':e['original']})
        if 'counterexample' in e:
            evid=add('counterexample',e['counterexample']);edges.append({'from':parent,'to':evid,'rule':'refuted_by'})
        if 'obstruction' in e:
            obs=add('modular_obstruction',{'p':e['obstruction']});edges.append({'from':parent,'to':obs,'rule':'refuted_by'})
        if 'witnesses' in e:
            for r in e['witnesses']:
                t=add('modular_certificate',r);edges.append({'from':parent,'to':t,'rule':'conditioned_by'})
        child=add('repaired_claim',{'statement':e['repair'],'scope':e.get('scope',e.get('universal_proof','bounded exact'))})
        edges.append({'from':parent,'to':child,'rule':'proposed_repair'})
    st=add('finite_completeness_audit',stress)
    br=add('finite_extremal_bridge_certificate',survey)
    return {'schema':'praetor.pfc.v0.1','nodes':dict(sorted(nodes.items())),'edges':sorted(edges,key=lambda x:(x['from'],x['to'],x['rule'])),'root':digest({'node_ids':sorted(nodes),'edges':sorted(edges,key=lambda x:(x['from'],x['to'],x['rule']))}),'heads':[st,br],'trust':{'exact_integer':'checked','symbolic_identity':'sympy plus algebraic derivation','Lean_kernel':'NOT_RUN','literature_novelty':'NOT_ESTABLISHED','blockchain_consensus':'NOT_IMPLEMENTED'}}


def verify_graph(G):
    if set(G)!={'schema','nodes','edges','root','heads','trust'} or G['schema']!='praetor.pfc.v0.1':raise ValueError('schema mismatch')
    for id,obj in G['nodes'].items():
        if id!=digest(obj):raise ValueError('node digest mismatch')
        if obj['kind']=='modular_certificate':verify_modular_receipt(obj['data'])
    for e in G['edges']:
        if set(e)!={'from','to','rule'} or e['from'] not in G['nodes'] or e['to'] not in G['nodes']:raise ValueError('invalid edge')
    if len(set(map(canonical,G['edges'])))!=len(G['edges']):raise ValueError('duplicate edge')
    if G['root']!=digest({'node_ids':sorted(G['nodes']),'edges':sorted(G['edges'],key=lambda x:(x['from'],x['to'],x['rule']))}):raise ValueError('root mismatch')
    if G['trust']!={'exact_integer':'checked','symbolic_identity':'sympy plus algebraic derivation','Lean_kernel':'NOT_RUN','literature_novelty':'NOT_ESTABLISHED','blockchain_consensus':'NOT_IMPLEMENTED'}:raise ValueError('invalid trust')
    return True


if __name__=='__main__':
    from pathlib import Path
    root=Path(__file__).resolve().parent
    typed=typed_repair_lab()
    stress=theorem_stress()
    survey=sharp_bridge_survey()
    G=make_graph(typed,stress,survey)
    assert verify_graph(G)
    for filename,obj in [('repairs.json',typed),('crt_audit.json',stress),('bridge_survey.json',survey),('proof_graph.json',G)]:
        (root/filename).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'stress':stress,'survey':{k:v for k,v in survey.items() if k not in ('distribution','extremizers')},'extremizers':len(survey['extremizers']),'graph_nodes':len(G['nodes']),'graph_edges':len(G['edges']),'graph_root':G['root']},indent=2))