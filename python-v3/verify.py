#!/usr/bin/env python3
"""independent check of every line in FOUND.tsv, using gmpy2 (not the hunter's own code).
confirms: start is a probable prime (BPSW), start+gap is a probable prime, and nothing in between is prime.
usage: python3 verify.py            -> checks FOUND.tsv, writes VERIFIED.tsv
"""
import gmpy2, re, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))

def parse(expr):
    m, P, d, a = map(int, re.fullmatch(r'(\d+)\*(\d+)#/(\d+)-(\d+)', expr).groups())
    return m * gmpy2.primorial(P) // d - a

def main():
    path = os.path.join(HERE, 'FOUND.tsv')
    if not os.path.exists(path): print('no FOUND.tsv yet'); return
    done = set()
    vp = os.path.join(HERE, 'VERIFIED.tsv')
    if os.path.exists(vp): done = {l.split('\t')[2] for l in open(vp)}
    for line in open(path):
        f = line.rstrip('\n').split('\t')
        if len(f) < 3 or not f[0].isdigit(): continue
        gap, merit, expr = f[:3]
        if expr in done: continue
        t = time.time()
        p = parse(expr); g = int(gap)
        ok = gmpy2.is_bpsw_prp(p) and gmpy2.next_prime(p) == p + g and gmpy2.is_bpsw_prp(p + g)
        status = 'OK' if ok else 'FAILED'
        print(f'{status}  gap {gap}  merit {merit}  {expr}  ({time.time()-t:.0f}s)')
        with open(vp, 'a') as f: f.write(f'{gap}\t{merit}\t{expr}\t{status}\n')

if __name__ == '__main__':
    main()
