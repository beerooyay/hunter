"""Shared memory regressions: baseline feedback, deduplication, verified exchange."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import research
import shared_learning

class SharedTests(unittest.TestCase):
    def test_refresh_and_expiry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'learning').mkdir()
            row=['0']*22
            for i,v in {0:'P4001_d210_L1e9',1:'11',5:'1',7:'20',9:'25.5',11:'100',18:'.02',21:'.01'}.items():row[i]=v
            (root/'gaps.tsv').write_text(('\t'.join(row)+'\n')*2)
            (root/'records.txt').write_text(''.join(f'{g} 10\n' for g in range(1,100002)))
            (root/'FOUND.tsv').write_text('20\t25.5\texpr\n21\t50\tunverified\n')
            (root/'VERIFIED.tsv').write_text('20\t-\texpr\tOK\n')
            db=research.connect(root/'learning/research.sqlite3')
            with db:db.execute('INSERT INTO finds VALUES(?,?,?,?,?,?)',('lab',22,26,1,1,'{}'))
            db.close()
            state=shared_learning.refresh(root)
            self.assertEqual(state['bands']['4001:210']['tested'],1)
            self.assertFalse(state['models']['4001:210']['applied'])
            table=dict(line.split() for line in (root/'learning/known-records.txt').read_text().splitlines())
            self.assertEqual(float(table['20']),25.5)
            self.assertEqual(float(table['21']),10)
            self.assertEqual(float(table['22']),26)
            self.assertTrue(shared_learning.read(root))
            state['expires']=0;(root/'learning/shared.json').write_text(json.dumps(state))
            self.assertEqual(shared_learning.read(root),{})

if __name__=='__main__':unittest.main()
