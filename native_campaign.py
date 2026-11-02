"""Bounded, independent native Praetor volume campaign. Logs/artifacts only."""
import json,os,signal,subprocess,time,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
URL="http://127.0.0.1:8765"
def api(path,data=None):
    body=urllib.parse.urlencode(data).encode() if data is not None else None
    return json.loads(urllib.request.urlopen(URL+path,data=body,timeout=30).read())
def main():
    arm=os.environ['HUNTER_ARM'];run=int(os.environ['GITHUB_RUN_ID']);attempt=int(os.environ.get('GITHUB_RUN_ATTEMPT','1'))
    # Each workflow run reserves one million raw multipliers per family.
    # Retry attempts occupy a separate equally sized block.
    base=(run*100+attempt)*10000000+int(os.environ['HUNTER_SHARD'])*1000000+1
    rows=[]
    for line in (ROOT/'cloud-state-template.tsv').read_text().splitlines():
        f=line.split('\t');f[4]=str(base);rows.append('\t'.join(f))
    (ROOT/'state.tsv').write_text('\n'.join(rows)+'\n')
    deadline=time.monotonic()+18000
    server=subprocess.Popen(['./hunter','serve','8765'],cwd=ROOT,stdout=open('native-server.log','a'),stderr=subprocess.STDOUT,start_new_session=True)
    try:
        for _ in range(120):
            if server.poll() is not None:raise RuntimeError('native server exited')
            try:api('/api/status');break
            except OSError:time.sleep(.5)
        else:raise RuntimeError('startup timeout')
        cores=max(1,os.cpu_count() or 2)
        print('campaign',dict(arm=arm,base=base,cores=cores,seconds=18000),flush=True)
        print(api('/api/start',dict(cores=cores,hours=5,job=60,gpu=0,arms=arm)),flush=True)
        while time.monotonic()<deadline:
            time.sleep(min(60,max(0,deadline-time.monotonic())))
            status=api('/api/status');Path('native-status.json').write_text(json.dumps(status,indent=2))
            print('checkpoint',status.get('found_session'),len(status.get('workers',[])),flush=True)
    finally:
        try:api('/api/stop',dict(now=1))
        except Exception:pass
        if server.poll() is None:
            os.killpg(server.pid,signal.SIGTERM)
            try:server.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(server.pid,signal.SIGKILL);server.wait()
        # Verifiers append independently. Stop only our own descendant verifier jobs.
        for line in subprocess.check_output(['ps','-eo','pid,ppid,args'],text=True).splitlines()[1:]:
            f=line.split(None,2)
            if len(f)==3 and f[2].startswith('hunter verify '):
                try:os.kill(int(f[0]),signal.SIGTERM)
                except ProcessLookupError:pass
if __name__=='__main__':main()
