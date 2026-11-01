from construction import *
import random

def test_results():
    for p in [13,19,31,37,43,61,67,73,97,103]:
        row=optimize(p)
        assert row['greedy_cost'] == 2*p
        assert row['optimal_cost']==6
        assert row['p_residue_missing']==[[1,7],[3,p-1],[1]]

def test_prime_offset_admissibility():
    # Independent direct admissibility checks without construction.optimize.
    for p in [13,19,31,37]:
        pats,small,Q=construct(p)
        for pattern in pats:
            assert not verify_admissible(pattern, small)
        assert not verify_admissible(materialize(pats[:2],[2]),small)
        assert not verify_admissible(materialize(pats,[2,2*p-2]),small)
        assert not verify_admissible(materialize(pats,[4,2]),small)
        for g in range(2,2*p-2,2):
            assert verify_admissible(materialize(pats,[2,g]),small)

def test_boundary_attack():
    for p in [13,19,31,37,43]:
        pats,small,_=construct(p)
        assert 3 in verify_admissible(materialize(pats,[2,2]),small)
        assert p in verify_admissible(materialize(pats,[2,2]),small)
        assert p not in verify_admissible(materialize(pats,[4,2]),small)
        assert p not in verify_admissible(materialize(pats,[2,2*p-2]),small)

def test_reject_inputs():
    for p in [2,3,5,7,11,17,23,29,41,49,91]:
        try: construct(p)
        except ValueError: pass
        else: raise AssertionError(f'Accepted bad p={p}')

def run():
    tests=[test_results,test_prime_offset_admissibility,test_boundary_attack,test_reject_inputs]
    for f in tests:f(); print('PASS',f.__name__)
    print('ALL PASS',len(tests))

if __name__=='__main__':run()