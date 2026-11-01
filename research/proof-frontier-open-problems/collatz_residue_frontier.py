#!/usr/bin/env python3
"""Exact affine residue cells for finite Collatz iterates; NOT a global proof.

For any positive integer h and r in [0,2**h), the exact h-step Collatz
trajectory of n=2**h*k+r has affine form A*k+B for every k>=0.
This is because the coefficient remains even through each of the first h
branch decisions. We independently validate every cell at k=0..3.
"""
import argparse, json
from collections import Counter
from pathlib import Path
from frontier_open import collatz, digest


def cells(h):
    m=1<<h
    result=[]
    for r in range(m):
        a,b=m,r
        branches=[]
        for t in range(h):
            if a%2:raise AssertionError('coefficient parity not determined')
            if b%2:
                a,b=3*a,3*b+1; branches.append('O')
            else:
                a,b=a//2,b//2; branches.append('E')
        assert a>=0 and b>=0
        for k in range(4):
            n=m*k+r
            x=n
            for t in range(h):x=collatz(x)
            assert x==a*k+b,(h,r,k,x,a*k+b)
        da,db=a-m,b-r
        # Exact natural-number threshold for T^h(n) < n, when a<m.
        if da>=0:
            threshold=None
        else:
            denom=m-a
            threshold=max(0,db//denom+1)  # strict: (m-a)*k > (b-r)
        result.append({'r':r,'a':a,'b':b,'trace':''.join(branches),
                       'eventually_descends':a<m,'min_k_for_descent':threshold})
    return result


def survey(depths=(3,4,5,6,8,10)):
    tables=[]
    for h in depths:
        xs=cells(h)
        always=sum(x['min_k_for_descent']==0 for x in xs)
        eventual=sum(x['eventually_descends'] for x in xs)
        tables.append({'steps':h,'residue_classes':1<<h,'asymptotic_descent_classes':eventual,
                       'asymptotic_fraction':round(eventual/(1<<h),7),
                       'descent_from_k0_classes':always,
                       'no_guaranteed_h_step_descent':(1<<h)-eventual,
                       'example_unsettled_by_h_step_test':[x['r'] for x in xs if not x['eventually_descends']][:12],
                       'certificate':digest(xs)})
    return tables


def main():
    p=Path(__file__).resolve().parent
    data={'scope':'exact finite-time affine cells, NOT eventual convergence',
          'survey':survey(),
          'examples_h3':cells(3)}
    (p/'collatz_affine_frontier.json').write_text(json.dumps(data,indent=2)+'\n')
    for t in data['survey']:
        print('h={steps:<2} residues={residue_classes:<5} eventually descend={asymptotic_descent_classes:<5} ({asymptotic_fraction:.1%}) not_certified_by_h_step={no_guaranteed_h_step_descent}'.format(**t))
if __name__=='__main__':main()