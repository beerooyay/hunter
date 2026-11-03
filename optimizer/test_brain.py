import json, subprocess, tempfile, unittest
from pathlib import Path
from optimizer.brain import dataset, train, ROOT
from fleet_campaign import reservation
from control_room import extract_snapshot
import io,zipfile
class BrainTests(unittest.TestCase):
    def native(self,rows):
        wire=str(len(rows))+'\n'+''.join(' '.join(map(str,row))+'\n' for row in rows)
        return subprocess.run([str(ROOT/'hunter'),'brain-train'],input=wire,text=True,capture_output=True,check=True).stdout
    def test_heldout_labels_cannot_change_weights(self):
        rows=[[0,65536,20000,10000,15000,30000,20000,28000]]*200
        a=self.native(rows+[[1,65536,10000,20000,20000,30000,30000,0],[2,65536,10000,20000,20000,30000,30000,0]])
        b=self.native(rows+[[1,65536,10000,20000,20000,30000,30000,65536],[2,65536,10000,20000,20000,30000,30000,65536]])
        self.assertEqual(a,b)
        values=[int(x.split('\t')[2]) for x in a.splitlines() if x.startswith('P\t')]
        self.assertTrue(all(0<=x<=65536 for x in values));self.assertLess(abs(values[0]-28000),abs(20000-28000))
    def test_dataset_dedup_and_block_splits(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=['P6007_d210_L1e9','123456','2567','0','0','0','-1','100','0','0','0','5','0','0','0','0','1','0','.001','0','2']
            p=Path(tmp)/'gaps.tsv';p.write_text('\t'.join(f)+'\n'+'\t'.join([f[0],'123457',*f[2:]])+'\n')
            rows,_,_=dataset([p,p]);self.assertEqual(len(rows),2);self.assertEqual(rows[0]['split'],rows[1]['split']);self.assertTrue(all(not r['completed'] for r in rows))
    def test_reservations_disjoint(self):
        intervals=[reservation(41500000000+r,a,s) for r in range(2) for a in (1,2,9) for s in range(10)]
        intervals.sort();self.assertTrue(all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])))
    def test_artifact_traversal_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            blob=io.BytesIO()
            with zipfile.ZipFile(blob,'w') as z:z.writestr('../oops','bad');z.writestr('gaps.tsv','data')
            dest=Path(tmp)/'snapshot';extract_snapshot(blob.getvalue(),dest)
            self.assertFalse((Path(tmp)/'oops').exists());self.assertEqual((dest/'gaps.tsv').read_text(),'data')
    def test_native_frozen_inference_matches_integer_reference(self):
        from optimizer.brain import Q
        model=json.loads((ROOT/'optimizer/seed-model.json').read_text())
        weights=model['weights'];x=[Q,25000,5960,16000,32000,18000]
        def div(a,b):return (abs(a)//b)*(-1 if a<0 else 1)
        h=[max(0,min(2*Q,sum(div(weights[j*6+k]*x[k],Q) for k in range(6)))) for j in range(8)]
        want=max(0,min(Q,x[5]+weights[56]+sum(div(weights[48+j]*h[j],Q) for j in range(8))))
        wire='1\n'+' '.join(map(str,[2,*x,0]))+'\n'+' '.join(str(v%(2**64)) for v in weights)+'\n'
        p=subprocess.run([str(ROOT/'hunter'),'brain-train','predict'],input=wire,text=True,capture_output=True,check=True)
        self.assertEqual(int(p.stdout.splitlines()[0].split('\t')[2]),want)
    def test_ambiguous_scheduled_dispatch_is_not_retried(self):
        from unittest.mock import patch
        import control_room as c
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'STORE',Path(tmp)),patch.object(c,'launch',side_effect=RuntimeError('ambiguous network failure')) as launch:
            c.atomic_json(Path(tmp)/'schedule.json',dict(status='pending',at=1,workers=8))
            c.schedule_check();c.schedule_check()
            self.assertEqual(launch.call_count,1)
            self.assertEqual(c.read(Path(tmp)/'schedule.json')['status'],'failed')
    def test_reject_bad_input(self):
        p=subprocess.run([str(ROOT/'hunter'),'brain-train'],input='1\n0 999999 0 0 0 0 0 0\n',text=True,capture_output=True)
        self.assertNotEqual(p.returncode,0)
if __name__=='__main__':unittest.main()
