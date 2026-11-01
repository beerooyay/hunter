import copy
import json
import unittest
from pathlib import Path
import planner
import checker

class TestPlanning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipts=json.loads((Path(__file__).parent/'certificates.json').read_text())

    def test_independent_checker(self):
        for r in self.receipts:
            self.assertTrue(checker.check_receipt(r))

    def test_greedy_unbounded_family(self):
        for r in self.receipts[:6]:
            p=r['problem']['p']
            self.assertEqual(r['greedy']['cost'],2*p)
            self.assertEqual(r['optimal']['cost'],6)
            self.assertEqual(r['optimal']['bridges'],[4,2])
            self.assertEqual(len(r['excluded_cheaper']),1)
            self.assertEqual(r['excluded_cheaper'][0]['modulus'],3)

    def test_explicit_paths(self):
        self.assertEqual(self.receipts[6]['greedy']['cost'],44)
        self.assertEqual(self.receipts[6]['optimal']['cost'],26)
        self.assertEqual(len(self.receipts[6]['excluded_cheaper']),66)

    def test_independent_brute_small_words(self):
        words=[(2,4),(2,6),(4,2),(4,6),(6,2)]
        for i in range(30):
            chosen=[words[(i+j*3+j*j)%len(words)] for j in range(3)]
            patterns=planner.motifs_from_words(chosen)
            receipt=planner.make_receipt(patterns,{'kind':'gap-words','words':chosen})
            checker.check_receipt(receipt)

    def test_tampering(self):
        r=self.receipts[6]
        mutations=[]
        def mutate(path,value):
            x=copy.deepcopy(r)
            dst=x
            for k in path[:-1]:dst=dst[k]
            dst[path[-1]]=value
            mutations.append(x)
        mutate(['optimal','cost'],8)
        mutate(['optimal','bridges'],[2,2])
        mutate(['greedy','cost'],42)
        mutate(['greedy','bridges'],[4,40])
        mutate(['offsets_sha256'],'a'*64)
        mutate(['pattern_sizes'],[4,3,3])
        mutate(['excluded_cheaper'],r['excluded_cheaper'][1:])
        mutate(['excluded_cheaper',0,'modulus'],997)
        mutate(['scope'],'proved Goldbach')
        mutate(['problem','words'],[[2,2],[2,4],[4,6]])
        for x in mutations:
            with self.assertRaises((ValueError,AssertionError)):
                checker.check_receipt(x)

if __name__=='__main__':unittest.main(verbosity=2)