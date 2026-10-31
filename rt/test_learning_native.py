"""Run against an isolated staged binary/state directory, never production."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('stage',type=Path)
args=parser.parse_args()
stage=args.stage.resolve()
root=Path(__file__).resolve().parents[1]
assert stage!=root and (stage/'hunter').exists()
base='http://127.0.0.1:8778'
def request(path,data=None):
    return json.loads(urllib.request.urlopen(base+path,data=data,timeout=5).read())

# Retain ordinary history but seed two explicit zero-test regression fixtures.
lines=[]
for line in (root/'state.tsv').read_text().splitlines():
    f=line.split('\t')
    if f[0] in ('P6007_d2310_L1e9','P12007_d2310_L1e9'):
        for k in (5,8,9,10,12,13,65):f[k+1]='0'
        f[18]='1' # one logged zero-rate sample
        f[26]=str(-69*(1<<32))
    lines.append('\t'.join(f))
(stage/'state.tsv').write_text('\n'.join(lines)+'\n')
for attempt in (1,2,3):
    p=subprocess.Popen([str(stage/'hunter'),'serve','8778'],cwd=stage,
             env=dict(os.environ,HUNTER_NO_OPEN='1'),stdout=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:state=request('/api/status');break
            except OSError:time.sleep(.1)
        cold=[a for a in state['arms'] if a['key'] in ('P6007_d2310_L1e9','P12007_d2310_L1e9')]
        assert all(a['est']>0 for a in cold)
        assert request('/api/start',b'cores=4&hours=.02&job=60&gpu=0&arms=6007.2310,12007.2310')['ok']
        time.sleep(.3)
        children=[]
        for line in subprocess.check_output(['ps','-axo','pid,ppid,command'],text=True).splitlines()[1:]:
            fields=line.split(None,2)
            if len(fields)==3 and int(fields[1])==p.pid and 'hunt ' in fields[2]:children.append(fields[2].split())
        assert len(children)==2,children
        assert {c[2] for c in children}=={'6007','12007'}
        if attempt<3:
            assert all(c[5]=='20' and float(c[8])==0 for c in children),children
        else:
            assert all(float(c[8])>0 for c in children),children
        print('PASS attempt',attempt,': no duplicate in-flight empty family; correct exploration lambda',flush=True)
    finally:
        p.terminate();p.wait(timeout=10)
    persisted={f[0]:f[1:] for line in (stage/'state.tsv').read_text().splitlines() if (f:=line.split('\t'))[0].startswith('P')}
    assert all(int(persisted[a['key']][65])==min(attempt,2) for a in cold)
print('PASS: priors migrated, attempts capped at 2 and persisted across 3 server restarts')
