#!/usr/bin/env python3
"""Independent checks of exact comparison, selection, and prime counting."""
import unittest
from fractions import Fraction
from itertools import product
from pathlib import Path
from math import prod, log
import random
import subprocess
import tempfile

from bridge_rank import (primes_to, offsets, admissible, combined, exact_score,
                         best_bridge, pareto_frontier, motifs)


class BridgeTests(unittest.TestCase):
    def test_exact_euler_ratio(self):
        rng=random.Random(917)
        for _ in range(75):
            wa,wb=rng.choice(motifs(2)),rng.choice(motifs(2))
            report=best_bridge(wa,wb,48)
            if report is None: continue
            B=report['cutoff']
            e1=combined(wa,wb,report['shortest'][0])
            e2=combined(wa,wb,report['best'][0])
            k=len(e1)
            # Compute exact rational Euler product up to B via independent formula.
            def trunc(H):
                f=Fraction(1)
                for p in range(2,B+1):
                    if p not in primes_to(B):continue
                    nu=len({h%p for h in H})
                    f*=Fraction(p-nu,p)*Fraction(p,p-1)**k
                return f
            lhs=trunc(e2)/trunc(e1)
            rhs=Fraction(report['best'][1],report['shortest'][1])
            self.assertEqual(lhs,rhs)
            # For primes > B (including 1009), every residue is distinct.
            for p in (1009,1013,2003):
                self.assertEqual(len({h%p for h in e1}),k)
                self.assertEqual(len({h%p for h in e2}),k)

    def test_pareto_is_lossless(self):
        rng=random.Random(1938)
        for _ in range(80):
            a,b=rng.choice(motifs(2)),rng.choice(motifs(2))
            B=offsets(a)[-1]+96+offsets(b)[-1]
            valid=[(g,exact_score(combined(a,b,g),B)) for g in range(2,97,2)
                   if admissible(combined(a,b,g))]
            front=pareto_frontier(valid)
            for x in (10000,1_000_000,10_000_000,1_000_000_000):
                score=lambda r: (log(r[1])-r[0]/log(x),-r[0])
                self.assertEqual(max(valid,key=score),max(front,key=score))

    def test_input_validation(self):
        with self.assertRaises(ValueError): offsets((0,))
        with self.assertRaises(ValueError): offsets((2,1.0))
        with self.assertRaises(ValueError): best_bridge((3,),(2,),96)
        with self.assertRaises(ValueError): best_bridge((2,),(2,),0)
        with self.assertRaises(ValueError): best_bridge((2,),(2,),96,reference_n=1)

    def test_known_valid_bridge(self):
        r=best_bridge((2,4),(2,6),96)
        self.assertEqual(r['shortest'][0],6)
        self.assertTrue(admissible(combined((2,4),(2,6),6)))
        self.assertFalse(admissible(offsets((2,4,2,6))))

    def test_small_prime_counts_against_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            src=Path(__file__).with_name('count_patterns.c')
            out=d/'counter'
            subprocess.run(['cc','-std=c11','-O2',str(src),'-o',str(out)],check=True,capture_output=True)
            input=d/'input.tsv'
            words=[(2,4,6,2,6),(2,4,2,4,2),(4,6,6,4,6)]
            with input.open('w') as f:
                for i,w in enumerate(words):
                    o=offsets(w)
                    f.write('\t'.join([str(i),str(i),'test',str(len(o))]+list(map(str,o)))+'\n')
            cp=subprocess.run([str(out),str(input),'110000','100003'],capture_output=True,text=True,check=True)
            records=[line.split(',') for line in cp.stdout.strip().splitlines()[1:]]
            N=110000+max(offsets(w)[-1] for w in words)
            isp=bytearray(b'\x01')*(N+1);isp[0:2]=b'\x00\x00'
            for i in range(2,int(N**.5)+1):
                if isp[i]:isp[i*i:N+1:i]=b'\x00'*((N-i*i)//i+1)
            for word,row in zip(words,records):
                o=offsets(word)
                t=c=0
                for p in range(100003,110001):
                    if isp[p] and all(isp[p+j] for j in o):
                        t+=1
                        if sum(isp[p:p+o[-1]+1])==len(o):c+=1
                self.assertEqual((t,c),(int(row[3]),int(row[4])))

if __name__=='__main__':unittest.main()