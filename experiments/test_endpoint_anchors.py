import itertools,random,unittest
from endpoint_anchors import anchor_pairs,all_pairs,RecordFrontier
class AnchorTests(unittest.TestCase):
 def test_all_prime_patterns(self):
  for a in ([],[-20],[-20,-13,-3,2,4,14,30],list(range(8))):
   for bits in itertools.product((False,True),repeat=len(a)):
    primes={v for v,b in zip(a,bits) if b}
    for threshold in (1,2,7,15,25,51):
     self.assertEqual(anchor_pairs(a,primes.__contains__,threshold),all_pairs(a,primes.__contains__,threshold))
 def test_random_patterns_and_no_duplicate_tests(self):
  rng=random.Random(5)
  for _ in range(400):
   a=sorted(rng.sample(range(-1000,1001),rng.randrange(1,100)));primes=set(rng.sample(a,rng.randrange(len(a)+1)));seen=set()
   def test(x):
    self.assertNotIn(x,seen);seen.add(x);return x in primes
   gap=rng.randrange(1,1500)
   self.assertEqual(anchor_pairs(a,test,gap),all_pairs(a,primes.__contains__,gap))
 def test_record_frontier_never_excludes_an_improvement(self):
  text='\n'.join(f'{g} {g/7:.8f}' for g in range(2,102,2));frontier=RecordFrontier(text,100,25)
  for lower in range(1,30):
   threshold=frontier.minimum(lower)
   for g in range(2,min(threshold,102),2):
    self.assertLess(g,25*lower)
    self.assertLessEqual(g,frontier.records[g]*lower)
  missing=RecordFrontier('2 10\n6 10',10,25)
  self.assertEqual(missing.minimum(10),4)
if __name__=='__main__':unittest.main()
