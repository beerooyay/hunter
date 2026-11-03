"""Bounded volume integration campaign. Each segment checkpoints on the same runner.
No perpetual relaunch, issue comments, paid runners, or experimental pruning.
"""
import argparse, json, os, signal, subprocess, time, urllib.parse, urllib.request
from pathlib import Path
from calibration import atomic_json
ROOT=Path(__file__).resolve().parent
ARMS=['6007.210','6007.2310','8009.210','8009.2310','6007.210','6007.2310','4001.210','4001.2310','8009.210','6007.2310']

def reservation(run,attempt,shard):
    if not(0<run and 1<=attempt<=9 and 0<=shard<10): raise ValueError('invalid campaign identity')
    base=run*100000000+attempt*10000000+shard*1000000+1
    if base+1000000>=2**64: raise ValueError('reservation exceeds native range')
    return base,base+1000000

def api(path,form=None):
    data=urllib.parse.urlencode(form).encode() if form is not None else None
    with urllib.request.urlopen('http://127.0.0.1:8765'+path,data=data,timeout=20) as r:return json.load(r)

def run(seconds):
    runid=int(os.environ['GITHUB_RUN_ID']);attempt=int(os.environ.get('GITHUB_RUN_ATTEMPT','1'));shard=int(os.environ['HUNTER_SHARD']);base,end=reservation(runid,attempt,shard)
    if not(ROOT/'state.tsv').exists():
        lines=[]
        for line in (ROOT/'optimizer/seed-state.tsv').read_text().splitlines():
            f=line.split('\t')
            if len(f)<5:continue
            f[4]=str(base);lines.append('\t'.join(f))
        (ROOT/'state.tsv').write_text('\n'.join(lines)+'\n')
    env=dict(os.environ,HUNTER_NO_OPEN='1');env.pop('HUNT_RECORD_ANCHORS',None);env.pop('HUNT_FIXED_PRP_NS',None)
    output=ROOT/'fleet-output';output.mkdir(exist_ok=True)
    log=open(output/'server.log','a')
    server=subprocess.Popen(['./hunter','serve','8765'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    def terminate(sig,frame):raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,terminate)
    began=time.monotonic();status={};state='failed'
    try:
        for _ in range(60):
            if server.poll() is not None:raise RuntimeError('server exited')
            try:api('/api/status');break
            except OSError:time.sleep(.5)
        else:raise RuntimeError('startup timeout')
        api('/api/start',dict(cores=max(1,os.cpu_count() or 2),hours=1,job=min(120,max(1,seconds)),gpu=0,arms=ARMS[shard]))
        while time.monotonic()-began<seconds:
            status=api('/api/status')
            for line in (ROOT/'state.tsv').read_text().splitlines():
                f=line.split('\t')
                if len(f)>=5 and int(f[4])>=end-65536:raise RuntimeError('reserved multiplier range nearly exhausted')
            atomic_json(output/'checkpoint.json',dict(updated=time.time(),run_id=runid,shard=shard,arm=ARMS[shard],status='running',native=status,range=[base,end],policy='baseline'))
            time.sleep(min(15,max(0,seconds-(time.monotonic()-began))))
        api('/api/stop',{})
        drain=time.monotonic()+130
        while time.monotonic()<drain:
            status=api('/api/status')
            if not status.get('running') and not status.get('workers'):break
            time.sleep(2)
        state='complete'
    finally:
        try:api('/api/stop',{'now':1})
        except Exception:pass
        if server.poll() is None:
            os.killpg(server.pid,signal.SIGTERM)
            try:server.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(server.pid,signal.SIGKILL);server.wait()
        log.close()
        import shutil
        for name in ('gaps.tsv','jobs.tsv','state.tsv','FOUND.tsv','VERIFIED.tsv','hunt.log'):
            if (ROOT/name).exists():shutil.copy2(ROOT/name,output/name)
        atomic_json(output/'checkpoint.json',dict(updated=time.time(),run_id=runid,shard=shard,arm=ARMS[shard],status=state,native=status,range=[base,end],policy='baseline',code=os.environ.get('GITHUB_SHA')))
        print(json.dumps(dict(shard=shard,state=state,elapsed=time.monotonic()-began)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=600);a=p.parse_args()
    if not 1<=a.seconds<=1800:raise ValueError('bounded segments only')
    run(a.seconds)
