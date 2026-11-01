"""A second proof-frontier domain: exact finite polynomial 'fudge-factor' repair.

A hand-wavy inequality f(n) <= g(n)+c for n in [0,N] becomes an exact
minimum-slack problem. This is elementary known mathematics, not a new theorem.
"""
import json
from pathlib import Path


def polynomial(coeff, n):
    return sum(c*n**i for i,c in enumerate(coeff))


def generate(f,g,bound,original_claim):
    diffs=[polynomial(f,n)-polynomial(g,n) for n in range(bound+1)]
    slack=max([0]+diffs)
    tight=max(range(bound+1),key=lambda n:diffs[n])
    original_counterexample=next((n for n,d in enumerate(diffs) if d>0),None)
    return {'type':'bounded-polynomial-inequality','statement':original_claim,
            'f':f,'g':g,'domain':{'min':0,'max':bound},
            'original_status':'refuted' if original_counterexample is not None else 'proved_on_bounded_domain',
            'counterexample':original_counterexample,
            'repair':{'added_constant':slack,'tight_witness':tight},
            'scope':'exact bound on the finite integer domain only'}


def verify(record):
    assert record['type']=='bounded-polynomial-inequality'
    assert record['scope']=='exact bound on the finite integer domain only'
    assert record['domain']['min']==0
    N=record['domain']['max']; assert isinstance(N,int) and 0<=N<=10000
    f=record['f']; g=record['g']; assert all(isinstance(x,int) for x in f+g)
    assert len(f)<=8 and len(g)<=8
    diffs=[polynomial(f,n)-polynomial(g,n) for n in range(N+1)]
    assert record['original_status']==('refuted' if max(diffs)>0 else 'proved_on_bounded_domain')
    ce=record['counterexample']
    assert (ce is None) == (max(diffs)<=0)
    if ce is not None: assert 0<=ce<=N and diffs[ce]>0
    c=record['repair']['added_constant']; witness=record['repair']['tight_witness']
    assert c>=0 and 0<=witness<=N
    assert all(d<=c for d in diffs) # upper bound for every point
    assert c==max(0,diffs[witness]) # one witness proves lower bound
    return True


def main():
    cases=[generate([0,0,1],[0,7],20,'for n in 0..20, n^2 <= 7n (maybe with small fudge)'),
           generate([0,0,0,1],[0,0,4],15,'n^3 <= 4n^2 on 0..15?'),
           generate([0,1,1],[0,10],10,'n^2 + n <= 10n on 0..10?')]
    for c in cases:verify(c)
    path=Path(__file__).parent/'slack_certificates.json'
    path.write_text(json.dumps(cases,indent=2)+'\n')
    print('EXACT SLACK REPAIRS:',[(c['repair']['added_constant'],c['repair']['tight_witness']) for c in cases])

if __name__=='__main__':main()