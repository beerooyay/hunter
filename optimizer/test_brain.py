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
    def test_reject_bad_input(self):
        p=subprocess.run([str(ROOT/'hunter'),'brain-train'],input='1\n0 999999 0 0 0 0 0 0\n',text=True,capture_output=True)
        self.assertNotEqual(p.returncode,0)
if __name__=='__main__':unittest.main()
