#!/usr/bin/env python3
import copy, random
from proof_receipt import new_claim, check_claim, example_instance,prime_trial
from conditional_void import forced_composite

def must_fail(fn):
    try: fn()
    except (ValueError,AssertionError,TypeError): return
    raise AssertionError('attack unexpectedly accepted')

def test():
    patterns=[([0,2,6,12,14,20],17),([0,2,8,12,14,18],29),([0,4,6,10,16,18],13),([0,6,8,14,18,20],23)]
    for H,n in patterns:
        r=new_claim(H)
        assert check_claim(r)
        assert not r['claim']['unresolved']
        assert example_instance(r,n)['all_consecutive']
        assert all(not prime_trial(n+b) for b in range(1,H[-1]) if b not in H)
    r=new_claim(patterns[0][0]); check_claim(r)
    for field,modify in [('missing',lambda x:x['claim']['witnesses'].pop('4')),
                         ('fake modulus',lambda x:x['claim']['witnesses'].__setitem__('4',7)),
                         ('wrong offset',lambda x:x['claim']['offsets'].__setitem__(1,3)),
                         ('wrong claim digest',lambda x:x.__setitem__('claim_id','0'*64)),
                         ('misleading status',lambda x:x['status'].__setitem__('lean_kernel','VERIFIED'))]:
        x=copy.deepcopy(r); modify(x)
        must_fail(lambda:check_claim(x))
    must_fail(lambda:example_instance(r,19))
    rng=random.Random(42)
    for _ in range(3000):
        x=copy.deepcopy(r)
        q=rng.randrange(5)
        if q==0:x['claim']['offsets'][rng.randrange(6)]+=rng.randrange(1,5)
        if q==1:x['claim']['witnesses']['4']+=rng.randrange(1,4)
        if q==2:x['claim']['unresolved'].append(rng.randrange(1,20))
        if q==3:x['claim_id']=str(rng.getrandbits(256))
        if q==4:x['status']['human_statement_review']='VERIFIED'
        must_fail(lambda:check_claim(x))
    # Exhaustively check the actual modular implication on small bases; don't assume the conclusion.
    for H,n in patterns:
        for base in range(11,5000):
            if not all(prime_trial(base+h) for h in H):continue
            for b in range(1,H[-1]):
                if b in H:continue
                p=forced_composite(tuple(H),b)
                if p is not None and base>p:
                    assert (base+b)%p==0
    print('passed: 4 fully forced motifs, 5 semantic attacks, 3000 mutations, independent interval checks')
if __name__=='__main__':test()