import json,random,subprocess,pathlib,unittest
from bridge_lab import words,offsets,admissible,local_shift_residues,independently_check,primes_up_to
from certificates import bridge_receipt,verify_bridge_receipt,path_receipt,verify_path_receipt,join3
P=pathlib.Path(__file__).resolve().parent
class ExactBridgeTests(unittest.TestCase):
    def test_difference_set_iff_direct(self):
        rng=random.Random(50213)
        for k in range(2,8):
            ws=words(k)
            for _ in range(250):
                A=offsets(rng.choice(ws)); B=offsets(rng.choice(ws))
                for p in primes_up_to(len(A)+len(B)):
                    good=local_shift_residues(A,B,p)
                    for g in range(p):
                        actual=len({x%p for x in A+(tuple(A[-1]+g+b for b in B))})<p
                        self.assertEqual(g in good,actual)
    def test_seven_gap_extremal_proof(self):
        w=(6,10,8,10,2,4,8);v=tuple(reversed(w))
        r=bridge_receipt(w,v);self.assertTrue(verify_bridge_receipt(r))
        self.assertEqual(r['payload']['minimum_bridge'],1858)
        self.assertEqual(r['payload']['crt_period'],30030)
        self.assertEqual(r['payload']['valid_classes'],50)
    def test_three_way_greedy_failure(self):
        r=path_receipt((2,4),(2,4),(4,6))
        self.assertTrue(verify_path_receipt(r))
        self.assertEqual(r['payload']['greedy_bridges'],[18,26])
        self.assertEqual(r['payload']['optimal_bridges'],[24,2])
    def test_invalid_mutation_rejected(self):
        rng=random.Random(1007);A=bridge_receipt((6,10,8,10,2,4,8),(8,4,2,10,8,10,6))
        B=path_receipt((2,4),(2,4),(4,6))
        for receipt,verify in [(A,verify_bridge_receipt),(B,verify_path_receipt)]:
            for _ in range(200):
                changed=json.loads(json.dumps(receipt))
                if rng.choice([0,1])==0:changed['payload']['minimum_bridge' if verify==verify_bridge_receipt else 'total_optimal'] += rng.randrange(1,8)
                else:changed['certificate_id']='0'*64
                with self.assertRaises(ValueError):verify(changed)
    def test_independent_c_full_histogram(self):
        # C program must be built with gcc and run at least for k=5.
        a=subprocess.check_output([str(P/'independent_bridges'),'5',str(P/'words_5.txt'),'2310'],text=True)
        b=subprocess.check_output([str(P/'difference_bridges'),'5',str(P/'words_5.txt'),'2310'],text=True)
        h1=[x for x in a.splitlines() if not x.startswith('extremizer:')]
        self.assertEqual(h1,b.splitlines())
if __name__=='__main__':unittest.main(verbosity=2)