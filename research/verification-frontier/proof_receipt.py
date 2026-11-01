#!/usr/bin/env python3
"""Praetor mathematical audit receipt, v0.4. Standard library only.

This certifies *modular implications*, not novel theorems or Lean proofs.
The example also checks a finite prime tuple using deterministic trial division.
"""
import hashlib
import json
import math
from pathlib import Path
from conditional_void import forced_composite

DOMAIN='praetor.claim.v04.conditional-exclusion'


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(DOMAIN.encode()+b'\x00'+canonical(value)).hexdigest()


def prime_trial(n):
    """Deterministic primality check for SMALL examples, not a large-prime protocol."""
    if type(n)!=int or n<2:return False
    if n%2==0:return n==2
    for d in range(3,math.isqrt(n)+1,2):
        if n%d==0:return False
    return True


def new_claim(offsets):
    H=tuple(offsets)
    if len(H)<2 or H[0]!=0 or H!=tuple(sorted(set(H))) or any(type(x)!=int or x<0 for x in H):
        raise ValueError('invalid distinct nonnegative sorted offsets')
    if H[-1]>100000 or len(H)>50:
        raise ValueError('toy certificate domain too large')
    witnesses={}
    unresolved=[]
    for b in range(1,H[-1]):
        if b in H: continue
        p=forced_composite(H,b)
        if p is None: unresolved.append(b)
        else: witnesses[str(b)]=p
    stmt={'kind':'forced-interior-composite-pattern','offsets':list(H),'scope':'all bases n for which every n+h is prime and > every witness prime','witnesses':witnesses,'unresolved':unresolved}
    return {'claim':stmt,'claim_id':digest(stmt), 'status':{'modular_witnesses':'checked_by_independent_integer_arithmetic','lean_kernel':'NOT_RUN','human_statement_review':'PENDING','historical_novelty':'NOT_ESTABLISHED'}}


def check_claim(obj):
    if type(obj)!=dict or set(obj)!={'claim','claim_id','status'}:raise ValueError('invalid receipt fields')
    c=obj['claim'];H=c['offsets']
    if type(H)!=list or any(type(x)!=int for x in H):raise ValueError('invalid offsets')
    rebuilt=new_claim(H)
    if c!=rebuilt['claim'] or obj['claim_id']!=rebuilt['claim_id'] or obj['status']!=rebuilt['status']:
        raise ValueError('mismatched or tampered claim')
    # independent of forced_composite function: check every supplied witness by residue enumeration
    for bs,p in c['witnesses'].items():
        b=int(bs)
        if not prime_trial(p) or len({a%p for a in H})!=p-1 or len({a%p for a in H+[b]})!=p:
            raise ValueError('invalid modular cover')
    if set(map(int,c['witnesses']))|set(c['unresolved']) != set(range(1,H[-1]))-set(H):
        raise ValueError('missing interior claim')
    return True


def example_instance(receipt,base):
    check_claim(receipt)
    H=receipt['claim']['offsets']
    if type(base)!=int or base<2 or base+H[-1]>10_000_000_000:raise ValueError('invalid or excessively large toy example base')
    positions=[base+x for x in H]
    if not all(prime_trial(x) for x in positions):raise ValueError('prescribed positions not all prime')
    if receipt['claim']['witnesses'] and min(positions)<=max(receipt['claim']['witnesses'].values()):
        raise ValueError('prime positions not above modulus bounds')
    # Unresolved points get direct trial check; in full cover case there are none.
    for b in receipt['claim']['unresolved']:
        if prime_trial(base+b):raise ValueError('not a consecutive-prime constellation')
    for bs,p in receipt['claim']['witnesses'].items():
        if (base+int(bs))%p:raise ValueError('arithmetic implication failed')
    return {'base':base,'primes':positions,'all_consecutive':True,'forced_interior':len(receipt['claim']['witnesses']), 'unresolved_interior':len(receipt['claim']['unresolved']), 'proof_status':'finite small-prime verification, NOT Lean kernel'}


def human_audit_md(receipt,instance=None):
    c=receipt['claim']
    H=c['offsets']
    lines=['# praetor research receipt v0.4','',f'claim id: `{receipt["claim_id"]}`','',
           '## exact statement (mathematical implication)','',
           f'for offsets `H = {H}`, assume that `n+h` is prime and greater than every listed witness modulus for each h in H.',
           'then every interior offset recorded with a witness is composite; remaining offsets are not covered by this theorem.',
           '', '## independently recheckable modular evidence', '', '| offset | modulus | residue classes of H modulo modulus |','|---:|---:|---|']
    for bs,p in c['witnesses'].items():
        lines.append(f'| {bs} | {p} | {sorted({x%p for x in H})} |')
    lines += ['',f'unresolved interior offsets: `{c["unresolved"]}`','',
              '## proof sketch','',
              'for each listed b, H occupies every residue class except one modulo p, and b occupies the missing class. since all n+h are prime larger than p, none can be divisible by p. therefore n+b must be divisible by p and, being larger than p, is composite.',
              '', '## trust boundaries', '',
              '- the modular certificates were checked by two arithmetic implementations, not by the Lean kernel.',
              '- the hypothesis that the designated numbers are prime must be independently certified.',
              '- this is a known prime-constellation/admissibility mechanism, not a claimed new theorem.',
              '- independent human verification of the intended statement is still pending.',
              '- a blockchain/consensus validity claim is not implied.', '']
    if instance is not None:
        lines += ['## finite example', '',f'base = {instance["base"]}; prescribed primes = {instance["primes"]}.',
                  'verified using small-integer deterministic primality and modular divisibility.','']
    return '\n'.join(lines)


if __name__=='__main__':
    H=[0,2,6,12,14,20]
    obj=new_claim(H)
    assert not obj['claim']['unresolved']
    inst=example_instance(obj,17)
    root=Path(__file__).parent
    (root/'auditable_claim.json').write_text(json.dumps({'receipt':obj,'example':inst},indent=2)+'\n')
    (root/'HUMAN_REVIEW.md').write_text(human_audit_md(obj,inst)+'\n')
    print('claim',obj['claim_id'],'forced',len(obj['claim']['witnesses']),'example',inst['primes'])