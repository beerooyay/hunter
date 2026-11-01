import unittest
from copy import deepcopy
from frontier_open import make_graph,validate,prime,collatz,digest
from collatz_residue_frontier import cells,survey

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.g=make_graph()
    def test_ledger(self):self.assertTrue(validate(deepcopy(self.g)))
    def test_known_witnesses(self):
        self.assertFalse(prime(1681))
        self.assertEqual(collatz(collatz(collatz(5))),4)
        self.assertEqual(collatz(collatz(collatz(3))),16)
    def test_no_global_proof(self):
        self.assertEqual([n['key'] for n in self.g['nodes'] if n['status']=='open'],['collatz_all','goldbach_all'])
    def test_node_tampering(self):
        for i,n in enumerate(self.g['nodes']):
            g=deepcopy(self.g);g['nodes'][i]['scope']='all integers'
            with self.assertRaises(AssertionError):validate(g)
    def test_fake_kernel_promotion(self):
        g=deepcopy(self.g);g['nodes'][1]['status']='kernel_checked';g['nodes'][1]['id']=digest({k:v for k,v in g['nodes'][1].items() if k!='id'})
        with self.assertRaises(AssertionError):validate(g)
    def test_hijacked_edge(self):
        g=deepcopy(self.g);g['edges'][0]['to']='0'*64
        with self.assertRaises(AssertionError):validate(g)
    def test_evidence_tampering(self):
        g=deepcopy(self.g);g['evidence']['goldbach']['witnesses']['30']=[4,26];g['root']=digest({k:v for k,v in g.items() if k!='root'})
        with self.assertRaises(AssertionError):validate(g)
    def test_collatz_exact_residue_cells(self):
        h3=cells(3)
        self.assertEqual(len(h3),8)
        self.assertTrue(all(x['a']>0 for x in h3))
        self.assertEqual(sum(x['eventually_descends'] for x in h3),6)
        self.assertEqual(len(cells(10)),1024)

    def test_collatz_frontier_not_global(self):
        summary=survey()
        self.assertEqual(summary[-1]['steps'],10)
        self.assertGreater(summary[-1]['no_guaranteed_h_step_descent'],0)

    def test_reproducible(self):self.assertEqual(make_graph()['root'],make_graph()['root'])
if __name__=='__main__':unittest.main()