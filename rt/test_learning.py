import itertools
import math
from pathlib import Path
import random
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import calibration
import research
import shared_learning


class LearningTests(unittest.TestCase):
    def test_probability_matches_exhaustive_bernoulli_patterns(self):
        right,left=[2,8,14],[3,9]
        for q in (.01,.2,.8):
            for gap in (0,5,13,23,24):
                total=0.
                for bits in itertools.product((0,1),repeat=5):
                    rs=[r for r,b in zip(right,bits[:3]) if b]
                    ls=[l for l,b in zip(left,bits[3:]) if b]
                    if rs and ls and rs[0]+ls[0]>=gap:
                        total+=q**sum(bits)*(1-q)**(5-sum(bits))
                actual=research.logprob(q,gap,right,left)
                self.assertAlmostEqual(math.exp(actual),total,places=13)

    def test_extreme_tail_stays_in_log_domain(self):
        value=research.logprob(.5,4000,list(range(1,2001)),list(range(1,2001)))
        self.assertTrue(math.isfinite(value))
        self.assertLess(value,-1000)

    def test_censoring_and_heldout_gate(self):
        # Prime hazard is .08 vs a .1 model. Include every failed test.
        rows=[(.1,1000,80,False)]*20+[(.1,1000,80,True)]*5
        learned=calibration.fit(rows)
        self.assertTrue(learned['gate_passed'])
        self.assertEqual(learned['research_scale'],.95)
        # Training disagrees with heldout: refuse the correction.
        rows=[(.1,1000,80,False)]*20+[(.1,1000,120,True)]*5
        self.assertFalse(calibration.fit(rows)['gate_passed'])
        self.assertEqual(calibration.fit(rows)['research_scale'],1)
        self.assertEqual(calibration.fit([(.1,40,0,False)])['research_scale'],1)

    def test_persistent_recipe_warmup_and_atomic_report(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name)
            db=research.connect(folder/'state.db')
            first,reason=research.choose(db,30,random.Random(5))
            self.assertTrue(reason.startswith('warmup'))
            with db:
                db.execute("INSERT INTO jobs VALUES(1,?,30,?,?,1,'complete',10,-50,'warmup')",(research.VERSION,*first))
            db.close()
            db=research.connect(folder/'state.db')
            for i in range(100):
                second,_=research.choose(db,30,random.Random(i))
                self.assertNotEqual(first,second)
            state=research.summary(db,folder,'test')
            self.assertEqual(state['jobs'],1)
            self.assertEqual(state['recipes'][0]['rounds'],1)
            self.assertTrue((folder/'summary.json').exists())
            db.close()

    def test_transfer_requires_both_domains(self):
        lower=[(.1,1000,80,False)]*20+[(.1,1000,80,True)]*5
        higher=[(.1,1000,120,False)]*20+[(.1,1000,120,True)]*5
        self.assertTrue(shared_learning.transfer(lower,lower)['applied'])
        self.assertFalse(shared_learning.transfer(lower,higher)['applied'])
        self.assertFalse(shared_learning.transfer(lower,[])['applied'])
        self.assertEqual(shared_learning.transfer(lower,[])['scale'],1)

    def test_empty_probability(self):
        self.assertEqual(research.logprob(.1,10,[],[1]),-math.inf)
        self.assertEqual(research.logprob(.1,10,[1],[]),-math.inf)


if __name__=='__main__':
    unittest.main()
