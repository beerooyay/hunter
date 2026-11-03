import json,os,random,subprocess,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from persistent_probe import ProbeWorker
import moon
ROOT=Path(__file__).resolve().parents[1]
class CachedTests(unittest.TestCase):
 def test_incremental_batches_match_fresh_native_and_original(self):
  with tempfile.TemporaryDirectory() as d:
   worker=ProbeWorker(ROOT/'hunter',d,time.monotonic()+120)
   try:
    rng=random.Random(123)
    for start,limit in [(10000001,32),(123456789101,256),(987654321101,64)]:
     shallow,_,_,_=worker.probe(start,limit,1000000)
     selected=sorted(rng.sample([r['m']-start for r in shallow],min(7,len(shallow))))
     refined,_,_,_=worker.probe(start,limit,10000000,selected)
     full,_,_,_=worker.probe(start,limit,10000000)
     ref={r['m']:r for r in full}
     self.assertEqual({r['m'] for r in refined},{start+i for i in selected})
     for r in refined:
      for key in ('right','left','q','ln','logp'):self.assertEqual(r[key],ref[r['m']][key])
     # Check unchanged standalone probe route as an independent setup/reference.
     raw=subprocess.check_output([str(ROOT/'hunter'),'probe','1439','2310',str(limit),'25',str(start),'10000000'],cwd=ROOT,env=dict(os.environ,HUNTER_PATTERNS='1'),text=True)
     independent=moon.parse(raw)
     for r in independent:
      for key in ('right','left','q','ln','logp'):self.assertEqual(r[key],ref[r['m']][key])
    worker.proc.stdin.write(b'10000001 32 10000000 1 0\n');worker.proc.stdin.flush()
    worker.proc.wait(timeout=5);self.assertNotEqual(worker.proc.returncode,0)
   finally:worker.close()
if __name__=='__main__':unittest.main()
