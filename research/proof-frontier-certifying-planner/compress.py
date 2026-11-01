"""Modular nogood compression of lower-cost repair certificates.

A nogood is a fully verified pair of bridge residues mod prime p. Because
admissibility depends only on translated residues mod p, this nogood excludes
EVERY pair sharing those residues, not just one point. The verifier independently
checks its local modular obstruction and exact coverage of all cheaper paths.
"""
import json
from pathlib import Path
import checker


def residue_witness(patterns,q,a,b):
    shift1=patterns[0][-1]+a
    shift2=patterns[0][-1]+a+patterns[1][-1]+b
    residues={(x+shift)%q for pattern,shift in zip(patterns,[0,shift1,shift2]) for x in pattern}
    return len(residues)==q


def compress(receipt):
    patterns=checker.reconstruct(receipt['problem'])
    pairs=[(r['g'],r['h']) for r in receipt['excluded_cheaper']]
    n=sum(map(len,patterns))
    sets={}
    for g,h in pairs:
        for q in checker.prime_list(n):
            a,b=g%q,h%q
            key=(q,a,b)
            if key not in sets and residue_witness(patterns,*key):
                sets[key]=set()
            if key in sets:sets[key].add((g,h))
    uncovered=set(pairs);selected=[]
    while uncovered:
        candidates=[(len(v&uncovered),k) for k,v in sets.items()]
        size,key=max(candidates)
        if not size:raise AssertionError('not coverable')
        selected.append({'prime':key[0],'g_mod':key[1],'h_mod':key[2]})
        uncovered-=sets[key]
    return {'source':receipt['problem'], 'optimal':receipt['optimal'],
            'lower_count':len(pairs),'nogoods':selected,
            'scope':'modular admissibility only'}


def verify(receipt):
    patterns=checker.reconstruct(receipt['source'])
    C=receipt['optimal']['cost'];g,h=receipt['optimal']['bridges']
    assert C==g+h and g>0 and h>0 and not g%2 and not h%2
    assert checker.check_obstruction(patterns,g,h) is None
    nogoods=receipt['nogoods'];n=sum(map(len,patterns))
    for row in nogoods:
        q,a,b=row['prime'],row['g_mod'],row['h_mod']
        assert q in checker.prime_list(n) and 0<=a<q and 0<=b<q
        assert residue_witness(patterns,q,a,b)
    expected=sum(1 for cost in range(4,C,2) for g in range(2,cost-1,2))
    assert receipt['lower_count']==expected
    for cost in range(4,C,2):
        for g in range(2,cost-1,2):
            h=cost-g
            assert any(g%r['prime']==r['g_mod'] and h%r['prime']==r['h_mod'] for r in nogoods)
    assert receipt['scope']=='modular admissibility only'
    return True


def main():
    rs=json.loads((Path(__file__).parent/'certificates.json').read_text())
    compressed=[compress(r) for r in rs]
    for x in compressed:verify(x)
    (Path(__file__).parent/'compressed_certificates.json').write_text(json.dumps(compressed,indent=2)+'\n')
    print('COMPRESSED OPTIMALITY CERTIFICATES:')
    for r,c in zip(rs,compressed):
        print(' ',r['problem'],'excluded',len(r['excluded_cheaper']),'nogoods',len(c['nogoods']))

if __name__=='__main__':main()