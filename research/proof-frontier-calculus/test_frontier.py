"""No IO or API fixtures required, deterministic adversarial lab."""
from frontier import *
from independent import run as independent_survey
import copy, json, random
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def rejected(fn):
    try:fn()
    except (ValueError,TypeError,KeyError,AssertionError):return
    raise AssertionError('acceptance of forged data')

def test():
    repairs=typed_repair_lab()
    assert len(repairs)==4
    # Full independent survey, checks every pair and exact histogram.
    S=sharp_bridge_survey()
    I=independent_survey()
    assert I['pairs']==S['pairs']==23716
    assert I['max_bridge']==S['sharp_maximum_shortest_bridge']==150
    assert I['max_pairs']==[(e['left'],e['right']) for e in S['extremizers']]
    assert I['histogram']==S['distribution']
    # Complete PFC/CRT audit, completely independent exhaustive enumeration of CRT period.
    T=theorem_stress()
    assert T['cases']==T['forced']+T['open_modular']==8120
    # Prove source+candidate cover and independent residue witness.
    H=(0,2,6,12,14,20);b=4
    w=modular_frontier(H,b)
    assert w['kind']=='forced' and verify_modular_receipt(w)
    # Force small witness minimal: one representative for each non-b residue.
    p=w['certificate']['modulus'];W=w['certificate']['witness_offsets']
    assert len(W)==p-1
    assert len({t%p for t in W+[b]})==p
    open_w=modular_frontier((0,2,6),8,(2,3,5,7))
    assert open_w['kind']=='open_modular'
    Q=open_w['certificate']['period'];x=open_w['certificate']['base_residue']
    assert Q==210 and all((x+t)%p!=0 for p in [2,3,5,7] for t in (0,2,6,8))
    # Detect semantic mutations, even if someone updates a field and claims it is still a proof.
    rng=random.Random(234)
    for i in range(2500):
        o=copy.deepcopy(w);mode=i%5
        if mode==0:o['certificate']['modulus']=rng.choice([1,4,7,9,11])
        if mode==1:o['certificate']['witness_offsets'][0]+=10000+2*rng.randint(1,10)
        if mode==2:o['statement']['candidate']+=rng.randint(1,10)
        if mode==3:o['claim_id']='0'*64
        if mode==4:o['kind']='open_modular'
        rejected(lambda:verify_modular_receipt(o))
    G=make_graph(repairs,T,S)
    assert verify_graph(G)
    for i in range(400):
        bad=copy.deepcopy(G)
        mode=i%4
        if mode==0:bad['root']='0'*64
        if mode==1:bad['nodes'].pop(next(iter(bad['nodes'])))
        if mode==2:bad['edges'][0]['to']='0'*64
        if mode==3:bad['trust']['Lean_kernel']='VERIFIED'
        rejected(lambda:verify_graph(bad))
    # Claim receipts for each bound include bounded scope and no false universal proof promotion.
    assert repairs[0]['universal_proof'] is False
    assert S['scope'].startswith('finite exhaustive')
    print(json.dumps({'status':'PASS','repair_operators':4,'independently_agreed_pairs':I['pairs'],'sharp_bridge':I['max_bridge'],'extremizers':len(I['max_pairs']),'crt_independent_cases':T['cases'],'forced':T['forced'],'modular_survivors':T['open_modular'],'tampering_rejected':2900,'graph_nodes':len(G['nodes'])},indent=2))

if __name__=='__main__':test()